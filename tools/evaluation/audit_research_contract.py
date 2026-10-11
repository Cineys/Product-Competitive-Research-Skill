#!/usr/bin/env python3
"""Audit a model-generated research contract against fixture events and bodies.

This tool validates deterministic structure and trace relationships. It never
claims that string occurrence alone proves semantic support; verified-claim
entailment remains an explicit manual-review item unless an automatic
contradiction is found.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit


STATUS_ALIASES = {
    "v1": {"snippet_only": "discovered", "accessed": "accessed",
           "inaccessible": "inaccessible"},
    "v1_1": {"discovered": "discovered", "accessed": "accessed",
             "inaccessible": "inaccessible"},
}


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def normalize_source_status(version, status):
    try:
        return STATUS_ALIASES[version][status]
    except KeyError as error:
        raise ValueError(f"unsupported {version} source status: {status}") from error


def normalized_text(value):
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def valid_http_url(value):
    try:
        parsed = urlsplit(value)
    except (TypeError, ValueError):
        return False
    return parsed.scheme in ("http", "https") and bool(parsed.hostname)


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def completed_items(events):
    return [event["item"] for event in events if event.get("type") == "item.completed"]


def trace_state(trace):
    searched, read = set(), set()
    for event in trace:
        if event.get("tool") == "fixture_search" and event.get("status") == "ok":
            searched.update(event.get("source_ids", []))
        if event.get("tool") == "fixture_read" and event.get("status") == "ok":
            read.add(event.get("source_id"))
    return searched, read


def add_check(checks, ident, passed, details=None):
    checks.append({"check_id": ident, "status": "pass" if passed else "fail",
                   "details": details})


def semantic_token_checks(claim, quote):
    """Find objective token contradictions; never return semantic 'pass'."""
    failures = []
    quote_text = normalized_text(quote)
    applicability = claim.get("applicability") or {}
    plan = applicability.get("plan")
    if plan and normalized_text(plan) not in quote_text:
        failures.append(f"plan token absent from quote: {plan}")
    value = claim.get("value")
    if isinstance(value, dict):
        amount = value.get("amount")
        if amount is not None and not re.search(rf"(?<![\d.]){re.escape(str(amount))}(?![\d.])", quote_text):
            failures.append(f"value amount absent from quote: {amount}")
        if value.get("type") == "money":
            currency = value.get("currency")
            if currency and normalized_text(currency) not in quote_text:
                failures.append(f"currency absent from quote: {currency}")
            commitment = value.get("commitment")
            commitment_tokens = {
                "monthly": ("monthly", "month"),
                "annual": ("annual", "annually", "year"),
                "annually": ("annual", "annually", "year"),
            }.get(normalized_text(commitment), (normalized_text(commitment),))
            if commitment and not any(token in quote_text for token in commitment_tokens):
                failures.append(f"commitment absent from quote: {commitment}")
        billing_period = normalized_text(value.get("billing_period", ""))
        billing_tokens = {
            "month": ("month", "monthly"),
            "year": ("year", "annual", "annually"),
            "annual": ("year", "annual", "annually"),
        }.get(billing_period, (billing_period,))
        if billing_period and not any(token in quote_text for token in billing_tokens):
            failures.append(f"billing period absent from quote: {billing_period}")
        per = normalized_text(value.get("per", ""))
        if per and per not in quote_text:
            failures.append(f"unit basis absent from quote: {per}")
    applicability_period = normalized_text(applicability.get("billing_period", ""))
    if applicability_period:
        period_tokens = {
            "month": ("month", "monthly"),
            "year": ("year", "annual", "annually"),
            "annual": ("year", "annual", "annually"),
        }.get(applicability_period, (applicability_period,))
        if not any(token in quote_text for token in period_tokens):
            failures.append(f"applicability billing period absent from quote: {applicability_period}")
    claim_text = normalized_text(" ".join((claim.get("claim", ""),
                                            str(claim.get("dimension", "")))))
    for concept, tokens in (
            ("editor", ("editor", "编辑")),
            ("guest", ("guest", "访客")),
            ("simultaneous", ("simultaneous", "同时"))):
        if any(token in claim_text for token in tokens) and not any(token in quote_text for token in tokens):
            failures.append(f"headcount concept absent from quote: {concept}")
    return failures


def expected_case02_facts(contract):
    products = {item["product_id"]: normalized_text(item["name"])
                for item in contract.get("products", [])}
    verified = [claim for claim in contract.get("claims", [])
                if claim.get("status") == "verified"]

    def product_name(claim):
        return products.get(claim.get("product"), normalized_text(claim.get("product", "")))

    expected = [
        ("price", "figma", "fixture pro", "12"),
        ("price", "figma", "fixture business", "24"),
        ("price", "sketch", "fixture standard", "10"),
        ("price", "sketch", "fixture team", "20"),
        ("limit", "figma", "fixture pro", "10"),
        ("limit", "figma", "fixture business", "50"),
        ("limit", "sketch", "fixture standard", "5"),
        ("limit", "sketch", "fixture team", "25"),
        ("guest", "figma", None, "100"),
        ("guest", "sketch", None, "80"),
    ]
    results = []
    for kind, product, plan, amount in expected:
        matches = []
        for claim in verified:
            value = claim.get("value") or {}
            haystack = normalized_text(" ".join((
                claim.get("claim", ""), claim.get("quote", ""),
                str(claim.get("dimension", "")), str(value.get("unit", "")),
                str((claim.get("applicability") or {}).get("plan", "")),
            )))
            if product not in product_name(claim):
                continue
            if str(value.get("amount")) != amount:
                continue
            if plan and plan not in haystack:
                continue
            if kind == "price" and value.get("type") != "money":
                continue
            if kind == "limit" and not ("editor" in haystack or "编辑" in haystack):
                continue
            if kind == "guest" and not ("guest" in haystack or "访客" in haystack):
                continue
            matches.append(claim.get("claim_id"))
        results.append({"fact": {"kind": kind, "product": product, "plan": plan,
                                  "amount": amount}, "claim_ids": matches,
                        "covered": bool(matches)})
    return results


def run_validator(validator, contract, cwd):
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run([sys.executable, str(validator), str(contract)], cwd=cwd,
                            env=environment, capture_output=True, text=True, timeout=30)
    return {"exit_code": result.returncode, "stdout": result.stdout,
            "stderr": result.stderr}


def audit(version, contract_path, events_path, trace_path, fixture_manifest_path,
          fixture_root, validator_path):
    contract = read_json(contract_path)
    events = read_jsonl(events_path)
    trace = read_jsonl(trace_path)
    fixture_manifest = read_json(fixture_manifest_path)
    fixture_by_id = {source["source_id"]: source for source in fixture_manifest["sources"]}
    fixture_by_url = {source["source_url"]: source for source in fixture_manifest["sources"]}
    searched_ids, read_ids = trace_state(trace)
    checks, manual_reviews = [], []

    sources = contract.get("sources", [])
    source_ids = [source.get("source_id") for source in sources]
    source_urls = [source.get("source_url") for source in sources]
    add_check(checks, "source_ids_unique", len(source_ids) == len(set(source_ids)), source_ids)
    add_check(checks, "source_urls_unique", len(source_urls) == len(set(source_urls)), source_urls)
    sources_by_id = {source.get("source_id"): source for source in sources}
    for source in sources:
        ident = source.get("source_id")
        url = source.get("source_url")
        fixture = fixture_by_id.get(ident)
        add_check(checks, f"source:{ident}:id_present",
                  isinstance(ident, str) and bool(ident.strip()))
        add_check(checks, f"source:{ident}:url_syntax", valid_http_url(url), url)
        add_check(checks, f"source:{ident}:fixture_id", fixture is not None)
        add_check(checks, f"source:{ident}:url", fixture is not None and fixture["source_url"] == url,
                  {"contract": url, "fixture": fixture and fixture["source_url"]})
        try:
            state = normalize_source_status(version, source.get("access_status"))
        except ValueError as error:
            state = None
            add_check(checks, f"source:{ident}:status", False, str(error))
        if state == "accessed":
            add_check(checks, f"source:{ident}:accessed_has_read", ident in read_ids)
        if state == "discovered":
            add_check(checks, f"source:{ident}:discovered_has_search", ident in searched_ids)
            add_check(checks, f"source:{ident}:discovered_not_read", ident not in read_ids)
        if fixture:
            body_path = fixture_root / fixture["fixture_path"]
            add_check(checks, f"source:{ident}:fixture_hash",
                      body_path.is_file() and sha256(body_path) == fixture["content_sha256"])

    claim_ids = {claim.get("claim_id") for claim in contract.get("claims", [])}
    for claim in contract.get("claims", []):
        ident = claim.get("claim_id")
        source_id = claim.get("source_id")
        source = sources_by_id.get(source_id)
        if source_id is not None:
            add_check(checks, f"claim:{ident}:source_id_resolves", source is not None)
            add_check(checks, f"claim:{ident}:source_url_matches",
                      source is not None and claim.get("source_url") == source.get("source_url"))
        if claim.get("status") != "verified":
            continue
        add_check(checks, f"claim:{ident}:verified_source_read", source_id in read_ids)
        add_check(checks, f"claim:{ident}:not_search_only",
                  not (source_id in searched_ids and source_id not in read_ids))
        quote = claim.get("quote")
        fixture = fixture_by_url.get(claim.get("source_url"))
        body = ""
        if fixture:
            body = (fixture_root / fixture["fixture_path"]).read_text(encoding="utf-8")
        quote_present = bool(quote) and normalized_text(quote) in normalized_text(body)
        add_check(checks, f"claim:{ident}:quote_in_body", quote_present)
        token_failures = semantic_token_checks(claim, quote or "") if quote_present else []
        add_check(checks, f"claim:{ident}:structured_tokens_not_contradicted",
                  not token_failures, token_failures)
        manual_reviews.append({
            "review_id": f"claim:{ident}:semantic_support",
            "status": "automatic_failure" if token_failures else "manual_review_required",
            "reason": (token_failures or [
                "Quote occurrence and structured-token consistency do not prove that the quote "
                "semantically supports the full claim, plan, billing basis, or headcount concept."
            ]),
        })

    comparison_ids = {item.get("comparison_id") for item in contract.get("comparisons", [])}
    for item in contract.get("comparisons", []):
        missing = sorted(set(item.get("evidence_claim_ids", [])) - claim_ids)
        add_check(checks, f"comparison:{item.get('comparison_id')}:claim_refs", not missing, missing)
    for item in contract.get("findings", []):
        missing_claims = sorted(set(item.get("evidence_claim_ids", [])) - claim_ids)
        missing_comparisons = sorted(set(item.get("comparison_ids", [])) - comparison_ids)
        add_check(checks, f"finding:{item.get('finding_id')}:claim_refs",
                  not missing_claims, missing_claims)
        add_check(checks, f"finding:{item.get('finding_id')}:comparison_refs",
                  not missing_comparisons, missing_comparisons)

    coverage = expected_case02_facts(contract)
    add_check(checks, "case02_key_fact_coverage", all(item["covered"] for item in coverage), coverage)

    items = completed_items(events)
    validator_events = [item for item in items
                        if item.get("type") == "command_execution"
                        and "validate_research.py" in str(item.get("command", ""))
                        and "research_contract.json" in str(item.get("command", ""))]
    model_validator = [{"item_id": item.get("id"), "exit_code": item.get("exit_code"),
                        "stdout": item.get("aggregated_output", ""),
                        "command": item.get("command")}
                       for item in validator_events]
    independent = run_validator(validator_path, contract_path, contract_path.parent)
    validator_match = any(item["exit_code"] == independent["exit_code"]
                          and normalized_text(item["stdout"]) == normalized_text(independent["stdout"])
                          for item in model_validator)
    add_check(checks, "model_validator_executed", bool(model_validator), model_validator)
    add_check(checks, "independent_validator_passed", independent["exit_code"] == 0, independent)
    add_check(checks, "validator_results_match", validator_match,
              {"model": model_validator, "independent": independent})

    automatic_failures = [item for item in checks if item["status"] == "fail"]
    return {
        "audit_version": "1.0.0", "contract_version": version,
        "schema_version": contract.get("schema_version"),
        "automatic_checks": checks, "automatic_failure_count": len(automatic_failures),
        "manual_reviews": manual_reviews,
        "manual_review_required_count": sum(item["status"] == "manual_review_required"
                                             for item in manual_reviews),
        "validator": {"model": model_validator, "independent": independent,
                      "results_match": validator_match},
        "trace": {"searched_source_ids": sorted(searched_ids),
                  "read_source_ids": sorted(read_ids)},
        "key_fact_coverage": coverage,
        "status": "automatic_checks_passed_manual_review_pending"
                  if not automatic_failures else "automatic_checks_failed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", choices=("v1", "v1_1"), required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--trace", type=Path, required=True)
    parser.add_argument("--fixture-manifest", type=Path, required=True)
    parser.add_argument("--fixture-root", type=Path, required=True)
    parser.add_argument("--validator", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit(f"refusing to overwrite audit output: {args.output}")
    result = audit(args.version, args.contract, args.events, args.trace,
                   args.fixture_manifest, args.fixture_root, args.validator)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                           encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["automatic_failure_count"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
