#!/usr/bin/env python3
"""Plan or explicitly execute the isolated two-call Case 2 pilot.

Without --execute-model-calls this script performs no model invocation.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys


REQUEST = "对比 Figma 和 Sketch 的最新付费档位与协作人数上限。"
REPO = Path(__file__).resolve().parents[2]
MCP_LAUNCHER = REPO / "tools/evaluation/run_fixture_mcp.sh"
CONTRACT_AUDITOR = REPO / "tools/evaluation/audit_research_contract.py"
SKILL_NAME = "product-competitive-research"
AUDIT_CONFIRMATION = "RUN_EVIDENCE_AUDIT"
REQUIRED_REFERENCES = ("references/evidence-policy.md", "references/analysis-framework.md")
INFRASTRUCTURE_ERROR_MARKERS = (
    "approval", "permission", "timed out", "timeout", "server", "connection",
    "initialize", "initialise", "unavailable", "transport", "broken pipe",
)


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_with_temporary_auth(auth_source, auth_target, operation):
    """Run an operation with a temporary credential copy and always attempt cleanup."""
    shutil.copyfile(auth_source, auth_target)
    auth_target.chmod(0o600)
    try:
        return operation()
    finally:
        auth_target.unlink(missing_ok=True)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_snapshot(skill, manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = {str(path.relative_to(skill)): sha256(path)
              for path in sorted(skill.rglob("*")) if path.is_file()}
    if actual != manifest["files"]:
        raise RuntimeError(f"snapshot integrity failure: {skill}")
    return actual


def verify_fixture_snapshot(root):
    manifest = json.loads((root / "fixture-manifest-sha256.json").read_text(encoding="utf-8"))
    actual = {name: sha256(root / "fixture-repo" / name) for name in manifest["files"]}
    if actual != manifest["files"]:
        raise RuntimeError("fixture snapshot integrity failure")
    return actual


def inspect_events(path):
    events, invalid = [], []
    for number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        try:
            events.append(json.loads(line))
        except ValueError:
            invalid.append(number)
    completed = [event for event in events if event.get("type") == "item.completed"]
    tools = [event.get("item") for event in completed
             if event.get("item", {}).get("type") not in ("agent_message", "reasoning")]
    return {
        "thread_ids": [event.get("thread_id") for event in events if event.get("type") == "thread.started"],
        "turn_completed": any(event.get("type") == "turn.completed" for event in events),
        "usage": [event.get("usage") for event in events if event.get("type") == "turn.completed"],
        "errors": [event for event in events if event.get("type") in ("error", "turn.failed")],
        "tool_failures": [item for item in tools
                          if item.get("status") == "failed" or item.get("error")],
        "invalid_jsonl_lines": invalid,
        "tools": tools,
    }


def successful_tool_names(evidence):
    return [item.get("tool") for item in evidence["tools"]
            if item.get("type") == "mcp_tool_call"
            and item.get("status") == "completed" and not item.get("error")]


def local_file_read_evidence(evidence, relative_path, expected_text):
    """Require a successful local command whose captured output contains the exact file."""
    normalized = relative_path.replace("\\", "/")
    for item in evidence["tools"]:
        if item.get("type") != "command_execution" or item.get("status") != "completed":
            continue
        command = str(item.get("command", "")).replace("\\", "/")
        output = str(item.get("aggregated_output", ""))
        if normalized in command and expected_text.strip() in output:
            return {"item_id": item.get("id"), "command": item.get("command")}
    return None


def classify_run(exit_code, evidence, final_answer_exists, snapshot_unchanged,
                 skill_read, reference_reads, required_mcp_tools):
    process_completed = exit_code == 0
    model_turn_completed = evidence["turn_completed"]
    infrastructure_tool_failures = []
    behavior_tool_failures = []
    for item in evidence["tool_failures"]:
        message = json.dumps(item.get("error"), ensure_ascii=False).casefold()
        target = (infrastructure_tool_failures if any(marker in message
                  for marker in INFRASTRUCTURE_ERROR_MARKERS) else behavior_tool_failures)
        target.append(item)
    infrastructure_failure = bool(
        not process_completed or evidence["errors"] or evidence["invalid_jsonl_lines"]
        or infrastructure_tool_failures
    )
    successful = successful_tool_names(evidence)
    missing_mcp_tools = [name for name in required_mcp_tools if name not in successful]
    missing_references = [name for name, item in reference_reads.items() if not item]
    model_behavior_failure = bool(
        not infrastructure_failure and (
            not model_turn_completed or not final_answer_exists or not snapshot_unchanged
            or not skill_read or missing_references or missing_mcp_tools
            or behavior_tool_failures
        )
    )
    research_task_completed = bool(
        process_completed and model_turn_completed and not infrastructure_failure
        and not model_behavior_failure
    )
    return {
        "process_completed": process_completed,
        "model_turn_completed": model_turn_completed,
        "research_task_completed": research_task_completed,
        "infrastructure_failure": infrastructure_failure,
        "model_behavior_failure": model_behavior_failure,
        "infrastructure_tool_failures": infrastructure_tool_failures,
        "behavior_tool_failures": behavior_tool_failures,
        "missing_required_mcp_tools": missing_mcp_tools,
        "missing_required_references": missing_references,
    }


def should_stop_after_run(outcome):
    return outcome["infrastructure_failure"]


def fixture_config(root, trace):
    return (
        "[mcp_servers.fixture_eval]\n"
        f"command = {json.dumps(str(MCP_LAUNCHER))}\n"
        "args = []\n"
        "required = true\n"
        'enabled_tools = ["fixture_search", "fixture_read"]\n'
        'default_tools_approval_mode = "approve"\n\n'
        "[mcp_servers.fixture_eval.tools.fixture_search]\n"
        'approval_mode = "approve"\n\n'
        "[mcp_servers.fixture_eval.tools.fixture_read]\n"
        'approval_mode = "approve"\n\n'
        "[mcp_servers.fixture_eval.env]\n"
        f"FIXTURE_MANIFEST = {json.dumps(str(root / 'fixture-repo/tests/fixtures/case-02/manifest.json'))}\n"
        f"FIXTURE_REPO_ROOT = {json.dumps(str(root / 'fixture-repo'))}\n"
        f"FIXTURE_TRACE_PATH = {json.dumps(str(trace))}\n"
    )


def install_discoverable_skill(workspace, skill):
    link = workspace / ".agents" / "skills" / SKILL_NAME
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.exists() or link.is_symlink():
        raise RuntimeError(f"refusing to reuse skill discovery path: {link}")
    link.symlink_to(skill, target_is_directory=True)
    return link


def command_for(codex, model, reasoning, workspace, output, mode="real-user"):
    sandbox = "workspace-write" if mode == "evidence-audit" else "read-only"
    command = [
        codex, "--no-daemon", "exec", "--ignore-rules", "--ephemeral",
        "--skip-git-repo-check", "--strict-config", "--json", "--color", "never",
        "--model", model, "--sandbox", sandbox,
        "-c", f'model_reasoning_effort="{reasoning}"',
        "-c", 'web_search="disabled"',
        "-c", 'approval_policy="never"',
        "-c", "project_doc_max_bytes=0",
        "-c", "features.apps=false",
    ]
    if mode == "evidence-audit":
        command.extend(("-c", "sandbox_workspace_write.network_access=false",
                        "-c", "allow_login_shell=false"))
    command.extend(("-C", str(workspace), "-o", str(output), "-"))
    return command


def prompt_for(mode):
    prompt = (
        "请使用 $product-competitive-research Skill。先通过本地文件读取工具读取自动发现的 "
        ".agents/skills/product-competitive-research/SKILL.md 及当前任务所需引用文件；"
        "不得使用 fixture 工具读取 Skill 或 references。\n"
        "本次只能使用 fixture_eval 的 fixture_search 与 fixture_read；禁止使用网络、内置网页搜索或 shell 读取 fixture 文件。\n"
        "搜索摘要只用于发现来源；具体事实必须通过 fixture_read 读取正文后核验。\n"
    )
    if mode == "evidence-audit":
        prompt += (
            "这是结构化证据审计模式。请根据所加载 Skill 自身定义的 Schema，在当前工作目录实际生成且只生成 "
            "report.md 和 research_contract.json 两个正式交付文件。不得在最终回答中重复完整 JSON，也不得由报告事后转换或补造契约。\n"
            "必须实际运行 .agents/skills/product-competitive-research/scripts/validate_research.py "
            "research_contract.json；最终回答只简短说明文件已生成及真实校验结果。\n"
        )
    return prompt + "\n" + REQUEST


def output_inventory(workspace):
    entries = []
    for path in workspace.rglob("*"):
        relative = path.relative_to(workspace)
        if relative.parts and relative.parts[0] == ".agents":
            continue
        if path.is_dir() and not path.is_symlink():
            continue
        entries.append(relative.as_posix())
    names = sorted(entries)
    temporary = [name for name in names
                 if any(part.startswith(".") for part in Path(name).parts)
                 or name.endswith((".tmp", "~", ".swp"))]
    unexpected = [name for name in names
                  if name not in ("report.md", "research_contract.json") and name not in temporary]
    deliverables = {
        name: {"exists": (workspace / name).is_file(),
               "regular_file": (workspace / name).is_file() and not (workspace / name).is_symlink(),
               "sha256": sha256(workspace / name) if (workspace / name).is_file() else None}
        for name in ("report.md", "research_contract.json")
    }
    return {"deliverables": deliverables, "temporary_files": temporary,
            "unexpected_files": unexpected, "all_non_skill_entries": names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prep-root", type=Path, required=True)
    parser.add_argument("--run-root", type=Path,
                        help="Fresh directory for this pilot's isolated workspaces and results")
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--reasoning", default="low")
    parser.add_argument("--mode", choices=("real-user", "evidence-audit"),
                        default="real-user")
    parser.add_argument("--plan-output", type=Path)
    parser.add_argument("--execute-model-calls", action="store_true")
    parser.add_argument("--confirm-model-calls")
    args = parser.parse_args()
    root = args.prep_root.resolve()
    execution_root = (args.run_root.resolve() if args.run_root
                      else root / "pilot")
    plan = json.loads((root / "pilot-plan.json").read_text(encoding="utf-8"))
    if (args.execute_model_calls and args.mode == "evidence-audit"
            and args.confirm_model_calls != AUDIT_CONFIRMATION):
        raise SystemExit(
            f"evidence-audit model calls require --confirm-model-calls {AUDIT_CONFIRMATION}")
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("codex CLI not found")
    auth_source = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"

    plan_output = args.plan_output.resolve() if args.plan_output else None
    if args.execute_model_calls and plan_output is None:
        plan_output = execution_root / "pilot-rendered-plan.json"
    if plan_output is not None and plan_output.exists():
        raise SystemExit(f"refusing to overwrite existing plan: {plan_output}")

    rendered = []
    for version in ("v1", "v1_1"):
        run_root = execution_root / version
        workspace = run_root / "workspace"
        results = run_root / "results"
        skill = root / "snapshots" / version / "product-competitive-research"
        snapshot_manifest = root / "snapshots" / version / f"{version}-manifest.json"
        snapshot_before = verify_snapshot(skill, snapshot_manifest)
        fixture_before = verify_fixture_snapshot(root)
        home = run_root / "codex-home"
        trace = results / "fixture-trace.jsonl"
        config = fixture_config(root, trace)
        prompt = prompt_for(args.mode)
        output = results / "final-answer.md"
        command = command_for(codex, args.model, args.reasoning, workspace, output, args.mode)
        rendered.append({"version": version, "command": command, "prompt": prompt,
                         "skill": str(skill), "config": config, "mode": args.mode})
        if not args.execute_model_calls:
            continue
        if not auth_source.is_file():
            raise SystemExit("auth.json is required only when executing model calls")
        if run_root.exists():
            raise SystemExit(f"refusing to reuse pilot run directory: {run_root}")
        workspace.mkdir(parents=True)
        results.mkdir(parents=True)
        home.mkdir(mode=0o700)
        (home / "config.toml").write_text(config, encoding="utf-8")
        install_discoverable_skill(workspace, skill)
        (results / "prompt.txt").write_text(prompt, encoding="utf-8")
        metadata = {"version": version, "started_at": now(), "model": args.model,
                    "reasoning": args.reasoning, "command": command,
                    "web_search": "disabled",
                    "sandbox": "workspace-write" if args.mode == "evidence-audit" else "read-only",
                    "mode": args.mode,
                    "snapshot_sha256_before": snapshot_before}
        save(results / "run-metadata.json", metadata)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("CODEX_", "OPENAI_", "AZURE_OPENAI_"))}
        env["CODEX_HOME"] = str(home)
        env["PYTHONDONTWRITEBYTECODE"] = "1"

        def execute_model_call():
            with (results / "events.jsonl").open("w") as stdout, \
                    (results / "stderr.log").open("w") as stderr:
                return subprocess.run(command, input=prompt, text=True, env=env,
                                      stdout=stdout, stderr=stderr)

        outcome = run_with_temporary_auth(
            auth_source, home / "auth.json", execute_model_call)
        evidence = inspect_events(results / "events.jsonl")
        snapshot_after = verify_snapshot(skill, snapshot_manifest)
        fixture_after = verify_fixture_snapshot(root)
        skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
        skill_read = local_file_read_evidence(
            evidence, f".agents/skills/{SKILL_NAME}/SKILL.md", skill_text)
        reference_reads = {
            name: local_file_read_evidence(
                evidence, f".agents/skills/{SKILL_NAME}/{name}",
                (skill / name).read_text(encoding="utf-8"))
            for name in REQUIRED_REFERENCES
        }
        metadata.update(ended_at=now(), exit_code=outcome.returncode,
                        event_summary=evidence, snapshot_sha256_after=snapshot_after,
                        snapshot_unchanged=snapshot_before == snapshot_after,
                        fixture_sha256_before=fixture_before,
                        fixture_sha256_after=fixture_after,
                        fixture_unchanged=fixture_before == fixture_after,
                        final_answer_exists=output.is_file() and output.stat().st_size > 0,
                        skill_read_evidence=skill_read,
                        reference_read_evidence=reference_reads)
        metadata["outcome"] = classify_run(
            outcome.returncode, evidence, metadata["final_answer_exists"],
            metadata["snapshot_unchanged"], skill_read, reference_reads,
            ("fixture_search", "fixture_read"))
        if args.mode == "evidence-audit":
            inventory = output_inventory(workspace)
            metadata["output_inventory"] = inventory
            deliverables_ok = all(item["regular_file"]
                                  for item in inventory["deliverables"].values())
            output_boundary_ok = not inventory["temporary_files"] and not inventory["unexpected_files"]
            audit_output = results / "evidence-audit.json"
            audit_command = [
                sys.executable, str(CONTRACT_AUDITOR), "--version", version,
                "--contract", str(workspace / "research_contract.json"),
                "--events", str(results / "events.jsonl"), "--trace", str(trace),
                "--fixture-manifest", str(root / "fixture-repo/tests/fixtures/case-02/manifest.json"),
                "--fixture-root", str(root / "fixture-repo"),
                "--validator", str(skill / "scripts/validate_research.py"),
                "--output", str(audit_output),
            ]
            audit_process = None
            audit_result = None
            if deliverables_ok:
                audit_process = subprocess.run(
                    audit_command, cwd=workspace,
                    env={**env, "PYTHONDONTWRITEBYTECODE": "1"},
                    capture_output=True, text=True)
                (results / "audit-stdout.log").write_text(audit_process.stdout, encoding="utf-8")
                (results / "audit-stderr.log").write_text(audit_process.stderr, encoding="utf-8")
                if audit_output.is_file():
                    audit_result = json.loads(audit_output.read_text(encoding="utf-8"))
            audit_ok = bool(audit_process and audit_process.returncode == 0 and audit_result)
            metadata["contract_audit"] = {
                "command": audit_command, "executed": audit_process is not None,
                "exit_code": audit_process.returncode if audit_process else None,
                "result": audit_result, "automatic_checks_passed": audit_ok,
            }
            isolation_ok = metadata["snapshot_unchanged"] and metadata["fixture_unchanged"]
            if not isolation_ok:
                metadata["outcome"]["infrastructure_failure"] = True
                metadata["outcome"]["research_task_completed"] = False
            if not (deliverables_ok and output_boundary_ok and audit_ok):
                metadata["outcome"]["model_behavior_failure"] = not metadata["outcome"]["infrastructure_failure"]
                metadata["outcome"]["research_task_completed"] = False
        metadata["status"] = ("completed" if metadata["outcome"]["research_task_completed"]
                              else "failed")
        save(results / "run-metadata.json", metadata)
        if should_stop_after_run(metadata["outcome"]):
            raise SystemExit(
                f"{version} infrastructure failure; preserved artifacts and stopped before the next run"
            )
    rendered_plan = {
        "generated_at": now(), "model_calls_executed": args.execute_model_calls,
        "model": args.model, "reasoning": args.reasoning, "mode": args.mode,
        "runs": rendered,
        "metric_layers": {
            "research_quality": ["fact coverage", "verified evidence validity", "uncertainty handling"],
            "delivery_efficiency": ["final answer output tokens", "readability", "embedded JSON size"],
            "execution_cost": ["total input/output tokens", "wall time", "tool calls", "tool failures"],
        },
    }
    if plan_output is not None:
        plan_output.parent.mkdir(parents=True, exist_ok=True)
        save(plan_output, rendered_plan)
    if not args.execute_model_calls:
        print("PLAN ONLY: no model calls executed")
        for item in rendered:
            print(item["version"], " ".join(item["command"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
