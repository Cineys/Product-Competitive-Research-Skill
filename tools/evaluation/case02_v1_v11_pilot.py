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


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_snapshot(skill, manifest_path):
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    actual = {str(path.relative_to(skill)): sha256(path)
              for path in sorted(skill.rglob("*")) if path.is_file()}
    if actual != manifest["files"]:
        raise RuntimeError(f"snapshot integrity failure: {skill}")
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


def command_for(codex, model, reasoning, workspace, output):
    return [
        codex, "--no-daemon", "exec", "--ignore-rules", "--ephemeral",
        "--skip-git-repo-check", "--strict-config", "--json", "--color", "never",
        "--model", model, "--sandbox", "read-only",
        "-c", f'model_reasoning_effort="{reasoning}"',
        "-c", 'web_search="disabled"',
        "-c", 'approval_policy="never"',
        "-c", "project_doc_max_bytes=0",
        "-c", "features.apps=false",
        "-C", str(workspace), "-o", str(output), "-",
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prep-root", type=Path, required=True)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--reasoning", default="low")
    parser.add_argument("--execute-model-calls", action="store_true")
    args = parser.parse_args()
    root = args.prep_root.resolve()
    plan = json.loads((root / "pilot-plan.json").read_text(encoding="utf-8"))
    codex = shutil.which("codex")
    if not codex:
        raise SystemExit("codex CLI not found")
    auth_source = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "auth.json"

    rendered = []
    for version in ("v1", "v1_1"):
        run_root = root / "pilot" / version
        workspace = run_root / "workspace"
        results = run_root / "results"
        skill = root / "snapshots" / version / "product-competitive-research"
        snapshot_manifest = root / "snapshots" / version / f"{version}-manifest.json"
        snapshot_before = verify_snapshot(skill, snapshot_manifest)
        home = run_root / "codex-home"
        trace = results / "fixture-trace.jsonl"
        config = (
            "[mcp_servers.fixture_eval]\n"
            f"command = {json.dumps(str(MCP_LAUNCHER))}\n"
            "args = []\n"
            "required = true\n\n"
            "[mcp_servers.fixture_eval.env]\n"
            f"FIXTURE_MANIFEST = {json.dumps(str(root / 'fixture-repo/tests/fixtures/case-02/manifest.json'))}\n"
            f"FIXTURE_REPO_ROOT = {json.dumps(str(root / 'fixture-repo'))}\n"
            f"FIXTURE_TRACE_PATH = {json.dumps(str(trace))}\n"
        )
        prompt = (
            "请读取并遵循 ./product-competitive-research/SKILL.md 及当前任务所需引用文件。\n"
            "本次只能使用 fixture_eval 的 fixture_search 与 fixture_read；禁止使用网络、内置网页搜索或 shell 读取 fixture 文件。\n"
            "搜索摘要只用于发现来源；具体事实必须通过 fixture_read 读取正文后核验。\n\n" + REQUEST
        )
        output = results / "final-answer.md"
        command = command_for(codex, args.model, args.reasoning, workspace, output)
        rendered.append({"version": version, "command": command, "prompt": prompt,
                         "skill": str(skill), "config": config})
        if not args.execute_model_calls:
            continue
        if not auth_source.is_file():
            raise SystemExit("auth.json is required only when executing model calls")
        if home.exists():
            raise SystemExit(f"refusing to reuse pilot home: {home}")
        home.mkdir(mode=0o700)
        shutil.copyfile(auth_source, home / "auth.json")
        (home / "auth.json").chmod(0o600)
        (home / "config.toml").write_text(config, encoding="utf-8")
        link = workspace / "product-competitive-research"
        if link.exists() or link.is_symlink():
            raise SystemExit(f"refusing to reuse workspace: {workspace}")
        link.symlink_to(skill, target_is_directory=True)
        (results / "prompt.txt").write_text(prompt, encoding="utf-8")
        metadata = {"version": version, "started_at": now(), "model": args.model,
                    "reasoning": args.reasoning, "command": command,
                    "web_search": "disabled", "sandbox": "read-only",
                    "snapshot_sha256_before": snapshot_before}
        save(results / "run-metadata.json", metadata)
        env = {k: v for k, v in os.environ.items()
               if not k.startswith(("CODEX_", "OPENAI_", "AZURE_OPENAI_"))}
        env["CODEX_HOME"] = str(home)
        with (results / "events.jsonl").open("w") as stdout, \
                (results / "stderr.log").open("w") as stderr:
            outcome = subprocess.run(command, input=prompt, text=True, env=env,
                                     stdout=stdout, stderr=stderr)
        evidence = inspect_events(results / "events.jsonl")
        snapshot_after = verify_snapshot(skill, snapshot_manifest)
        metadata.update(ended_at=now(), exit_code=outcome.returncode,
                        event_summary=evidence, snapshot_sha256_after=snapshot_after,
                        snapshot_unchanged=snapshot_before == snapshot_after,
                        final_answer_exists=output.is_file() and output.stat().st_size > 0)
        metadata["status"] = "completed" if (
            outcome.returncode == 0 and evidence["turn_completed"] and not evidence["errors"]
            and not evidence["tool_failures"]
            and metadata["final_answer_exists"] and metadata["snapshot_unchanged"]
        ) else "failed"
        save(results / "run-metadata.json", metadata)
        (home / "auth.json").unlink(missing_ok=True)
        if metadata["status"] != "completed":
            raise SystemExit(
                f"{version} execution failed; preserved artifacts and stopped before the next run"
            )
    save(root / "pilot-rendered-plan.json", {
        "generated_at": now(), "model_calls_executed": args.execute_model_calls,
        "model": args.model, "reasoning": args.reasoning, "runs": rendered,
        "metric_layers": {
            "research_quality": ["fact coverage", "verified evidence validity", "uncertainty handling"],
            "delivery_efficiency": ["final answer output tokens", "readability", "embedded JSON size"],
            "execution_cost": ["total input/output tokens", "wall time", "tool calls", "tool failures"],
        },
    })
    if not args.execute_model_calls:
        print("PLAN ONLY: no model calls executed")
        for item in rendered:
            print(item["version"], " ".join(item["command"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
