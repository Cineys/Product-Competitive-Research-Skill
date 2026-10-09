#!/usr/bin/env python3
"""Validate contract 1.0.0 with Python 3.10+ standard library only.

No network or writes. Exit 0: structural checks pass (semantic review remains);
1: invalid contract; 2: input/CLI error. Import validate(data) for diagnostics.
"""
import argparse
from datetime import datetime
from decimal import Decimal
from itertools import combinations
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit


def enum(values):
    return ("enum", values.split())


def nullable(spec):
    return ("nullable", spec)


def array(spec):
    return ("array", spec)


TEXT = "text"
STRINGS = array(TEXT)
FEATURE = enum("supported partially_supported unsupported unknown not_applicable")
SOURCE_TYPE = enum("official_doc pricing_page changelog marketing_claim user_review third_party_report")
STATE = enum("confirmed unconfirmed rejected")
TIME = {"accessed_at": "time", "published_at": nullable("time"),
        "effective_from": nullable("time"), "effective_to": nullable("time")}
VALUE = ("value", None)
SCHEMA = {
    "schema_version": enum("1.0.0"), "research_id": TEXT,
    "phase": enum("clarification_required ready researching completed completed_with_gaps"),
    "metadata": {"created_at": "time", "as_of": "time", "language": TEXT,
                 "source_mode": enum("live provided fixture mixed")},
    "scope": {"user_request": TEXT, "objective": nullable(TEXT),
              "decision_context": nullable(TEXT), "target_users": nullable(TEXT),
              "own_product_id": nullable(TEXT), "product_ids": STRINGS,
              "dimension_ids": STRINGS, "inclusions": STRINGS, "exclusions": STRINGS,
              "assumptions": array({"assumption_id": TEXT, "statement": TEXT,
                  "origin": enum("user agent"), "state": STATE, "impact": TEXT, "blocking": "bool"}),
              "budget": {"max_source_reads": "positive_int"}},
    "clarification": {"required": "bool", "reason_codes": array(enum(
        "ambiguous_objective ambiguous_product_identity missing_comparison_boundary")),
        "questions": array({"question_id": TEXT, "text": TEXT, "resolves": STRINGS, "blocking": "bool"})},
    "products": array({"product_id": TEXT, "name": TEXT, "official_url": nullable("url"),
                       "role": enum("own competitor reference"),
                       "context_origin": enum("user public_source fixture")}),
    "dimensions": array({"dimension_id": TEXT, "name": TEXT,
                         "kind": enum("capability price limit positioning"),
                         "definition": TEXT, "comparison_basis": TEXT, "unit": nullable(TEXT)}),
    "sources": array({"source_id": TEXT, "source_url": "url", "title": TEXT,
                      "source_type": SOURCE_TYPE, "access_status": enum("accessed snippet_only inaccessible"),
                      "timestamp": TIME, "locator": nullable(TEXT),
                      "fixture_path": nullable(TEXT), "content_sha256": nullable("sha256")}),
    "claims": array({"claim_id": TEXT, "product": TEXT, "dimension": TEXT, "claim": TEXT,
                     "source_id": nullable(TEXT), "source_url": nullable("url"),
                     "source_type": nullable(SOURCE_TYPE), "quote": nullable(TEXT),
                     "timestamp": nullable(TIME),
                     "status": enum("verified unverified insufficient_evidence"),
                     "feature_status": nullable(FEATURE), "value": nullable(VALUE),
                     "applicability": {"plan": nullable(TEXT), "region": nullable(TEXT),
                         "version": nullable(TEXT), "billing_period": nullable(TEXT), "conditions": STRINGS},
                     "conflict_flag": "bool"}),
    "conflicts": array({"conflict_id": TEXT, "claim_ids": STRINGS, "reason": TEXT,
                        "resolution": enum("unresolved resolved_by_effective_date resolved_by_scope resolved_by_correction"),
                        "selected_claim_ids": STRINGS, "rationale": TEXT}),
    "comparisons": array({"comparison_id": TEXT, "product": TEXT, "dimension": TEXT,
                          "feature_status": nullable(FEATURE), "value": nullable(VALUE),
                          "assessment_status": enum("established unknown conflicted not_applicable"),
                          "evidence_claim_ids": STRINGS, "conflict_ids": STRINGS, "rationale": TEXT}),
    "findings": array({"finding_id": TEXT, "statement": TEXT, "evidence_claim_ids": STRINGS,
                       "comparison_ids": STRINGS, "certainty": enum("established qualified unresolved")}),
    "recommendations": array({"recommendation_id": TEXT,
        "evidence_mapping": array({"finding_id": TEXT, "claim_ids": STRINGS, "supports": TEXT}),
        "user_impact": {"statement": TEXT, "basis": enum("evidence hypothesis"), "claim_ids": STRINGS},
        "action": TEXT, "preconditions": array({"statement": TEXT, "state": STATE,
                                                "assumption_id": nullable(TEXT)}),
        "conditional": "bool", "validation": {"method": TEXT, "metric": TEXT,
            "success_criterion": TEXT, "criterion_status": enum("to_be_defined proposed confirmed")}}),
    "limitations": STRINGS,
}


def shape(value, spec, path, errors):
    def fail(message):
        errors.append(f"{path}: {message}")
    if isinstance(spec, dict):
        if not isinstance(value, dict):
            fail("expected object")
            return
        for key in sorted(set(spec) - set(value)):
            fail(f"missing field {key}")
        for key in sorted(set(value) - set(spec)):
            fail(f"unexpected field {key}")
        for key in spec.keys() & value.keys():
            shape(value[key], spec[key], f"{path}.{key}", errors)
        return
    if isinstance(spec, tuple):
        kind, arg = spec
        if kind == "nullable":
            if value is not None:
                shape(value, arg, path, errors)
        elif kind == "array":
            if not isinstance(value, list):
                fail("expected array")
            else:
                for i, item in enumerate(value):
                    shape(item, arg, f"{path}[{i}]", errors)
        elif kind == "enum":
            if not isinstance(value, str) or value not in arg:
                fail(f"expected one of {arg}")
        elif kind == "value":
            variants = {
                "money": {"type": enum("money"), "amount": "decimal", "currency": "currency",
                          "per": TEXT, "billing_period": TEXT, "commitment": TEXT},
                "limit": {"type": enum("limit"), "amount": "limit", "unit": TEXT},
                "text": {"type": enum("text"), "text": TEXT},
            }
            tag = value.get("type") if isinstance(value, dict) else None
            if not isinstance(tag, str) or tag not in variants:
                fail("expected money, limit or text value object")
            else:
                shape(value, variants[tag], path, errors)
        return
    if spec == "bool":
        valid = type(value) is bool
    elif spec == "positive_int":
        valid = type(value) is int and value > 0
    elif spec == "limit":
        valid = (type(value) is int and value >= 0) or value == "unlimited"
    else:
        valid = isinstance(value, str) and bool(value.strip())
        if valid and spec in ("sha256", "decimal", "currency", "time"):
            patterns = {"sha256": r"[0-9a-fA-F]{64}", "decimal": r"\d+(?:\.\d+)?",
                        "currency": r"[A-Z]{3}",
                        "time": r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})"}
            valid = bool(re.fullmatch(patterns[spec], value))
            if valid and spec == "time":
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError:
                    valid = False
        if valid and spec == "url":
            try:
                parsed = urlsplit(value)
                valid = parsed.scheme in ("https", "http") and bool(parsed.hostname) and not any(c.isspace() for c in value)
            except ValueError:
                valid = False
    if not valid:
        fail(f"invalid {spec}")


def validate(data):
    """Return deterministic errors; does not validate the truth of prose."""
    errors = []
    shape(data, SCHEMA, "$", errors)
    if errors:
        return sorted(errors)

    def check(condition, path, message):
        if not condition:
            errors.append(f"{path}: {message}")

    def index(items, key, path):
        result = {}
        for item in items:
            ident = item[key]
            check(ident not in result, path, f"duplicate ID {ident}")
            result[ident] = item
        return result

    tables = {}
    for collection, key in (("products", "product_id"), ("dimensions", "dimension_id"),
            ("sources", "source_id"), ("claims", "claim_id"), ("conflicts", "conflict_id"),
            ("comparisons", "comparison_id"), ("findings", "finding_id"),
            ("recommendations", "recommendation_id")):
        tables[collection] = index(data[collection], key, collection)
    tables["assumptions"] = index(data["scope"]["assumptions"], "assumption_id", "scope.assumptions")
    index(data["clarification"]["questions"], "question_id", "clarification.questions")

    def refs(ids, table, path):
        check(len(ids) == len(set(ids)), path, "duplicate references")
        for ident in ids:
            check(ident in tables[table], path, f"missing {table} ID {ident}")
        return [tables[table][ident] for ident in ids if ident in tables[table]]

    scope, clarification = data["scope"], data["clarification"]
    refs(scope["product_ids"], "products", "scope.product_ids")
    refs(scope["dimension_ids"], "dimensions", "scope.dimension_ids")
    own = [p["product_id"] for p in data["products"] if p["role"] == "own"]
    check(own == ([] if scope["own_product_id"] is None else [scope["own_product_id"]]),
          "scope.own_product_id", "must match the sole own-role product, or be null with none")
    asking = data["phase"] == "clarification_required"
    check(clarification["required"] == asking, "clarification.required", "inconsistent phase")
    if asking:
        check(bool(clarification["questions"] and clarification["reason_codes"]), "clarification", "questions and reasons required")
        for key in ("claims", "comparisons", "findings", "recommendations"):
            check(not data[key], key, "must be empty during clarification")
    else:
        check(not clarification["questions"], "clarification.questions", "must be empty during execution")
        check(scope["objective"] is not None, "scope.objective", "required during execution")
        check(all(not a["blocking"] or a["state"] == "confirmed" for a in scope["assumptions"]),
              "scope.assumptions", "unresolved blocking assumption")
    if data["phase"] == "completed_with_gaps":
        check(bool(data["limitations"]), "limitations", "gaps must be described")
    for s in data["sources"]:
        t = s["timestamp"]
        if t["effective_from"] and t["effective_to"]:
            check(datetime.fromisoformat(t["effective_from"].replace("Z", "+00:00")) <
                  datetime.fromisoformat(t["effective_to"].replace("Z", "+00:00")),
                  s["source_id"], "invalid effective interval")
        if data["metadata"]["source_mode"] == "fixture" or s["fixture_path"] is not None:
            check(s["fixture_path"] is not None and s["content_sha256"] is not None,
                  s["source_id"], "fixture requires path and SHA-256")

    def dimension_value(item, path):
        refs([item["product"]], "products", path)
        dims = refs([item["dimension"]], "dimensions", path)
        if dims:
            kind = dims[0]["kind"]
            if kind == "capability":
                check(item["feature_status"] is not None and item["value"] is None, path, "capability requires feature_status and null value")
            else:
                check(item["feature_status"] is None, path, "non-capability requires null feature_status")
                if item["value"] is not None:
                    check(item["value"]["type"] == {"price": "money", "limit": "limit", "positioning": "text"}[kind], path, "value type does not match dimension")

    membership = {ident: set() for ident in tables["claims"]}
    for cf in data["conflicts"]:
        path = cf["conflict_id"]
        refs(cf["claim_ids"], "claims", path)
        refs(cf["selected_claim_ids"], "claims", path)
        check(len(set(cf["claim_ids"])) >= 2, path, "conflict requires two distinct claims")
        check(set(cf["selected_claim_ids"]) <= set(cf["claim_ids"]), path, "selected claims must belong to conflict")
        check(bool(cf["selected_claim_ids"]) == (cf["resolution"] != "unresolved"), path, "selection inconsistent with resolution")
        for ident in cf["claim_ids"]:
            if ident in membership:
                membership[ident].add(path)
    for c in data["claims"]:
        path = c["claim_id"]
        dimension_value(c, path)
        check(c["conflict_flag"] == bool(membership[path]), path, "conflict_flag must match conflict membership")
        source = None
        if c["source_id"] is None:
            check(all(c[k] is None for k in ("source_url", "source_type", "quote", "timestamp")), path, "source-free claim cannot invent source fields")
        else:
            found = refs([c["source_id"]], "sources", path)
            source = found[0] if found else None
            if source:
                for key in ("source_url", "source_type", "timestamp"):
                    check(c[key] == source[key], path, f"{key} differs from source")
        if c["status"] == "verified":
            check(source is not None and source["access_status"] == "accessed" and c["quote"] is not None, path, "verified requires accessed source and quote")
        if c["feature_status"] == "unsupported":
            check(c["status"] == "verified", path, "unsupported requires verified explicit-negative evidence; review quote semantics")
        if c["feature_status"] in ("partially_supported", "not_applicable"):
            check(bool(c["applicability"]["conditions"]), path, "feature status requires explanation in conditions")
        if c["feature_status"] == "unknown":
            check(c["status"] != "verified", path, "unknown capability is not a verified support conclusion")
    # Compare only identical price bases. Version/date changes still need an
    # explicit history resolution; different plans/currencies are not conflicts.
    prices = [c for c in data["claims"] if c["status"] == "verified"
              and c["value"] is not None and c["value"]["type"] == "money"]
    for left, right in combinations(prices, 2):
        same_entity = (left["product"], left["dimension"]) == (right["product"], right["dimension"])
        same_scope = all(left["applicability"][k] == right["applicability"][k]
                         for k in ("plan", "region", "billing_period", "conditions"))
        same_basis = all(left["value"][k] == right["value"][k]
                         for k in ("currency", "per", "billing_period", "commitment"))
        if same_entity and same_scope and same_basis and Decimal(left["value"]["amount"]) != Decimal(right["value"]["amount"]):
            check(bool(membership[left["claim_id"]] & membership[right["claim_id"]]),
                  left["claim_id"], f"price difference requires shared conflict record with {right['claim_id']}")
    for cmp in data["comparisons"]:
        path = cmp["comparison_id"]
        dimension_value(cmp, path)
        claims = refs(cmp["evidence_claim_ids"], "claims", path)
        conflicts = refs(cmp["conflict_ids"], "conflicts", path)
        check(all(c["product"] == cmp["product"] and c["dimension"] == cmp["dimension"] for c in claims), path, "evidence belongs to different product/dimension")
        expected = set().union(*(membership[c["claim_id"]] for c in claims)) if claims else set()
        check(set(cmp["conflict_ids"]) == expected, path, "conflict_ids must exactly match evidence conflicts")
        unresolved = any(c["resolution"] == "unresolved" for c in conflicts)
        check((cmp["assessment_status"] == "conflicted") == unresolved, path, "conflicted status must match unresolved conflicts")
        if cmp["assessment_status"] in ("unknown", "conflicted", "not_applicable"):
            check(cmp["value"] is None, path, "uncertain/inapplicable comparison requires null value")
            if cmp["feature_status"] is not None:
                target = "not_applicable" if cmp["assessment_status"] == "not_applicable" else "unknown"
                check(cmp["feature_status"] == target, path, "feature and assessment statuses disagree")
        if cmp["assessment_status"] == "established":
            verified = [c for c in claims if c["status"] == "verified"]
            for conflict in conflicts:
                if conflict["resolution"] != "unresolved":
                    verified = [c for c in verified if c["claim_id"] not in conflict["claim_ids"]
                                or c["claim_id"] in conflict["selected_claim_ids"]]
            check(bool(verified), path, "established requires verified evidence")
            check(cmp["feature_status"] not in ("unknown", "not_applicable"), path, "established cannot be unknown/inapplicable")
            if cmp["feature_status"] is None:
                check(cmp["value"] is not None, path, "established non-capability needs a value")
                check(any(c["value"] == cmp["value"] for c in verified), path, "value must match verified selected evidence")
            else:
                check(any(c["feature_status"] == cmp["feature_status"] for c in verified), path, "feature status must match verified selected evidence")
            if cmp["feature_status"] == "unsupported":
                check(any(c["feature_status"] == "unsupported" for c in verified), path, "unsupported requires verified unsupported claim")
    for f in data["findings"]:
        claims = refs(f["evidence_claim_ids"], "claims", f["finding_id"])
        comparisons = refs(f["comparison_ids"], "comparisons", f["finding_id"])
        if f["certainty"] == "established":
            check(bool(claims) and all(c["status"] == "verified" for c in claims) and
                  all(c["assessment_status"] == "established" for c in comparisons) and
                  not any(tables["conflicts"][cf]["resolution"] == "unresolved" for c in claims for cf in membership[c["claim_id"]]),
                  f["finding_id"], "established finding requires established evidence")
    for r in data["recommendations"]:
        path = r["recommendation_id"]
        check(bool(r["evidence_mapping"]), path, "evidence mapping required")
        for m in r["evidence_mapping"]:
            findings = refs([m["finding_id"]], "findings", path)
            refs(m["claim_ids"], "claims", path)
            check(bool(m["claim_ids"]), path, "mapping needs claims")
            if findings:
                check(set(m["claim_ids"]) <= set(findings[0]["evidence_claim_ids"]), path, "mapped claims must support mapped finding")
        refs(r["user_impact"]["claim_ids"], "claims", path)
        if r["user_impact"]["basis"] == "evidence":
            check(bool(r["user_impact"]["claim_ids"]), path, "evidence-based impact needs claims")
        for pre in r["preconditions"]:
            if pre["assumption_id"] is not None:
                assumptions = refs([pre["assumption_id"]], "assumptions", path)
                if assumptions:
                    check(pre["state"] == assumptions[0]["state"], path, "precondition state differs from assumption")
        if scope["own_product_id"] is None:
            check(r["conditional"] and any(p["state"] == "unconfirmed" for p in r["preconditions"]), path, "no own product: conditional advice with unconfirmed context required")
        if any(p["state"] != "confirmed" for p in r["preconditions"]):
            check(r["conditional"], path, "unconfirmed/rejected preconditions require conditional advice")
    return sorted(errors)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", type=Path)
    args = parser.parse_args()
    try:
        def reject_constant(value):
            raise ValueError(f"non-JSON numeric constant: {value}")
        data = json.loads(args.contract.read_text(encoding="utf-8-sig"),
                          object_pairs_hook=unique_object, parse_constant=reject_constant)
    except (OSError, UnicodeError, ValueError, RecursionError) as exc:
        print(f"INPUT ERROR: {exc}", file=sys.stderr)
        return 2
    errors = validate(data)
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("PASS: deterministic constraints satisfied. Semantic evidence review still required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
