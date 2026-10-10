#!/usr/bin/env python3
"""Deterministic, read-only MCP server for repository fixture manifests.

Environment:
  FIXTURE_MANIFEST   Absolute path to one manifest.json.
  FIXTURE_REPO_ROOT  Repository root used to resolve fixture_path.
  FIXTURE_TRACE_PATH Absolute JSONL trace path.

The server uses newline-delimited JSON-RPC over stdio and never performs network
I/O. Run it through ``sandbox-exec`` or ``codex sandbox`` with network disabled.
"""

from datetime import datetime, timezone
import hashlib
import html
import json
import os
from pathlib import Path
import re
import sys


PROTOCOL_VERSION = "2025-06-18"
SERVER_INFO = {"name": "fixture-eval", "version": "1.0.0"}


def now():
    return datetime.now(timezone.utc).isoformat()


def load_state():
    manifest_path = Path(os.environ["FIXTURE_MANIFEST"]).resolve()
    repo_root = Path(os.environ["FIXTURE_REPO_ROOT"]).resolve()
    trace_path = Path(os.environ["FIXTURE_TRACE_PATH"]).resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not manifest.get("synthetic") or manifest.get("network_allowed") is not False:
        raise RuntimeError("fixture manifest must be synthetic with network_allowed=false")
    sources = {}
    for source in manifest.get("sources", []):
        url = source["source_url"]
        if url in sources:
            raise RuntimeError(f"duplicate fixture URL: {url}")
        fixture = (repo_root / source["fixture_path"]).resolve()
        fixture.relative_to((repo_root / "tests" / "fixtures").resolve())
        body = fixture.read_text(encoding="utf-8")
        digest = hashlib.sha256(fixture.read_bytes()).hexdigest()
        if digest != source["content_sha256"]:
            raise RuntimeError(f"fixture hash mismatch: {source['source_id']}")
        sources[url] = {"metadata": source, "path": fixture, "body": body}
    return manifest_path, repo_root, trace_path, sources


MANIFEST_PATH, REPO_ROOT, TRACE_PATH, SOURCES = load_state()
SEQUENCE = 0


def append_trace(tool, arguments, status, details):
    global SEQUENCE
    SEQUENCE += 1
    event = {
        "sequence": SEQUENCE,
        "timestamp": now(),
        "tool": tool,
        "arguments": arguments,
        "status": status,
        **details,
    }
    TRACE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with TRACE_PATH.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def plain_text(markup):
    text = re.sub(r"<script\b[^>]*>.*?</script>", " ", markup, flags=re.I | re.S)
    text = re.sub(r"<style\b[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def search(arguments):
    query = str(arguments.get("query", "")).strip()
    terms = [term.casefold() for term in re.findall(r"[\w.-]+", query) if len(term) > 1]
    matches = []
    for entry in SOURCES.values():
        source = entry["metadata"]
        searchable = " ".join((source["source_id"], source["title"], source["source_url"])).casefold()
        if terms and not any(term in searchable for term in terms):
            continue
        body_text = plain_text(entry["body"])
        snippet = body_text[:180] + ("…" if len(body_text) > 180 else "")
        matches.append({
            "source_id": source["source_id"],
            "title": source["title"],
            "url": source["source_url"],
            "source_type": source["source_type"],
            "snippet": snippet,
        })
    matches.sort(key=lambda item: item["source_id"])
    append_trace("fixture_search", {"query": query}, "ok", {
        "result_count": len(matches),
        "source_ids": [item["source_id"] for item in matches],
    })
    return {"query": query, "results": matches}


def read(arguments):
    url = str(arguments.get("url", "")).strip()
    entry = SOURCES.get(url)
    if entry is None:
        append_trace("fixture_read", {"url": url}, "not_found", {})
        return {"status": "not_found", "url": url}
    source = entry["metadata"]
    body = entry["body"]
    append_trace("fixture_read", {"url": url}, "ok", {
        "source_id": source["source_id"],
        "content_sha256": source["content_sha256"],
        "body_bytes": len(body.encode("utf-8")),
    })
    return {
        "status": "ok",
        "source_id": source["source_id"],
        "title": source["title"],
        "url": source["source_url"],
        "source_type": source["source_type"],
        "timestamp": source["timestamp"],
        "content_sha256": source["content_sha256"],
        "body": body,
    }


TOOLS = [
    {
        "name": "fixture_search",
        "description": "Search only the configured synthetic fixture manifest. Returns metadata and short snippets, never full page bodies.",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
    },
    {
        "name": "fixture_read",
        "description": "Read the full synthetic fixture body for an exact URL returned by fixture_search. Unknown URLs return not_found.",
        "inputSchema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
            "additionalProperties": False,
        },
    },
]


def result_payload(value, is_error=False):
    return {
        "content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, sort_keys=True)}],
        "structuredContent": value,
        "isError": is_error,
    }


def handle(message):
    method = message.get("method")
    request_id = message.get("id")
    if method == "initialize":
        version = message.get("params", {}).get("protocolVersion", PROTOCOL_VERSION)
        return {"jsonrpc": "2.0", "id": request_id, "result": {
            "protocolVersion": version,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": SERVER_INFO,
        }}
    if method == "notifications/initialized":
        return None
    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params", {})
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name == "fixture_search":
            value = search(arguments)
        elif name == "fixture_read":
            value = read(arguments)
        else:
            value = {"status": "unknown_tool", "tool": name}
            return {"jsonrpc": "2.0", "id": request_id, "result": result_payload(value, True)}
        return {"jsonrpc": "2.0", "id": request_id, "result": result_payload(value)}
    if request_id is None:
        return None
    return {"jsonrpc": "2.0", "id": request_id, "error": {
        "code": -32601, "message": f"method not found: {method}"}}


def main():
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            message = json.loads(line)
            response = handle(message)
        except Exception as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {
                "code": -32603, "message": f"fixture server error: {exc}"}}
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False, separators=(",", ":")) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
