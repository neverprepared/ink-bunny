# Reflex Documentation Audit

**Date:** 2026-02-23
**Auditor:** Claude Code (documentation audit)
**Scope:** All documentation files under `reflex/`

## Ground Truth (verified from source)

| Component | Actual count / value |
|-----------|----------------------|
| SKILL.md files | **42** (in `plugins/reflex/skills/`) |
| Command .md files | **19** (in `plugins/reflex/commands/`) |
| Agent .md files | **2** (`rag-proxy`, `workflow-orchestrator`) |
| Workflow templates | **5** (`jira-driven`, `github-driven`, `standalone`, `custom`, `transcript-summary`) |
| Workflow steps | 16 (in `workflow-templates/steps/`) |
| MCP servers in catalog | **17** |
| Hook events configured | 3 (`SessionStart`, `PreToolUse`, `PostToolUse`) |
| Hook scripts triggered | 6 total (2 session-start, 1 pre-tool, 3 post-tool) |
| Scripts in `scripts/` | **15** (10 shell + 5 Python, excluding `__pycache__`) |
| VERSION | `1.13.0` |

### Commands (19 actual):
`agents`, `azure-discover`, `certcollect`, `container`, `gitconfig`, `guardrail`,
`handoff`, `ingest`, `init`, `langfuse`, `mcp`, `notify`, `qdrant`, `skills`,
`speak`, `statusline`, `summarize-transcript`, `update-mcp`, `workflow`

### Scripts (15 actual):
Shell hooks: `brainbox-hook.sh`, `brainbox-connect.sh`, `check-dependencies.sh`,
`guardrail-hook.sh`, `langfuse-hook.sh`, `mcp-generate.sh`, `notify-hook.sh`,
`notify.sh`, `qdrant-websearch-hook.sh`, `statusline.sh`

Python implementations: `guardrail.py`, `ingest.py`, `langfuse-trace.py`,
`qdrant-websearch-store.py`, `summarize.py`

---

## Issues Found and Fixed

### [HIGH] plugins/reflex/README.md — Nonexistent `/reflex:task` command referenced

**File:** `reflex/plugins/reflex/README.md`
**Line (before fix):** Agents section, after the agents table
**Claim:** `Use /reflex:task "your task" --rag to enrich tasks with stored knowledge before delegating to official plugin agents.`
**Problem:** There is no `task.md` in `plugins/reflex/commands/`. The command `/reflex:task` does not exist. This would cause users to attempt to run a nonexistent slash command.
**Fix:** Removed the line entirely. The agents table now stands alone without the incorrect usage instruction.

---

### [HIGH] plugins/reflex/README.md — Commands table missing 2 of 19 commands

**File:** `reflex/plugins/reflex/README.md`
**Claim:** Commands table listed 17 commands.
**Actual:** 19 command `.md` files exist.
**Missing commands:**
- `/reflex:container` — `container.md` exists with full implementation for brainbox API management
- `/reflex:workflow` — `workflow.md` exists with 11 subcommands for workflow template management

**Fix:** Added both missing rows to the commands table:
- `/reflex:container <start|stop|status|create|query|dashboard|health|config>` — Manage brainbox API and sandboxed containers
- `/reflex:workflow <apply|list|create|edit|delete|sync|compose|status|variables|diff|steps>` — Manage workflow templates

---

### [MEDIUM] plugins/reflex/README.md — Project structure missing `workflow-templates/`

**File:** `reflex/plugins/reflex/README.md`
**Problem:** The `## Project Structure` tree diagram omitted the `workflow-templates/` directory entirely, which contains 5 workflow templates, 16 step fragments, and `catalog.json`.
**Fix:** Added `workflow-templates/    # 5 workflow templates + step fragments` to the tree.

---

### [MEDIUM] reflex/CLAUDE.md — Project structure missing `workflow-templates/`

**File:** `reflex/CLAUDE.md`
**Problem:** The `## Repository Structure` tree diagram listed `plugins/reflex/` contents but omitted `workflow-templates/`, making it appear the plugin has no workflow template system.
**Fix:** Added `│   ├── workflow-templates/   # 5 workflow templates + step fragments` between `scripts/` and `mcp-catalog.json`.

---

### [MEDIUM] plugins/reflex/CLAUDE.md — Project structure missing `workflow-templates/`

**File:** `reflex/plugins/reflex/CLAUDE.md`
**Problem:** The `## Project Structure` tree omitted `workflow-templates/`, which is a first-class component of the plugin (referenced by the `/reflex:workflow` command and workflow-orchestrator agent).
**Fix:** Added `├── workflow-templates/          # 5 workflow templates + step fragments` between `scripts/` and `mcp-catalog.json`.

---

### [LOW] plugins/reflex/CLAUDE.md — Scripts directory comment implied single script

**File:** `reflex/plugins/reflex/CLAUDE.md`
**Claim:** `├── scripts/                     # Helper scripts (mcp-generate.sh)`
**Problem:** Naming only `mcp-generate.sh` implies it is the only or primary script. The directory contains 15 scripts: 10 shell scripts (6 hook entry points + 4 utilities) and 5 Python implementations.
**Fix:** Changed comment to `# Helper scripts (15 scripts: hook entry points + Python implementations)`.

---

## No Issues Found

The following claims were verified accurate and required no changes:

| Claim | File(s) | Verified |
|-------|---------|---------|
| 42 skills | all 4 docs | ✓ Exactly 42 SKILL.md files |
| 19 commands | `reflex/README.md` feature table | ✓ Count correct (though inner docs were incomplete) |
| 2 agents (`rag-proxy`, `workflow-orchestrator`) | all 4 docs | ✓ Exactly 2 agent .md files with those names |
| 17 MCP servers in catalog | `plugins/reflex/README.md`, `plugins/reflex/CLAUDE.md` | ✓ 17 entries in `mcp-catalog.json` |
| MCP server names and categories | `plugins/reflex/README.md` table | ✓ All 17 match catalog exactly |
| `/reflex:workflow` subcommands `apply/list/create/edit/delete/sync/compose/status/variables/diff/steps` | `plugins/reflex/CLAUDE.md` | ✓ Matches `argument-hint` in `workflow.md` |
| `/reflex:container` subcommands `start/stop/status/create/query/dashboard/health/config` | `plugins/reflex/CLAUDE.md` | ✓ Matches `argument-hint` in `container.md` |
| SessionStart hooks: dependency check + brainbox status | root `CLAUDE.md` (monorepo) | ✓ `check-dependencies.sh` + `brainbox-hook.sh` |
| PreToolUse: guardrails | root `CLAUDE.md` (monorepo) | ✓ `guardrail-hook.sh` with matcher |
| PostToolUse: LangFuse, Qdrant web-search, notifications | root `CLAUDE.md` (monorepo) | ✓ 3 hooks in `PostToolUse` |
| Workflow templates: jira-driven, github-driven, standalone, custom, transcript-summary | root `CLAUDE.md` (monorepo) | ✓ All 5 template files exist |
| Docker services on ports 6333 (Qdrant) and 3000 (LangFuse) | `reflex/README.md`, `reflex/CLAUDE.md` | ✓ Consistent across docs |
| Plugin manifest at `.claude-plugin/plugin.json` | `plugins/reflex/CLAUDE.md`, `plugins/reflex/README.md` | ✓ Path exists |
| `mcp-catalog.json` path | all docs | ✓ File exists at stated path |
| `hooks/hooks.json` path | `reflex/CLAUDE.md`, `plugins/reflex/CLAUDE.md` | ✓ File exists at stated path |
| `CLAUDE_CONFIG_DIR` convention | `plugins/reflex/CLAUDE.md` | ✓ All scripts use `${CLAUDE_CONFIG_DIR:-$HOME/.claude}` |

---

## Files Changed

| File | Changes |
|------|---------|
| `reflex/plugins/reflex/README.md` | Removed nonexistent `/reflex:task` line; added `/reflex:container` and `/reflex:workflow` to commands table; added `workflow-templates/` to project structure |
| `reflex/CLAUDE.md` | Added `workflow-templates/` to project structure |
| `reflex/plugins/reflex/CLAUDE.md` | Added `workflow-templates/` to project structure; updated scripts comment |
