#!/usr/bin/env python3
"""Prepare and run Case 2 once from an ordinary macOS Terminal (stdlib only).

Never import this module to run the evaluation: execution requires main().
No additional Seatbelt file-isolation preflight is used. Formal runs rely on
Codex's own read-only sandbox; strict filesystem isolation is not independently
verified and the two environments are not claimed to be fully isolated.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone


REQUEST = "对比 Figma 和 Sketch 最新的付费套餐与协作人数上限。"
TAG = "v0.1.0-mvp"
SKILL_PATH = "skills/product-competitive-research"
REPO = Path(__file__).resolve().parents[2]


def now():
    return datetime.now(timezone.utc).isoformat()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def checked(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, **kwargs)


def inspect_events(path):
    events, invalid = [], []
    for number, line in enumerate(path.read_text(errors="replace").splitlines(), 1):
        try:
            events.append(json.loads(line))
        except ValueError:
            invalid.append(number)
    items = [e.get("item", {}) for e in events if e.get("type") == "item.completed"]
    return {
        "thread_ids": [e.get("thread_id") for e in events if e.get("type") == "thread.started"],
        "usage": [e.get("usage") for e in events if e.get("type") == "turn.completed"],
        "errors": [e for e in events if e.get("type") in ("error", "turn.failed")],
        "turn_completed": any(e.get("type") == "turn.completed" for e in events),
        "invalid_jsonl_lines": invalid,
        "tools": [i for i in items if i.get("type") not in ("agent_message", "reasoning")],
        "web_search_events": [i for i in items if i.get("type") == "web_search"],
        "actual_model": next((e["model"] for e in events if isinstance(e.get("model"), str)), None),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="gpt-6.1-sol")
    parser.add_argument("--reasoning", default="low")
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("This evaluation requires macOS.")
    if any(os.environ.get(k) for k in ("CODEX_THREAD_ID", "CODEX_SESSION_ID", "CODEX_SANDBOX")):
        parser.error("Run in an ordinary Terminal, outside an active Codex session.")
    codex = shutil.which("codex")
    if not codex:
        parser.error("codex must already be installed.")

    # A new output root every time, outside the repository; never overwrite a run.
    base = Path.home() / "Projects" / "case02-evaluation"
    base.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix="run-", dir=base)).resolve()
    results = root / "results"
    results.mkdir()
    print("Results:", results, flush=True)
    manifest = {"started_at": now(), "tag": TAG, "request": REQUEST,
                "requested_model": args.model, "reasoning": args.reasoning,
                "sandbox": "read-only", "web_search": "live", "runs": {},
                "additional_seatbelt_preflight": "disabled",
                "filesystem_isolation": "Not independently verified; formal runs rely on Codex read-only sandbox.",
                "environments_fully_isolated": False,
                "full_delivery_chain_tested": False,
                "network_capability": "Same requested live search; actual access requires event review.",
                "status": "preparing"}
    homes = []
    try:
        # Copy only auth, never config, history, plugins, rules, or cached skills.
        auth_home = Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
        auth = auth_home / "auth.json"
        if not auth.is_file():
            raise RuntimeError("Existing auth.json required; no login or authentication fallback is attempted.")
        for name in ("control", "skill"):
            (root / name).mkdir()
            home = Path(tempfile.mkdtemp(prefix="case02-codex-home-"))
            home.chmod(0o700)
            homes.append(home)
            shutil.copyfile(auth, home / "auth.json")
            (home / "auth.json").chmod(0o600)
        manifest["tag_commit"] = checked(["git", "-C", str(REPO), "rev-parse", TAG], text=True).stdout.strip()
        files = checked(["git", "-C", str(REPO), "ls-tree", "-r", "--name-only", TAG,
                         "--", SKILL_PATH], text=True).stdout.splitlines()
        if not files:
            raise RuntimeError("Tagged Skill directory is missing.")
        extracted = root / "skill" / "product-competitive-research"
        hashes = {}
        for filename in files:
            relative = Path(filename).relative_to(SKILL_PATH)
            target = extracted / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            data = checked(["git", "-C", str(REPO), "show", f"{TAG}:{filename}"]).stdout
            target.write_bytes(data)
            target.chmod(0o444)
            if target.read_bytes() != data:
                raise RuntimeError("Skill extraction verification failed.")
            hashes[str(relative)] = hashlib.sha256(data).hexdigest()
        manifest["skill_sha256"] = hashes

        envs = {}
        for index, name in enumerate(("control", "skill")):
            env = {k: v for k, v in os.environ.items()
                   if not k.startswith(("CODEX_", "OPENAI_", "AZURE_OPENAI_"))}
            env["CODEX_HOME"] = str(homes[index])
            envs[name] = env

        # Configuration discovery only: these commands never call a model.
        help_text = checked([codex, "exec", "--help"], env=envs["control"], text=True).stdout
        for flag in ("--ignore-user-config", "--ignore-rules", "--ephemeral", "--json", "--sandbox"):
            if flag not in help_text:
                raise RuntimeError("Required CLI option is unsupported: " + flag)
        manifest["cli_version"] = checked([codex, "--version"], env=envs["control"], text=True).stdout.strip()
        common = [codex, "--no-daemon", "exec", "--ignore-user-config", "--ignore-rules",
                  "--ephemeral", "--skip-git-repo-check", "--json", "--color", "never",
                  "--model", args.model, "--sandbox", "read-only",
                  "-c", 'model_reasoning_effort=' + json.dumps(args.reasoning),
                  "-c", 'web_search="live"', "-c", 'approval_policy="never"',
                  "-c", "project_doc_max_bytes=0"]
        manifest["common_command"] = common

        manifest["status"] = "running"
        save(results / "run-metadata.json", manifest)

        for name in ("control", "skill"):
            prompt = REQUEST if name == "control" else (
                "请读取并遵循 ./product-competitive-research/SKILL.md 及其所需引用文件。\n\n" + REQUEST)
            (results / f"{name}-prompt.txt").write_text(prompt)
            final = results / f"{name}-result.txt"
            command = common + ["-C", str(root / name), "-o", str(final), "-"]
            record = {"started_at": now(), "command": command, "status": "running"}
            manifest["runs"][name] = record
            save(results / "run-metadata.json", manifest)
            print(f"Starting {name} (one new codex exec session)", flush=True)
            with (results / f"{name}-events.jsonl").open("w") as stdout, \
                    (results / f"{name}-stderr.log").open("w") as stderr:
                outcome = subprocess.run(command, input=prompt, text=True,
                                         env=envs[name], stdout=stdout, stderr=stderr)
            record.update(ended_at=now(), exit_code=outcome.returncode)
            evidence = inspect_events(results / f"{name}-events.jsonl")
            record["event_summary"] = evidence
            record["status"] = "completed" if (outcome.returncode == 0 and evidence["turn_completed"]
                and not evidence["errors"] and final.exists() and final.stat().st_size) else "failed"
            save(results / "run-metadata.json", manifest)
            if record["status"] != "completed":
                raise RuntimeError(f"{name} failed; review its stderr and JSONL. No retry; remaining group skipped.")
            # Do not automatically infer official-page access from URL strings.
            # Terminal CLI JSONL may expose searches without page bodies or model ID.
        a = manifest["runs"]["control"]["event_summary"]["thread_ids"]
        b = manifest["runs"]["skill"]["event_summary"]["thread_ids"]
        if not a or not b or set(a) & set(b):
            raise RuntimeError("Independent thread IDs could not be verified; result requires review.")
        manifest["status"] = "completed_pending_evidence_review"
    except (Exception, KeyboardInterrupt) as error:
        manifest["status"] = "stopped"
        manifest["failure_reason"] = str(error) or type(error).__name__
        print("Stopped:", manifest["failure_reason"], file=sys.stderr)
    finally:
        # Remove copied credentials and disposable runtime state, retain all logs.
        for home in homes:
            shutil.rmtree(home)
        manifest["ended_at"] = now()
        save(results / "run-metadata.json", manifest)
        (results / "REVIEW.txt").write_text(
            "Case 2: review original JSONL, stderr and final answers for the six agreed criteria.\n"
            "URL presence is not proof of access. Search results are not page-body access.\n"
            "Verify successful commands reading SKILL.md and required references in B.\n"
            "Model IDs absent from events remain unknown; requested model is recorded separately.\n"
            "Identical live search settings do not prove successful live access. If unavailable,\n"
            "latest prices are unverified. Missing page/tool details remain unverified.\n"
            "No complete report/JSON/validator delivery chain is tested in read-only mode.\n"
            "Additional Seatbelt file-isolation preflight is disabled. Strict filesystem\n"
            "isolation is not independently verified and the two environments are not\n"
            "claimed to be fully isolated. Formal runs rely on Codex read-only sandbox.\n"
            "Authentication usability and network access are established only by a run.\n"
            "No automatic scoring, retries, resume, or additional inference sessions.\n")
    return 0 if manifest["status"] == "completed_pending_evidence_review" else 1


if __name__ == "__main__":
    sys.exit(main())
