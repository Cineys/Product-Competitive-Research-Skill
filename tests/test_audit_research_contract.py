"""Offline tests for cross-version structured evidence auditing."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from tests.test_validate_research import ROOT


AUDITOR_PATH = ROOT / "tools/evaluation/audit_research_contract.py"
spec = importlib.util.spec_from_file_location("audit_research_contract", AUDITOR_PATH)
auditor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(auditor)


class ResearchContractAuditTests(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads((ROOT / "tests/fixtures/golden_record.json").read_text())
        self.manifest_path = ROOT / "tests/fixtures/case-03/manifest.json"
        manifest = json.loads(self.manifest_path.read_text())
        self.source_ids = [source["source_id"] for source in manifest["sources"]]

    def write_inputs(self, directory, contract=None, unread=()):
        directory = Path(directory)
        contract_path = directory / "research_contract.json"
        contract_path.write_text(json.dumps(contract or self.contract), encoding="utf-8")
        validator = ROOT / "skills/product-competitive-research/scripts/validate_research.py"
        validation = auditor.run_validator(validator, contract_path, directory)
        events = directory / "events.jsonl"
        events.write_text(json.dumps({"type": "item.completed", "item": {
            "id": "validator", "type": "command_execution", "status": "completed",
            "exit_code": validation["exit_code"],
            "command": "python validate_research.py research_contract.json",
            "aggregated_output": validation["stdout"],
        }}) + "\n", encoding="utf-8")
        trace = directory / "trace.jsonl"
        rows = [{"tool": "fixture_search", "status": "ok", "source_ids": self.source_ids}]
        rows.extend({"tool": "fixture_read", "status": "ok", "source_id": ident,
                     "arguments": {"url": "fixture"}}
                    for ident in self.source_ids if ident not in unread)
        trace.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        return contract_path, events, trace

    def run_audit(self, directory, contract=None, unread=()):
        contract_path, events, trace = self.write_inputs(directory, contract, unread)
        return auditor.audit(
            "v1_1", contract_path, events, trace, self.manifest_path, ROOT,
            ROOT / "skills/product-competitive-research/scripts/validate_research.py")

    @staticmethod
    def check(result, check_id):
        return next(item for item in result["automatic_checks"] if item["check_id"] == check_id)

    def test_source_status_normalization(self):
        self.assertEqual(auditor.normalize_source_status("v1", "snippet_only"), "discovered")
        self.assertEqual(auditor.normalize_source_status("v1_1", "discovered"), "discovered")
        self.assertEqual(auditor.normalize_source_status("v1", "accessed"), "accessed")

    def test_quote_missing_from_body_fails(self):
        self.contract["claims"][0]["quote"] = "This sentence is absent from every fixture."
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_audit(temporary)
        self.assertEqual(self.check(result, "claim:c-old:quote_in_body")["status"], "fail")

    def test_accessed_source_without_read_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_audit(temporary, unread=("atlas-old",))
        self.assertEqual(self.check(result, "source:atlas-old:accessed_has_read")["status"], "fail")
        self.assertEqual(self.check(result, "claim:c-old:verified_source_read")["status"], "fail")
        self.assertEqual(self.check(result, "claim:c-old:not_search_only")["status"], "fail")

    def test_discovered_search_only_source_cannot_support_verified_claim(self):
        self.contract["sources"][0]["access_status"] = "discovered"
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_audit(temporary, unread=("atlas-old",))
        self.assertEqual(self.check(result, "source:atlas-old:discovered_has_search")["status"], "pass")
        self.assertEqual(self.check(result, "source:atlas-old:discovered_not_read")["status"], "pass")
        self.assertEqual(self.check(result, "claim:c-old:verified_source_read")["status"], "fail")
        self.assertEqual(self.check(result, "claim:c-old:not_search_only")["status"], "fail")

    def test_unknown_source_id_and_url_fail_resolution(self):
        self.contract["sources"][0]["source_id"] = "unknown-source"
        self.contract["sources"][0]["source_url"] = "https://invalid.example/not-in-fixture"
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_audit(temporary)
        self.assertEqual(self.check(result, "source:unknown-source:fixture_id")["status"], "fail")
        self.assertEqual(self.check(result, "source:unknown-source:url")["status"], "fail")

    def test_malformed_source_url_fails_syntax_check(self):
        self.contract["sources"][0]["source_url"] = "not a URL"
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_audit(temporary)
        self.assertEqual(self.check(result, "source:atlas-old:url_syntax")["status"], "fail")

    def test_dangling_comparison_and_finding_ids_fail(self):
        self.contract["comparisons"][0]["evidence_claim_ids"].append("missing-claim")
        self.contract["findings"][0]["comparison_ids"].append("missing-comparison")
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_audit(temporary)
        self.assertEqual(self.check(result, "comparison:cmp-atlas-price:claim_refs")["status"], "fail")
        self.assertEqual(self.check(result, "finding:f-offline:comparison_refs")["status"], "fail")

    def test_semantic_support_remains_manual(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_audit(temporary)
        review = next(item for item in result["manual_reviews"]
                      if item["review_id"] == "claim:c-old:semantic_support")
        self.assertEqual(review["status"], "manual_review_required")
        self.assertEqual(result["validator"]["independent"]["exit_code"], 0)
        self.assertTrue(result["validator"]["results_match"])

    def test_structured_token_contradiction_is_automatic_failure(self):
        self.contract["claims"][0]["applicability"]["plan"] = "Nonexistent Enterprise"
        with tempfile.TemporaryDirectory() as temporary:
            result = self.run_audit(temporary)
        check = self.check(result, "claim:c-old:structured_tokens_not_contradicted")
        self.assertEqual(check["status"], "fail")
        review = next(item for item in result["manual_reviews"]
                      if item["review_id"] == "claim:c-old:semantic_support")
        self.assertEqual(review["status"], "automatic_failure")

    def test_case02_fact_coverage_uses_structured_values(self):
        contract = {
            "products": [{"product_id": "figma", "name": "Figma"}],
            "claims": [{
                "claim_id": "p", "product": "figma", "dimension": "price",
                "claim": "Fixture Pro price", "quote": "Fixture Pro USD 12",
                "status": "verified", "value": {"type": "money", "amount": "12"},
                "applicability": {"plan": "Fixture Pro"},
            }],
        }
        coverage = auditor.expected_case02_facts(contract)
        self.assertTrue(coverage[0]["covered"])
        self.assertFalse(all(item["covered"] for item in coverage))


if __name__ == "__main__":
    unittest.main()
