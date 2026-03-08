---
description: Manage MCP servers (list, install, uninstall, enable, disable, select)
allowed-tools: Bash(jq:*), AskUserQuestion, Read
argument-hint: [list|select|install|uninstall|enable|disable|status|generate] [server...]
---

# MCP Server Management

Manage MCP servers for your workspace. `$CLAUDE_CONFIG_DIR/.claude.json` is the source of truth —
a server is **enabled** if its key exists in `.mcpServers`, **disabled** if absent. No separate
config file.

## Paths

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
CATALOG="${PLUGIN_ROOT}/mcp-catalog.json"
CLAUDE_JSON="${CLAUDE_CONFIG_DIR:-$HOME/.claude}/.claude.json"
```

**Important**: `.claude.json` contains many user settings — always update only the `mcpServers`
key using `jq`, never overwrite the whole file.

Helper for in-place updates:

```bash
# Enable a server (add/overwrite one key in mcpServers)
DEF=$(jq -c ".servers[\"$name\"].definition" "$CATALOG")
jq --arg n "$name" --argjson d "$DEF" '.mcpServers[$n] = $d' "$CLAUDE_JSON" > /tmp/mcp.tmp && mv /tmp/mcp.tmp "$CLAUDE_JSON"

# Disable a server (remove one key from mcpServers)
jq --arg n "$name" 'del(.mcpServers[$n])' "$CLAUDE_JSON" > /tmp/mcp.tmp && mv /tmp/mcp.tmp "$CLAUDE_JSON"

# Replace all mcpServers at once
jq --argjson s "$NEW_SERVERS" '.mcpServers = $s' "$CLAUDE_JSON" > /tmp/mcp.tmp && mv /tmp/mcp.tmp "$CLAUDE_JSON"
```

---

## Subcommands

### `/reflex:mcp` or `/reflex:mcp list`

Show all catalog servers with their enabled/disabled status.

**Instructions:**

1. Read `${CATALOG}` and `${CLAUDE_JSON}`
2. Enabled servers: `jq -r '.mcpServers | keys[]' "$CLAUDE_JSON"`
3. Count enabled vs total catalog servers
4. Display a table:

```
## MCP Servers ({enabled}/{total} enabled)

| Server | Status | Category | Description |
|--------|--------|----------|-------------|
| git | enabled | development | Git repository operations |
| atlassian | disabled | collaboration | Jira and Confluence integration |
| kubernetes | disabled | cloud | Kubernetes cluster operations |
```

5. Add a note: "`qdrant` and `brainbox` are plugin-declared — always available as `/reflex:qdrant` and `/reflex:brainbox`."
6. Show hint: `Manage: /reflex:mcp select | /reflex:mcp enable <name> | /reflex:mcp disable <name>`

---

### `/reflex:mcp select`

Interactive server selection — add/remove servers from `.claude.json`.

**Instructions:**

1. Read `${CATALOG}` and `${CLAUDE_JSON}`
2. Collect currently enabled server names: `jq -r '.mcpServers | keys[]' "$CLAUDE_JSON"`
3. Present two `AskUserQuestion` calls (4 questions each, max 4 options per question).
   Pre-select options whose names are in the currently enabled set.

**First call** (Development + Data & Docs):
- Question 1 — "Which Development servers to enable?": `git`, `github`, `playwright`, `atlassian`
- Question 2 — "Which Data & Docs servers to enable?": `markitdown`, `microsoft-docs`, `sql-server`, `google-workspace`

**Second call** (Cloud + Ops):
- Question 3 — "Which Azure Cloud servers to enable?": `azure`, `azure-devops`, `azure-ai-foundry`, `devbox`
- Question 4 — "Which Ops & Infra servers to enable?": `kubernetes`, `spacelift`, `uptime-kuma`

Option labels: `<name> — <description>` (from catalog).

4. Combine all selected names from both calls into `SELECTED`
5. Build new `mcpServers` object from catalog definitions for each selected name:

```bash
NEW_SERVERS='{}'
for name in "${SELECTED[@]}"; do
  DEF=$(jq -c ".servers[\"$name\"].definition" "$CATALOG")
  NEW_SERVERS=$(echo "$NEW_SERVERS" | jq --arg n "$name" --argjson d "$DEF" '. + {($n): $d}')
done
jq --argjson s "$NEW_SERVERS" '.mcpServers = $s' "$CLAUDE_JSON" > /tmp/mcp.tmp && mv /tmp/mcp.tmp "$CLAUDE_JSON"
```

6. Output: "Updated — {N} servers enabled. Restart Claude Code to apply."

Note: `qdrant` and `brainbox` are plugin-declared and excluded from this selection.

---

### `/reflex:mcp enable <server...>`

Enable one or more servers by adding their definitions to `.claude.json`.

**Instructions:**

1. For each server name in arguments:
   - Look up `.servers.<name>.definition` in `${CATALOG}`
   - If not found in catalog: warn "Unknown server: {name}" and skip
   - Otherwise add/overwrite:
     ```bash
     DEF=$(jq -c ".servers[\"$name\"].definition" "$CATALOG")
     jq --arg n "$name" --argjson d "$DEF" '.mcpServers[$n] = $d' "$CLAUDE_JSON" > /tmp/mcp.tmp && mv /tmp/mcp.tmp "$CLAUDE_JSON"
     ```
2. Output: "Enabled: {names}. Restart Claude Code to apply."

---

### `/reflex:mcp disable <server...>`

Disable one or more servers by removing them from `.claude.json`.

**Instructions:**

1. For each server name in arguments:
   ```bash
   jq --arg n "$name" 'del(.mcpServers[$n])' "$CLAUDE_JSON" > /tmp/mcp.tmp && mv /tmp/mcp.tmp "$CLAUDE_JSON"
   ```
2. Output: "Disabled: {names}. Restart Claude Code to apply."

---

### `/reflex:mcp install <server...>`

Alias for `enable`. Same behavior.

---

### `/reflex:mcp uninstall <server...>`

Alias for `disable`. Same behavior.

---

### `/reflex:mcp status`

Show detailed status for each catalog server including credential readiness.

**Instructions:**

1. Read `${CATALOG}` and `${CLAUDE_JSON}`
2. Enabled servers: `jq -r '.mcpServers | keys[]' "$CLAUDE_JSON"`
3. For each catalog server, check:
   - **Enabled**: key present in `.mcpServers`
   - **Credentials**: for each var in `.servers.<name>.requires[]`, test `[[ -n "${!VAR}" ]]`
   - Collect any missing vars
4. Display:

```
## MCP Server Status

| Server | Enabled | Credentials | Missing |
|--------|---------|-------------|---------|
| git | yes | ready | - |
| atlassian | yes | missing | JIRA_URL, JIRA_API_TOKEN |
| azure | no | partial | AZURE_CLIENT_SECRET |
```

5. Show hint: `Configure credentials: /reflex:init <service>`

---

### `/reflex:mcp generate`

Re-sync `.claude.json` server definitions from the current catalog (useful after `/reflex:update-mcp apply`).

**Instructions:**

1. Read `${CLAUDE_JSON}` — get currently enabled names: `jq -r '.mcpServers | keys[]' "$CLAUDE_JSON"`
2. For each enabled name: look up `.servers.<name>.definition` in `${CATALOG}`
   - If not in catalog: warn "Server '{name}' not in catalog — keeping existing definition" and skip
3. Build updated `mcpServers` and write back (preserving all other `.claude.json` keys):

```bash
ENABLED=$(jq -r '.mcpServers | keys[]' "$CLAUDE_JSON")
NEW_SERVERS='{}'
while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  DEF=$(jq -c ".servers[\"$name\"].definition // empty" "$CATALOG")
  if [[ -z "$DEF" ]]; then
    DEF=$(jq -c ".mcpServers[\"$name\"]" "$CLAUDE_JSON")
    echo "Warning: '$name' not in catalog, keeping existing definition" >&2
  fi
  NEW_SERVERS=$(echo "$NEW_SERVERS" | jq --arg n "$name" --argjson d "$DEF" '. + {($n): $d}')
done <<< "$ENABLED"
jq --argjson s "$NEW_SERVERS" '.mcpServers = $s' "$CLAUDE_JSON" > /tmp/mcp.tmp && mv /tmp/mcp.tmp "$CLAUDE_JSON"
```

4. Output: "Re-synced {N} server definitions from catalog. Restart Claude Code to apply."
