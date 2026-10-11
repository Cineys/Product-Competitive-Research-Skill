"""Non-model tests for the deterministic fixture MCP implementation."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import importlib.util

from tests.test_validate_research import ROOT


PREPARE = ROOT / "tools/evaluation/prepare_behavior_eval.py"
SMOKE = ROOT / "tools/evaluation/smoke_fixture_harness.py"
PILOT = ROOT / "tools/evaluation/case02_v1_v11_pilot.py"
MODEL_SMOKE = ROOT / "tools/evaluation/model_smoke_fixture.py"


def load_pilot_module():
    spec = importlib.util.spec_from_file_location("case02_v1_v11_pilot", PILOT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixtureHarnessTests(unittest.TestCase):
    def prepare(self, directory):
        prep = Path(directory) / "prep"
        subprocess.run([sys.executable, str(PREPARE), "--output", str(prep)],
                       cwd=ROOT, check=True, capture_output=True, text=True)
        return prep

    def test_failed_tool_event_is_reported(self):
        pilot = load_pilot_module()
        with tempfile.TemporaryDirectory(prefix="fixture-events-") as temporary:
            events = Path(temporary) / "events.jsonl"
            events.write_text(
                '\n'.join((
                    json.dumps({"type": "item.completed", "item": {
                        "type": "mcp_tool_call", "status": "failed",
                        "error": {"message": "denied"}}}),
                    json.dumps({"type": "turn.completed", "usage": {}}),
                )) + '\n', encoding="utf-8")
            evidence = pilot.inspect_events(events)
            self.assertTrue(evidence["turn_completed"])
            self.assertEqual(len(evidence["tool_failures"]), 1)

    def test_run_classification_distinguishes_infrastructure_and_behavior(self):
        pilot = load_pilot_module()
        base = {
            "turn_completed": True, "errors": [], "invalid_jsonl_lines": [],
            "tools": [], "tool_failures": [],
        }
        denied = dict(base, tool_failures=[{
            "type": "mcp_tool_call", "tool": "fixture_search", "status": "failed",
            "error": {"message": "MCP tool call requires approval"},
        }])
        infrastructure = pilot.classify_run(0, denied, True, True, {"item_id": "skill"}, {},
                                            ("fixture_search", "fixture_read"))
        self.assertTrue(infrastructure["process_completed"])
        self.assertTrue(infrastructure["model_turn_completed"])
        self.assertTrue(infrastructure["infrastructure_failure"])
        self.assertFalse(infrastructure["research_task_completed"])
        self.assertTrue(pilot.should_stop_after_run(infrastructure))

        behavior = pilot.classify_run(0, base, True, True, None, {},
                                      ("fixture_search", "fixture_read"))
        self.assertFalse(behavior["infrastructure_failure"])
        self.assertTrue(behavior["model_behavior_failure"])
        self.assertFalse(behavior["research_task_completed"])
        self.assertFalse(pilot.should_stop_after_run(behavior))

        with tempfile.TemporaryDirectory(prefix="temporary-auth-") as temporary:
            directory = Path(temporary)
            source = directory / "source-auth.json"
            target = directory / "runtime/auth.json"
            source.write_text("temporary credential fixture", encoding="utf-8")
            target.parent.mkdir()

            def fail_after_copy():
                self.assertTrue(target.is_file())
                raise RuntimeError("simulated Python exception")

            with self.assertRaisesRegex(RuntimeError, "simulated Python exception"):
                pilot.run_with_temporary_auth(source, target, fail_after_copy)
            self.assertFalse(target.exists())

    def test_skill_read_requires_exact_local_command_output(self):
        pilot = load_pilot_module()
        content = "---\nname: product-competitive-research\n---\nbody\n"
        evidence = {"tools": [{
            "id": "item_1", "type": "command_execution", "status": "completed",
            "command": "cat .agents/skills/product-competitive-research/SKILL.md",
            "aggregated_output": content,
        }]}
        proof = pilot.local_file_read_evidence(
            evidence, ".agents/skills/product-competitive-research/SKILL.md", content)
        self.assertEqual(proof["item_id"], "item_1")

    def test_prepare_smoke_and_plan_only(self):
        with tempfile.TemporaryDirectory(prefix="fixture-harness-") as temporary:
            prep = self.prepare(temporary)
            report = prep / "smoke/report.json"
            subprocess.run([sys.executable, str(SMOKE), "--prep-root", str(prep),
                            "--report", str(report)], cwd=ROOT, check=True,
                           capture_output=True, text=True)
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "pass")
            plan_output = prep / "plan-only.json"
            fresh_runs = Path(temporary) / "fresh-runs"
            result = subprocess.run([sys.executable, str(PILOT), "--prep-root", str(prep),
                                     "--run-root", str(fresh_runs),
                                     "--plan-output", str(plan_output)],
                                    cwd=ROOT, check=True, capture_output=True, text=True)
            self.assertIn("PLAN ONLY", result.stdout)
            rendered = json.loads(plan_output.read_text(encoding="utf-8"))
            self.assertFalse(rendered["model_calls_executed"])
            self.assertEqual([run["version"] for run in rendered["runs"]], ["v1", "v1_1"])
            self.assertIn(str((fresh_runs / "v1/workspace").resolve()),
                          rendered["runs"][0]["command"])
            configs = [run["config"] for run in rendered["runs"]]
            self.assertIn("web_search", " ".join(rendered["runs"][0]["command"]))
            self.assertIn('$product-competitive-research', rendered["runs"][0]["prompt"])
            self.assertIn('enabled_tools = ["fixture_search", "fixture_read"]', configs[0])
            self.assertIn('default_tools_approval_mode = "approve"', configs[0])
            self.assertIn('[mcp_servers.fixture_eval.tools.fixture_search]', configs[0])
            self.assertEqual(configs[0].split("FIXTURE_TRACE_PATH")[0],
                             configs[1].split("FIXTURE_TRACE_PATH")[0])

            pilot = load_pilot_module()
            workspace = Path(temporary) / "skill-workspace"
            workspace.mkdir()
            skill = prep / "snapshots/v1/product-competitive-research"
            link = pilot.install_discoverable_skill(workspace, skill)
            self.assertEqual(link, workspace / ".agents/skills/product-competitive-research")
            self.assertEqual(link.resolve(), skill.resolve())
            sandbox_read = subprocess.run(
                ["codex", "sandbox", "-P", ":read-only", "--", "cat", str(link / "SKILL.md")],
                cwd=workspace, capture_output=True, text=True)
            self.assertEqual(sandbox_read.returncode, 0, sandbox_read.stderr)
            self.assertIn("name: product-competitive-research", sandbox_read.stdout)

            model_smoke_root = Path(temporary) / "model-smoke-plan"
            smoke_plan = subprocess.run([
                sys.executable, str(MODEL_SMOKE), "--prep-root", str(prep),
                "--output-root", str(model_smoke_root), "--version", "v1",
            ], cwd=ROOT, check=True, capture_output=True, text=True)
            self.assertIn("PLAN ONLY", smoke_plan.stdout)
            smoke_data = json.loads((model_smoke_root / "smoke-plan.json").read_text())
            self.assertFalse(smoke_data["model_calls_executed"])
            self.assertEqual(smoke_data["explicit_confirmation_required"], "RUN_ONE_MODEL_SMOKE")

    def test_evidence_audit_plan_is_workspace_write_but_network_disabled(self):
        with tempfile.TemporaryDirectory(prefix="evidence-audit-plan-") as temporary:
            prep = self.prepare(temporary)
            plan_output = Path(temporary) / "audit-plan.json"
            result = subprocess.run([
                sys.executable, str(PILOT), "--prep-root", str(prep),
                "--run-root", str(Path(temporary) / "runs"),
                "--mode", "evidence-audit", "--plan-output", str(plan_output),
            ], cwd=ROOT, check=True, capture_output=True, text=True)
            self.assertIn("PLAN ONLY", result.stdout)
            plan = json.loads(plan_output.read_text(encoding="utf-8"))
            self.assertFalse(plan["model_calls_executed"])
            for run in plan["runs"]:
                command = run["command"]
                self.assertIn("workspace-write", command)
                self.assertIn("sandbox_workspace_write.network_access=false", command)
                self.assertNotIn("--add-dir", command)
                self.assertIn("report.md", run["prompt"])
                self.assertIn("research_contract.json", run["prompt"])
                self.assertIn("validate_research.py", run["prompt"])

    def test_evidence_audit_execution_requires_explicit_confirmation(self):
        with tempfile.TemporaryDirectory(prefix="evidence-audit-confirm-") as temporary:
            prep = self.prepare(temporary)
            run_root = Path(temporary) / "must-not-be-created"
            result = subprocess.run([
                sys.executable, str(PILOT), "--prep-root", str(prep),
                "--run-root", str(run_root), "--mode", "evidence-audit",
                "--execute-model-calls",
            ], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("require --confirm-model-calls RUN_EVIDENCE_AUDIT", result.stderr)
            self.assertFalse(run_root.exists())

    def test_plan_and_audit_outputs_refuse_overwrite(self):
        with tempfile.TemporaryDirectory(prefix="evidence-audit-overwrite-") as temporary:
            prep = self.prepare(temporary)
            plan_output = Path(temporary) / "existing-plan.json"
            plan_output.write_text("keep", encoding="utf-8")
            result = subprocess.run([
                sys.executable, str(PILOT), "--prep-root", str(prep),
                "--mode", "evidence-audit", "--plan-output", str(plan_output),
            ], cwd=ROOT, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(plan_output.read_text(encoding="utf-8"), "keep")

    def test_fixture_and_skill_hash_verification_detects_changes(self):
        pilot = load_pilot_module()
        with tempfile.TemporaryDirectory(prefix="evidence-audit-hash-") as temporary:
            prep = self.prepare(temporary)
            pilot.verify_fixture_snapshot(prep)
            skill = prep / "snapshots/v1/product-competitive-research"
            manifest = prep / "snapshots/v1/v1-manifest.json"
            pilot.verify_snapshot(skill, manifest)
            fixture = prep / "fixture-repo/tests/fixtures/case-02/figma-price.html"
            fixture.chmod(0o600)
            fixture.write_text(fixture.read_text(encoding="utf-8") + "\nchanged", encoding="utf-8")
            with self.assertRaises(RuntimeError):
                pilot.verify_fixture_snapshot(prep)

    def test_output_inventory_detects_temporary_unexpected_and_symlink_files(self):
        pilot = load_pilot_module()
        with tempfile.TemporaryDirectory(prefix="evidence-audit-inventory-") as temporary:
            workspace = Path(temporary)
            (workspace / "report.md").write_text("report", encoding="utf-8")
            (workspace / "research_contract.json").write_text("{}", encoding="utf-8")
            (workspace / ".scratch").write_text("temporary", encoding="utf-8")
            (workspace / "nested").mkdir()
            (workspace / "nested/extra.txt").write_text("unexpected", encoding="utf-8")
            (workspace / "linked-output").symlink_to(workspace / "report.md")
            inventory = pilot.output_inventory(workspace)
            self.assertEqual(inventory["temporary_files"], [".scratch"])
            self.assertEqual(inventory["unexpected_files"],
                             ["linked-output", "nested/extra.txt"])
            self.assertTrue(all(item["regular_file"]
                                for item in inventory["deliverables"].values()))

    @unittest.skipUnless(sys.platform == "darwin", "Codex sandbox profiles are macOS-specific")
    def test_workspace_sandbox_writes_workspace_but_protects_skill_and_network(self):
        with tempfile.TemporaryDirectory(prefix="evidence-audit-sandbox-") as temporary:
            workspace = Path(temporary)
            skill = workspace / ".agents/skills/test/SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("immutable\n", encoding="utf-8")
            write = subprocess.run(
                ["codex", "sandbox", "-P", ":workspace", "--", "/bin/sh", "-c",
                 "printf ok > report.md"], cwd=workspace, capture_output=True, text=True)
            self.assertEqual(write.returncode, 0, write.stderr)
            self.assertEqual((workspace / "report.md").read_text(encoding="utf-8"), "ok")
            mutate = subprocess.run(
                ["codex", "sandbox", "-P", ":workspace", "--", "/bin/sh", "-c",
                 "printf bad >> .agents/skills/test/SKILL.md"], cwd=workspace,
                capture_output=True, text=True)
            self.assertNotEqual(mutate.returncode, 0)
            self.assertEqual(skill.read_text(encoding="utf-8"), "immutable\n")
            network = subprocess.run(
                ["codex", "sandbox", "-P", ":workspace", "--", sys.executable, "-c",
                 "import socket; socket.create_connection(('example.com', 80), 1)"],
                cwd=workspace, capture_output=True, text=True)
            self.assertNotEqual(network.returncode, 0)


if __name__ == "__main__":
    unittest.main()
