#!/usr/bin/env bash
#
# mcp-generate.sh — DEPRECATED
#
# MCP server management now uses .mcp.json directly as the source of truth.
# Use the /reflex:mcp command instead:
#
#   /reflex:mcp select    — interactive server selection
#   /reflex:mcp enable    — enable servers by name
#   /reflex:mcp disable   — disable servers by name
#   /reflex:mcp generate  — re-sync definitions from catalog
#
# This script is kept as a stub for backwards compatibility.
#

echo "mcp-generate.sh is deprecated. Use /reflex:mcp to manage MCP servers." >&2
echo "See: /reflex:mcp list | select | enable | disable | generate" >&2
exit 0
