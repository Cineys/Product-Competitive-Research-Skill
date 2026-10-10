#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
PROFILE='(version 1)(allow default)(deny network*)'
exec /usr/bin/sandbox-exec -p "$PROFILE" /usr/bin/python3 "$SCRIPT_DIR/fixture_mcp.py"
