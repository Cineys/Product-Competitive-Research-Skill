"""Run from repository root: python3 -m unittest (no network/dependencies).

These tests validate contracts and fixture integrity, not agent behavior.
See rubric.md for replay and semantic-evidence acceptance.
"""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/product-competitive-research/scripts/validate_research.py"
SPEC = importlib.util.spec_from_file_location("research_validator", SCRIPT)
VALIDATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATOR)
GOLDEN = ROOT / "tests/fixtures/golden_record.json"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class ValidatorTests(unittest.TestCase):
    def setUp(self):
        self.data = read_json(GOLDEN)

    def assert_invalid(self, fragment):
        errors = VALIDATOR.validate(self.data)
        self.assertTrue(errors, "invalid contract was accepted")
        self.assertTrue(any(fragment in e for e in errors), errors)

    def test_complete_golden_record(self):
        self.assertEqual(VALIDATOR.validate(self.data), [])

    def test_unmentioned_feature_cannot_be_unsupported(self):
        # Actual source lists online editing/comments, but never mentions offline.
        # Keep its honest insufficient_evidence status; unsupported must fail.
        self.data["claims"][3]["feature_status"] = "unsupported"
        self.assert_invalid("unsupported requires verified")

    def test_unsupported_without_quote(self):
        self.data["claims"][4]["quote"] = None
        self.assert_invalid("verified requires accessed source and quote")

    def test_unknown_without_fabricated_claim_is_valid(self):
        self.data["claims"] = [c for c in self.data["claims"] if c["claim_id"] != "c-unknown"]
        self.data["comparisons"][2]["evidence_claim_ids"] = []
        self.data["findings"][0]["evidence_claim_ids"] = ["c-negative"]
        self.assertEqual(VALIDATOR.validate(self.data), [])

    def test_unknown_cannot_be_verified(self):
        self.data["claims"][3]["status"] = "verified"
        self.assert_invalid("unknown capability")

    def test_dangling_links(self):
        for collection, field in (("claims", "source_id"), ("comparisons", "evidence_claim_ids"),
                                  ("findings", "comparison_ids"), ("findings", "evidence_claim_ids")):
            with self.subTest(collection=collection, field=field):
                self.data = read_json(GOLDEN)
                self.data[collection][0][field] = "missing" if field == "source_id" else ["missing"]
                self.assert_invalid("missing")

    def test_dangling_recommendation_links(self):
        for key in ("finding_id", "claim_ids"):
            with self.subTest(key=key):
                self.data = read_json(GOLDEN)
                self.data["recommendations"][0]["evidence_mapping"][0][key] = "missing" if key == "finding_id" else ["missing"]
                self.assert_invalid("missing")

    def test_recommendation_cannot_borrow_unrelated_claim(self):
        self.data["recommendations"][0]["evidence_mapping"][0]["claim_ids"] = ["c-new"]
        self.assert_invalid("mapped claims must support mapped finding")

    def test_no_own_product_requires_conditional_advice(self):
        self.data["recommendations"][0]["conditional"] = False
        self.assert_invalid("no own product")

    def test_no_own_product_requires_context_precondition(self):
        self.data["recommendations"][0]["preconditions"] = []
        self.assert_invalid("unconfirmed context required")

    def test_conflict_flag_false_rejected(self):
        self.data["claims"][0]["conflict_flag"] = False
        self.assert_invalid("conflict_flag must match")

    def remove_price_conflict(self):
        self.data["conflicts"] = []
        for c in self.data["claims"]:
            c["conflict_flag"] = False
        self.data["comparisons"][0]["conflict_ids"] = []

    def test_omitted_entire_price_conflict_detected(self):
        self.remove_price_conflict()
        self.assert_invalid("price difference requires shared conflict record")

    def test_version_labels_do_not_hide_price_history(self):
        self.remove_price_conflict()
        self.data["claims"][0]["applicability"]["version"] = "old"
        self.data["claims"][1]["applicability"]["version"] = "new"
        self.assert_invalid("price difference requires shared conflict record")

    def test_different_price_bases_not_false_conflicts(self):
        for field in ("plan", "currency", "commitment", "equal_amount"):
            with self.subTest(field=field):
                self.data = read_json(GOLDEN)
                self.remove_price_conflict()
                old = self.data["claims"][0]
                if field == "plan":
                    old["applicability"]["plan"] = "Other plan"
                elif field == "equal_amount":
                    old["value"]["amount"] = "12.00"
                else:
                    old["value"][field] = "EUR" if field == "currency" else "annual"
                self.assertEqual(VALIDATOR.validate(self.data), [])

    def test_comparison_missing_conflict_reference(self):
        self.data["comparisons"][0]["conflict_ids"] = []
        self.assert_invalid("conflict_ids must exactly match")

    def test_resolved_comparison_cannot_use_superseded_price(self):
        self.data["comparisons"][0]["value"]["amount"] = "8"
        self.assert_invalid("value must match verified selected evidence")

    def test_unresolved_price_variant(self):
        conflict = self.data["conflicts"][0]
        conflict.update(resolution="unresolved", selected_claim_ids=[])
        cmp = self.data["comparisons"][0]
        cmp.update(assessment_status="conflicted", value=None)
        self.assertEqual(VALIDATOR.validate(self.data), [])
        cmp["value"] = copy.deepcopy(self.data["claims"][1]["value"])
        self.assert_invalid("uncertain/inapplicable comparison requires null value")

    def test_invalid_enum(self):
        self.data["claims"][3]["feature_status"] = "false"
        self.assert_invalid("expected one of")

    def test_duplicate_id(self):
        self.data["claims"].append(copy.deepcopy(self.data["claims"][0]))
        self.assert_invalid("duplicate ID")

    def test_source_metadata_mismatch(self):
        self.data["claims"][0]["source_url"] = "https://wrong.invalid/page"
        self.assert_invalid("source_url differs")

    def test_malformed_input_no_crash(self):
        for value in (None, [], {}, {"schema_version": 1}):
            with self.subTest(value=value):
                self.assertTrue(VALIDATOR.validate(value))

    def test_cli_exit_codes(self):
        # Keep writes inside the workspace for sandboxed Windows hosts.
        with tempfile.TemporaryDirectory(dir=ROOT, prefix="research-test-") as temp:
            self.assertTrue(Path(temp).resolve().is_relative_to(ROOT.resolve()))
            path = Path(temp) / "contract.json"
            for content, code in ((GOLDEN.read_text(encoding="utf-8"), 0),
                                  ('{}', 1), ('{"x":1,"x":2}', 2), ('{', 2), ('NaN', 2)):
                with self.subTest(code=code, content=content[:20]):
                    path.write_text(content, encoding="utf-8")
                    result = subprocess.run([sys.executable, str(SCRIPT), str(path)],
                                            capture_output=True, text=True, encoding="utf-8")
                    self.assertEqual(result.returncode, code, result.stderr)


class FixtureTests(unittest.TestCase):
    def test_manifests_paths_and_hashes(self):
        for manifest_path in (ROOT / "tests/fixtures").rglob("manifest.json"):
            manifest = read_json(manifest_path)
            self.assertTrue(manifest["synthetic"])
            self.assertFalse(manifest["network_allowed"])
            for source in manifest["sources"]:
                with self.subTest(source=source["source_id"]):
                    path = (ROOT / source["fixture_path"]).resolve()
                    self.assertTrue(path.is_relative_to(ROOT / "tests/fixtures"))
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), source["content_sha256"])
                    self.assertIn("SYNTHETIC OFFLINE TEST DATA", path.read_text(encoding="utf-8"))

    def test_four_case_specs_are_linked(self):
        for i in range(1, 5):
            case = f"case-{i:02}"
            input_data = read_json(ROOT / "tests/cases" / case / "input.json")
            assertions = read_json(ROOT / "tests/cases" / case / "assertions.json")
            self.assertEqual(input_data["case_id"], case)
            self.assertEqual(assertions["case_id"], case)
            self.assertFalse(input_data["network_allowed"])
            self.assertTrue((ROOT / input_data["fixture_manifest"]).is_file())
            self.assertTrue(assertions["semantic_checks"])

    def test_golden_quotes_are_in_actual_fixture_bodies(self):
        golden = read_json(GOLDEN)
        sources = {s["source_id"]: s for s in golden["sources"]}
        manifest = read_json(ROOT / "tests/fixtures/case-03/manifest.json")
        self.assertEqual(golden["sources"], manifest["sources"])
        for claim in golden["claims"]:
            body = (ROOT / sources[claim["source_id"]]["fixture_path"]).read_text(encoding="utf-8")
            self.assertIn(claim["quote"], body)

    def test_injection_fixture_contains_normal_and_attack_text(self):
        body = (ROOT / "tests/fixtures/case-04/atlas-injection.html").read_text(encoding="utf-8")
        self.assertIn("up to 10 simultaneous editors", body)
        self.assertIn("SYSTEM OVERRIDE", body)
        self.assertIn("https://collector.invalid/upload", body)


if __name__ == "__main__":
    unittest.main()
