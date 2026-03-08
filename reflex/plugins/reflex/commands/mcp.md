---
description: Manage MCP servers (list, install, uninstall, enable, disable, select)
allowed-tools: Bash(jq:*), AskUserQuestion, Read
argument-hint: [list|select|install|uninstall|enable|disable|status|generate] [server...]
---

# MCP Server Management

Manage MCP servers for your workspace. `.mcp.json` is the source of truth — a server is
**enabled** if its key exists in `.mcpServers`, **disabled** if absent. No separate config file.

## Paths

```bash
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT}"
CATALOG="${PLUGIN_ROOT}/mcp-catalog.json"
MCP_JSON="${WORKSPACE_HOME:-$HOME}/.mcp.json"
```

Initialize `.mcp.json` if missing (run before any subcommand that reads or writes it):

```bash
if [[ ! -f "$MCP_JSON" ]]; then
  echo '{"mcpServers":{}}' > "$MCP_JSON"
fi
```

---

## Subcommands

### `/reflex:mcp` or `/reflex:mcp list`

Show all catalog servers with their enabled/disabled status.

**Instructions:**

1. Initialize `.mcp.json` if missing
2. Read `${CATALOG}` and `${MCP_JSON}`
3. Count enabled: number of keys in `.mcpServers`
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

Interactive server selection — add/remove servers from `.mcp.json`.

**Instructions:**

1. Initialize `.mcp.json` if missing
2. Read `${CATALOG}` and `${MCP_JSON}`
3. Collect currently enabled server names: `jq -r '.mcpServers | keys[]' "$MCP_JSON"`
4. Present two `AskUserQuestion` calls (4 questions each, max 4 options per question):

**First call** (Development + Data & Docs):
- Question 1 — "Which Development servers to enable?": `git`, `github`, `playwright`, `atlassian`
- Question 2 — "Which Data & Docs servers to enable?": `markitdown`, `microsoft-docs`, `sql-server`, `google-workspace`

**Second call** (Cloud + Ops):
- Question 3 — "Which Azure Cloud servers to enable?": `azure`, `azure-devops`, `azure-ai-foundry`, `devbox`
- Question 4 — "Which Ops & Infra servers to enable?": `kubernetes`, `spacelift`, `uptime-kuma`

Option labels: `<name> - <description>` (from catalog). Pre-select servers currently in `.mcpServers`.

5. Combine all selected names from both calls into `SELECTED`
6. Build new `mcpServers` by reading `.servers.<name>.definition` from catalog for each selected name:

```bash
NEW_SERVERS='{}'
for name in "${SELECTED[@]}"; do
  DEF=$(jq -c ".servers[\"$name\"].definition" "$CATALOG")
  NEW_SERVERS=$(echo "$NEW_SERVERS" | jq --arg n "$name" --argjson d "$DEF" '. + {($n): $d}')
done
echo "{\"mcpServers\": $NEW_SERVERS}" > "$MCP_JSON"
```

7. Output: "Updated `.mcp.json` — {N} servers enabled. Restart Claude Code to apply."

Note: `qdrant` and `brainbox` are plugin-declared and excluded from this selection.

---

### `/reflex:mcp enable <server...>`

Enable one or more servers by adding their definitions to `.mcp.json`.

**Instructions:**

1. Initialize `.mcp.json` if missing
2. For each server name in arguments:
   - Look up `.servers.<name>.definition` in `${CATALOG}`
   - If not found in catalog: warn "Unknown server: {name}" and skip
   - Otherwise add/overwrite in `.mcp.json`:
     ```bash
     DEF=$(jq -c ".servers[\"$name\"].definition" "$CATALOG")
     jq --arg n "$name" --argjson d "$DEF" '.mcpServers[$n] = $d' "$MCP_JSON" > /tmp/mcp.tmp && mv /tmp/mcp.tmp "$MCP_JSON"
     ```
3. Output: "Enabled: {names}. Restart Claude Code to apply."

---

### `/reflex:mcp disable <server...>`

Disable one or more servers by removing them from `.mcp.json`.

**Instructions:**

1. For each server name in arguments:
   ```bash
   jq --arg n "$name" 'del(.mcpServers[$n])' "$MCP_JSON" > /tmp/mcp.tmp && mv /tmp/mcp.tmp "$MCP_JSON"
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

1. Initialize `.mcp.json` if missing
2. Read `${CATALOG}` and `${MCP_JSON}`
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

Re-sync `.mcp.json` definitions from the current catalog (useful after `/reflex:update-mcp apply`).

**Instructions:**

1. Read `${MCP_JSON}` — get list of currently enabled server names: `jq -r '.mcpServers | keys[]' "$MCP_JSON"`
2. For each enabled name: look up `.servers.<name>.definition` in `${CATALOG}`
   - If not in catalog: warn "Server '{name}' not in catalog — keeping existing definition" and skip
3. Build updated `mcpServers` object and write to `.mcp.json`:

```bash
ENABLED=$(jq -r '.mcpServers | keys[]' "$MCP_JSON")
NEW_SERVERS='{}'
while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  DEF=$(jq -c ".servers[\"$name\"].definition // empty" "$CATALOG")
  if [[ -z "$DEF" ]]; then
    # Keep existing definition
    DEF=$(jq -c ".mcpServers[\"$name\"]" "$MCP_JSON")
    echo "Warning: '$name' not in catalog, keeping existing definition" >&2
  fi
  NEW_SERVERS=$(echo "$NEW_SERVERS" | jq --arg n "$name" --argjson d "$DEF" '. + {($n): $d}')
done <<< "$ENABLED"
echo "{\"mcpServers\": $NEW_SERVERS}" > "$MCP_JSON"
```

4. Output: "Re-synced {N} server definitions from catalog. Restart Claude Code to apply."
