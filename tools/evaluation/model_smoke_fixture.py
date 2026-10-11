#!/usr/bin/env python3
"""Plan or explicitly run one minimal model smoke for Skill + fixture MCP wiring.

The default is plan-only. A model call requires both --execute-model-call and
the exact confirmation token --confirm-model-call RUN_ONE_MODEL_SMOKE.
"""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import case02_v1_v11_pilot as pilot


CONFIRMATION = "RUN_ONE_MODEL_SMOKE"
PROMPT = """请使用 $product-competitive-research Skill 完成最小基础设施检查，不要生成竞品分析报告。
1. 使用本地文件读取命令完整读取 .agents/skills/product-competitive-research/SKILL.md。不得用 fixture 工具读取 Skill。
2. 调用 fixture_eval.fixture_search，query 为 Figma。
3. 从搜索结果选择第一个 URL，调用 fixture_eval.fixture_read。
4. 简短输出：Skill 数据契约版本、读取到的 source_id、title 和 content_sha256。
禁止使用 web search、其他 MCP、真实网络或 shell 读取 fixture 文件。
"""


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def load_trace(path):
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prep-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--version", choices=("v1", "v1_1"), required=True)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--reasoning", default="low")
    parser.add_argument("--execute-model-call", action="store_true")
    parser.add_argument("--confirm-model-call")
    args = parser.parse_args()

    root = args.prep_root.resolve()
    output_root = args.output_root.resolve()
    skill = root / "snapshots" / args.version / pilot.SKILL_NAME
    manifest = root / "snapshots" / args.version / f"{args.version}-manifest.json"
    snapshot_before = pilot.verify_snapshot(skill, manifest)
    trace = output_root / "results/fixture-trace.jsonl"
    config = pilot.fixture_config(root, trace)
    workspace = output_root / "workspace"
    results = output_root / "results"
    home = output_root / "codex-home"
    final_answer = results / "final-answer.md"
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("codex CLI not found")
    command = pilot.command_for(codex, args.model, args.reasoning, workspace, final_answer)
    plan = {
        "generated_at": now(), "model_calls_executed": False,
        "explicit_confirmation_required": CONFIRMATION,
        "version": args.version, "model": args.model, "reasoning": args.reasoning,
        "skill": str(skill), "skill_sha256": snapshot_before["SKILL.md"],
        "workspace_skill_path": str(workspace / ".agents/skills" / pilot.SKILL_NAME),
        "command": command, "prompt": PROMPT, "config": config,
    }
    if output_root.exists():
        raise SystemExit(f"refusing to reuse model smoke output: {output_root}")
    output_root.mkdir(parents=True)
    save(output_root / "smoke-plan.json", plan)
    if not args.execute_model_call:
        print("PLAN ONLY: no model call executed")
        print(" ".join(command))
        return 0
    if args.confirm_model_call != CONFIRMATION:
        raise SystemExit(f"model call requires --confirm-model-call {CONFIRMATION}")

    auth_source = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"
    if not auth_source.is_file():
        raise SystemExit("auth.json is required only when executing the model smoke")
    workspace.mkdir()
    results.mkdir()
    home.mkdir(mode=0o700)
    shutil.copyfile(auth_source, home / "auth.json")
    (home / "auth.json").chmod(0o600)
    (home / "config.toml").write_text(config, encoding="utf-8")
    pilot.install_discoverable_skill(workspace, skill)
    (results / "prompt.txt").write_text(PROMPT, encoding="utf-8")
    metadata = {
        **plan, "started_at": now(), "web_search": "disabled", "sandbox": "read-only",
        "snapshot_sha256_before": snapshot_before,
    }
    save(results / "run-metadata.json", metadata)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("CODEX_", "OPENAI_", "AZURE_OPENAI_"))}
    env["CODEX_HOME"] = str(home)
    try:
        with (results / "events.jsonl").open("w") as stdout, \
                (results / "stderr.log").open("w") as stderr:
            outcome = subprocess.run(command, input=PROMPT, text=True, env=env,
                                     stdout=stdout, stderr=stderr)
    finally:
        (home / "auth.json").unlink(missing_ok=True)

    evidence = pilot.inspect_events(results / "events.jsonl")
    snapshot_after = pilot.verify_snapshot(skill, manifest)
    skill_text = (skill / "SKILL.md").read_text(encoding="utf-8")
    skill_read = pilot.local_file_read_evidence(
        evidence, f".agents/skills/{pilot.SKILL_NAME}/SKILL.md", skill_text)
    trace_events = load_trace(trace)
    successful_mcp = [item.get("tool") for item in evidence["tools"]
                      if item.get("type") == "mcp_tool_call"
                      and item.get("status") == "completed" and not item.get("error")]
    successful_trace = [event.get("tool") for event in trace_events if event.get("status") == "ok"]
    trace_matches_events = successful_mcp == successful_trace == ["fixture_search", "fixture_read"]
    serialized_events = json.dumps(evidence, ensure_ascii=False).casefold()
    no_web_search = "web_search" not in serialized_events and "search_query" not in serialized_events
    no_network_escalation = all(marker not in serialized_events for marker in (
        "request_permissions", "sandbox_approval", "network_access", "require_escalated"))
    final_exists = final_answer.is_file() and final_answer.stat().st_size > 0
    classified = pilot.classify_run(
        outcome.returncode, evidence, final_exists, snapshot_before == snapshot_after,
        skill_read, {}, ("fixture_search", "fixture_read"))
    smoke_completed = bool(
        classified["research_task_completed"] and trace_matches_events
        and no_web_search and no_network_escalation)
    metadata.update({
        "model_calls_executed": True, "ended_at": now(), "exit_code": outcome.returncode,
        "event_summary": evidence, "skill_read_evidence": skill_read,
        "fixture_trace": trace_events, "trace_matches_events": trace_matches_events,
        "no_web_search": no_web_search, "no_network_permission_escalation": no_network_escalation,
        "snapshot_sha256_after": snapshot_after,
        "snapshot_unchanged": snapshot_before == snapshot_after,
        "final_answer_exists": final_exists, "outcome": classified,
        "smoke_completed": smoke_completed,
    })
    save(results / "run-metadata.json", metadata)
    return 0 if smoke_completed else 1


if __name__ == "__main__":
    sys.exit(main())
