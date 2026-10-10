#!/usr/bin/env python3
"""Execute non-model smoke checks for snapshots, MCP tools, trace, and network denial."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


REPO = Path(__file__).resolve().parents[2]
LAUNCHER = REPO / "tools/evaluation/run_fixture_mcp.sh"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def snapshot_hashes(root, version):
    skill = root / "snapshots" / version / "product-competitive-research"
    return {str(path.relative_to(skill)): sha256(path)
            for path in sorted(skill.rglob("*")) if path.is_file()}


def rpc_call(process, request):
    process.stdin.write(json.dumps(request, separators=(",", ":")) + "\n")
    process.stdin.flush()
    line = process.stdout.readline()
    if not line:
        raise RuntimeError("MCP server closed stdout")
    response = json.loads(line)
    if "error" in response:
        raise RuntimeError(response["error"])
    return response["result"]


def probe_command(prefix):
    code = (
        "import socket,sys; s=socket.socket(); s.settimeout(1); "
        "\ntry: s.connect(('127.0.0.1',9))"
        "\nexcept PermissionError: print('NETWORK_DENIED'); sys.exit(0)"
        "\nexcept OSError as e: print('NOT_POLICY_DENIAL',repr(e)); sys.exit(2)"
        "\nelse: print('NETWORK_ALLOWED'); sys.exit(3)"
    )
    return subprocess.run(prefix + ["/usr/bin/python3", "-c", code],
                          capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prep-root", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    root = args.prep_root.resolve()
    report_path = args.report.resolve()
    manifest = root / "fixture-repo/tests/fixtures/case-02/manifest.json"
    trace = root / "smoke/fixture-trace.jsonl"
    trace.parent.mkdir(parents=True, exist_ok=True)
    before = {version: snapshot_hashes(root, version) for version in ("v1", "v1_1")}

    env = dict(os.environ)
    env.update(FIXTURE_MANIFEST=str(manifest),
               FIXTURE_REPO_ROOT=str(root / "fixture-repo"),
               FIXTURE_TRACE_PATH=str(trace))
    process = subprocess.Popen([str(LAUNCHER)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, env=env)
    checks = {}
    try:
        initialized = rpc_call(process, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2025-06-18", "capabilities": {},
                       "clientInfo": {"name": "fixture-smoke", "version": "1"}}})
        process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
        process.stdin.flush()
        tools = rpc_call(process, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        search = rpc_call(process, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
            "params": {"name": "fixture_search", "arguments": {"query": "Figma"}}})["structuredContent"]
        known_url = search["results"][0]["url"]
        read = rpc_call(process, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
            "params": {"name": "fixture_read", "arguments": {"url": known_url}}})["structuredContent"]
        missing = rpc_call(process, {"jsonrpc": "2.0", "id": 5, "method": "tools/call",
            "params": {"name": "fixture_read", "arguments": {"url": "https://unknown.invalid/page"}}})["structuredContent"]
    finally:
        process.stdin.close()
        process.wait(timeout=5)
    stderr = process.stderr.read()
    trace_events = [json.loads(line) for line in trace.read_text(encoding="utf-8").splitlines()]
    after = {version: snapshot_hashes(root, version) for version in ("v1", "v1_1")}

    source = next(item for item in json.loads(manifest.read_text(encoding="utf-8"))["sources"]
                  if item["source_url"] == known_url)
    expected_body = (root / "fixture-repo" / source["fixture_path"]).read_text(encoding="utf-8")
    checks.update({
        "mcp_initialized": initialized["serverInfo"]["name"] == "fixture-eval",
        "only_expected_tools": [item["name"] for item in tools["tools"]] == ["fixture_search", "fixture_read"],
        "search_has_no_body_field": bool(search["results"]) and all("body" not in item for item in search["results"]),
        "search_has_short_snippets": all(len(item["snippet"]) <= 181 for item in search["results"]),
        "read_returns_exact_body": read.get("status") == "ok" and read.get("body") == expected_body,
        "unknown_url_not_found": missing == {"status": "not_found", "url": "https://unknown.invalid/page"},
        "trace_sequence": [event["sequence"] for event in trace_events] == [1, 2, 3],
        "trace_tools": [event["tool"] for event in trace_events] == ["fixture_search", "fixture_read", "fixture_read"],
        "trace_statuses": [event["status"] for event in trace_events] == ["ok", "ok", "not_found"],
        "server_clean_exit": process.returncode == 0 and not stderr,
        "snapshots_unchanged": before == after,
        "snapshots_read_only": all(not (path.stat().st_mode & 0o222)
            for version in ("v1", "v1_1")
            for path in (root / "snapshots" / version / "product-competitive-research").rglob("*") if path.is_file()),
        "independent_run_directories": (root / "pilot/v1/workspace").resolve() != (root / "pilot/v1_1/workspace").resolve(),
    })

    seatbelt = probe_command(["/usr/bin/sandbox-exec", "-p", "(version 1)(allow default)(deny network*)"])
    codex_sandbox = probe_command(["codex", "sandbox", "-P", ":read-only"])
    checks["mcp_launcher_network_denied"] = seatbelt.returncode == 0 and "NETWORK_DENIED" in seatbelt.stdout
    checks["codex_sandbox_network_denied"] = codex_sandbox.returncode == 0 and "NETWORK_DENIED" in codex_sandbox.stdout

    plan = json.loads((root / "pilot-plan.json").read_text(encoding="utf-8"))
    checks["same_fixture_for_both_versions"] = plan["versions"] == ["v1", "v1_1"] and bool(plan["fixture_sha256"])
    checks["no_model_calls_recorded"] = plan["model_calls_executed"] is False
    report = {
        "status": "pass" if all(checks.values()) else "fail",
        "checks": checks,
        "trace_path": str(trace),
        "network_probes": {
            "sandbox_exec": {"returncode": seatbelt.returncode, "stdout": seatbelt.stdout, "stderr": seatbelt.stderr},
            "codex_sandbox": {"returncode": codex_sandbox.returncode, "stdout": codex_sandbox.stdout, "stderr": codex_sandbox.stderr},
        },
        "snapshot_hashes_before": before,
        "snapshot_hashes_after": after,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
