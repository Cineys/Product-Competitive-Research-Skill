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


def load_pilot_module():
    spec = importlib.util.spec_from_file_location("case02_v1_v11_pilot", PILOT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FixtureHarnessTests(unittest.TestCase):
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

    def test_prepare_smoke_and_plan_only(self):
        with tempfile.TemporaryDirectory(prefix="fixture-harness-") as temporary:
            prep = Path(temporary) / "prep"
            subprocess.run([sys.executable, str(PREPARE), "--output", str(prep)],
                           cwd=ROOT, check=True, capture_output=True, text=True)
            report = prep / "smoke/report.json"
            subprocess.run([sys.executable, str(SMOKE), "--prep-root", str(prep),
                            "--report", str(report)], cwd=ROOT, check=True,
                           capture_output=True, text=True)
            data = json.loads(report.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "pass")
            result = subprocess.run([sys.executable, str(PILOT), "--prep-root", str(prep)],
                                    cwd=ROOT, check=True, capture_output=True, text=True)
            self.assertIn("PLAN ONLY", result.stdout)
            rendered = json.loads((prep / "pilot-rendered-plan.json").read_text(encoding="utf-8"))
            self.assertFalse(rendered["model_calls_executed"])
            self.assertEqual([run["version"] for run in rendered["runs"]], ["v1", "v1_1"])
            configs = [run["config"] for run in rendered["runs"]]
            self.assertIn("web_search", " ".join(rendered["runs"][0]["command"]))
            self.assertEqual(configs[0].split("FIXTURE_TRACE_PATH")[0],
                             configs[1].split("FIXTURE_TRACE_PATH")[0])


if __name__ == "__main__":
    unittest.main()
