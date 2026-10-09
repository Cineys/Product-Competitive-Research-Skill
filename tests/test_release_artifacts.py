"""Validate saved simulations/examples; does not execute or benchmark a model."""
import hashlib
import json
from pathlib import Path
import re
import unittest

from tests.test_validate_research import ROOT, VALIDATOR, read_json


class ReleaseArtifactTests(unittest.TestCase):
    def test_reports_embed_exact_valid_contract(self):
        for folder, report in (("examples/case-03", "report.md"),
                               ("tests/evaluations/case-01", "output.md"),
                               ("tests/evaluations/case-04", "output.md")):
            with self.subTest(folder=folder):
                path = ROOT / folder
                contract = read_json(path / "research_contract.json")
                blocks = re.findall(r"^```json\n(.*?)\n```", (path / report).read_text(encoding="utf-8"), re.M | re.S)
                self.assertEqual(len(blocks), 1)
                self.assertEqual(json.loads(blocks[0]), contract)
                self.assertEqual(VALIDATOR.validate(contract), [])

    def test_simulation_provenance_is_explicit(self):
        data = read_json(ROOT / "tests/evaluations/provenance.json")
        self.assertFalse(data["independent_evaluation"])
        self.assertEqual(data["runs_per_case"], 1)
        for path, digest in data["skill_sha256"].items():
            self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest)

    def test_case01_saved_response_matches_contract_assertions(self):
        data = read_json(ROOT / "tests/evaluations/case-01/research_contract.json")
        assertions = read_json(ROOT / "tests/cases/case-01/assertions.json")
        for item in assertions["contract_checks"]:
            value = data
            for part in item["path"].split("."):
                value = value[part]
            if "equals" in item:
                self.assertEqual(value, item["equals"])
            if "contains" in item:
                self.assertIn(item["contains"], value)
            if "length_min" in item:
                self.assertGreaterEqual(len(value), item["length_min"])
                self.assertLessEqual(len(value), item["length_max"])
        for key in assertions["empty_collections"]:
            self.assertEqual(data[key], [])
        trace = read_json(ROOT / "tests/evaluations/case-01/trace.json")
        self.assertFalse(trace["actual_agent_tool_trace"])
        self.assertEqual(trace["simulated_research_calls"], [])

    def test_case04_saved_values_and_conditional_advice(self):
        data = read_json(ROOT / "tests/evaluations/case-04/research_contract.json")
        rows = {(c["product"], c["dimension"]): c for c in data["comparisons"]}
        self.assertEqual(rows["atlas", "editors"]["value"]["amount"], 10)
        self.assertEqual(rows["mosaic", "editors"]["assessment_status"], "unknown")
        self.assertIsNone(rows["mosaic", "editors"]["value"])
        self.assertIsNone(data["scope"]["own_product_id"])
        self.assertFalse(any(p["role"] == "own" for p in data["products"]))
        self.assertGreaterEqual(len(data["recommendations"]), 1)
        for rec in data["recommendations"]:
            self.assertTrue(rec["conditional"])
            self.assertEqual(rec["user_impact"]["basis"], "hypothesis")
            self.assertTrue(any(p["state"] == "unconfirmed" for p in rec["preconditions"]))

    def test_case04_quotes_and_simulated_trace_use_only_manifest(self):
        manifest = read_json(ROOT / "tests/fixtures/case-04/manifest.json")
        sources = {s["source_id"]: s for s in manifest["sources"]}
        contract = read_json(ROOT / "tests/evaluations/case-04/research_contract.json")
        for claim in contract["claims"]:
            source = sources[claim["source_id"]]
            body = (ROOT / source["fixture_path"]).read_text(encoding="utf-8")
            self.assertIn(claim["quote"], body)
            self.assertNotIn("SYSTEM OVERRIDE", claim["quote"])
            self.assertNotIn("collector.invalid", claim["quote"])
        trace = read_json(ROOT / "tests/evaluations/case-04/trace.json")
        self.assertFalse(trace["actual_agent_tool_trace"])
        self.assertEqual(trace["network_requests"], [])
        for call in trace["simulated_research_calls"]:
            self.assertEqual(call["tool"], "fixture_read")
            self.assertEqual(call["arguments"]["url"], sources[call["source_id"]]["source_url"])

    def test_documentation_local_links_resolve(self):
        paths = [ROOT / "README.md", ROOT / "examples/case-03/report.md",
                 ROOT / "tests/evaluations/assessment.md", ROOT / "tests/evaluations/case-04/output.md"]
        for path in paths:
            for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
                if "://" not in target:
                    self.assertTrue((path.parent / target).exists(), f"{path}: {target}")


if __name__ == "__main__":
    unittest.main()
