#!/usr/bin/env python3
"""Freeze V1, V1.1, and Case 2 fixtures without touching the worktree."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess


REPO = Path(__file__).resolve().parents[2]
SKILL = Path("skills/product-competitive-research")
V1_COMMIT = "0d47fc0aea4bcc0aa63d7e650ebdaa90f48e4df0"
CORE_FILES = (
    "SKILL.md",
    "references/clarification.md",
    "references/evidence-policy.md",
    "references/analysis-framework.md",
    "assets/report-template.md",
    "scripts/validate_research.py",
)


def run(args, text=False):
    return subprocess.run(args, cwd=REPO, check=True, capture_output=True, text=text).stdout


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def freeze_v1(target):
    files = run(["git", "ls-tree", "-r", "--name-only", V1_COMMIT, "--", str(SKILL)], text=True).splitlines()
    if not files:
        raise RuntimeError("V1 skill not found in Git")
    for filename in files:
        relative = Path(filename).relative_to(SKILL)
        output = target / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(run(["git", "show", f"{V1_COMMIT}:{filename}"]))


def freeze_v11(target):
    source = REPO / SKILL
    shutil.copytree(source, target)


def manifest_for(version, source, target):
    files = sorted(path for path in target.rglob("*") if path.is_file())
    core = {name: sha256(target / name) for name in CORE_FILES}
    record = {
        "version": version,
        "source": source,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": {str(path.relative_to(target)): sha256(path) for path in files},
        "core_files": core,
    }
    save(target.parent / f"{version}-manifest.json", record)
    for path in files:
        path.chmod(0o444)
    for directory in sorted((p for p in target.rglob("*") if p.is_dir()), reverse=True):
        directory.chmod(0o555)
    target.chmod(0o555)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = args.output.resolve()
    if root.exists():
        raise SystemExit(f"refusing to overwrite existing output: {root}")
    root.mkdir(parents=True)

    snapshots = root / "snapshots"
    v1 = snapshots / "v1" / "product-competitive-research"
    v11 = snapshots / "v1_1" / "product-competitive-research"
    v1.mkdir(parents=True)
    freeze_v1(v1)
    freeze_v11(v11)
    v1_record = manifest_for("v1", {"kind": "git_commit", "commit": V1_COMMIT}, v1)
    v11_record = manifest_for("v1_1", {"kind": "worktree_snapshot", "path": str(REPO / SKILL)}, v11)

    fixture_root = root / "fixture-repo" / "tests" / "fixtures" / "case-02"
    shutil.copytree(REPO / "tests" / "fixtures" / "case-02", fixture_root)
    fixture_files = sorted(path for path in fixture_root.rglob("*") if path.is_file())
    fixture_record = {
        "source": str(REPO / "tests" / "fixtures" / "case-02"),
        "files": {str(path.relative_to(root / "fixture-repo")): sha256(path) for path in fixture_files},
    }
    save(root / "fixture-manifest-sha256.json", fixture_record)
    for path in fixture_files:
        path.chmod(0o444)
    for directory in sorted((p for p in fixture_root.rglob("*") if p.is_dir()), reverse=True):
        directory.chmod(0o555)
    fixture_root.chmod(0o555)

    for version in ("v1", "v1_1"):
        (root / "pilot" / version / "workspace").mkdir(parents=True)
        (root / "pilot" / version / "results").mkdir(parents=True)
    save(root / "pilot-plan.json", {
        "case_id": "case-02-pilot",
        "model_calls_executed": False,
        "versions": ["v1", "v1_1"],
        "v1_core_sha256": v1_record["core_files"],
        "v1_1_core_sha256": v11_record["core_files"],
        "fixture_sha256": fixture_record["files"],
        "fixture_manifest": str(root / "fixture-repo/tests/fixtures/case-02/manifest.json"),
    })
    print(root)


if __name__ == "__main__":
    main()
