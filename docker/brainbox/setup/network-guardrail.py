#!/usr/bin/env python3
"""
Network write guardrail for brainbox containers.

PreToolUse hook that blocks outbound network write operations (POST, PUT,
DELETE, PATCH) while allowing all read-only network access and full
filesystem freedom.

Receives tool call data from stdin (JSON) and returns a decision via
stdout JSON.

Exit codes:
  0 = Decision made (check stdout JSON for permissionDecision)
  Non-zero = Error (caller should fail open)
"""

import json
import re
import sys


# =============================================================================
# Patterns — network write operations to block
# =============================================================================

# Bash commands that perform HTTP writes
BASH_WRITE_PATTERNS = [
    # curl with explicit write methods
    (r"curl\b.*\s+(-X\s*|--request[\s=])(POST|PUT|DELETE|PATCH)\b",
     "curl with write method"),
    # curl with data flags (implies POST)
    (r"curl\b.*\s+(-d\b|--data\b|--data-\w+\b|--form\b|-F\b)",
     "curl with data payload (implies POST)"),
    # wget write methods
    (r"wget\b.*\s+(--post-data\b|--post-file\b|--method[\s=](POST|PUT|DELETE|PATCH))",
     "wget with write method"),
    # httpie write methods
    (r"\bhttps?\s+.*\b(POST|PUT|DELETE|PATCH)\b",
     "httpie with write method"),
    # python requests write methods
    (r"requests\.(post|put|delete|patch)\s*\(",
     "python requests write call"),
    # python httpx write methods
    (r"httpx\.(post|put|delete|patch|AsyncClient)\s*\(",
     "python httpx write call"),
    # node fetch/axios write
    (r"""(fetch|axios)\s*\(.*method\s*:\s*['\"](POST|PUT|DELETE|PATCH)""",
     "node fetch/axios write call"),
]

# Playwright MCP tools that interact with page elements (form submission, clicks)
PLAYWRIGHT_WRITE_PATTERN = re.compile(
    r"mcp__playwright__\w*("
    r"click|fill|type|press|select|check|uncheck|submit"
    r"|upload|drag|drop|dispatch|set_value|focus|hover"
    r")\w*",
    re.IGNORECASE,
)


# =============================================================================
# Allowlist — destinations always permitted regardless of HTTP method
# =============================================================================

# Targets that agents must be able to write to (e.g. hub task reporting)
ALLOWED_DESTINATIONS = [
    r"host[.]docker[.]internal:\d+",  # brainbox hub API (any port)
]


def is_allowlisted(command: str) -> bool:
    """Return True if the command targets an explicitly allowed destination."""
    for pattern in ALLOWED_DESTINATIONS:
        if re.search(pattern, command):
            return True
    return False


# =============================================================================
# Matching
# =============================================================================

def check_bash_command(command: str) -> str | None:
    """Check if a Bash command performs a network write. Returns description or None."""
    if is_allowlisted(command):
        return None
    for pattern, description in BASH_WRITE_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return description
    return None


def check_tool_name(tool_name: str) -> str | None:
    """Check if an MCP tool name is a write operation. Returns description or None."""
    if PLAYWRIGHT_WRITE_PATTERN.match(tool_name):
        return f"Playwright interaction: {tool_name}"
    return None


# =============================================================================
# Main
# =============================================================================

def main():
    try:
        raw_input = sys.stdin.read().strip()
        if not raw_input:
            sys.exit(0)

        tool_data = json.loads(raw_input)
        tool_name = tool_data.get("tool_name", "")
        tool_input = tool_data.get("tool_input", {})

        reason = None

        # Check Bash commands for HTTP write patterns
        if tool_name == "Bash":
            command = tool_input.get("command", "")
            reason = check_bash_command(command)

        # Check Playwright MCP tools for page interactions
        elif tool_name.startswith("mcp__playwright__"):
            reason = check_tool_name(tool_name)

        if reason:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": (
                        f"Network write operation denied: {reason}. "
                        "This container has read-only HTTP access. "
                        "GET/search/query operations are allowed. "
                        "POST/PUT/DELETE/PATCH operations are blocked. "
                        "Use WebFetch (GET-only) or WebSearch for reading APIs."
                    ),
                },
            }
            print(json.dumps(output))

        sys.exit(0)

    except (json.JSONDecodeError, Exception):
        # Fail open on errors
        sys.exit(0)


if __name__ == "__main__":
    main()
