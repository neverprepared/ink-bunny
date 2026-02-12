# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Reflex is a Claude Code plugin for application development, infrastructure, and data engineering workflows. It provides skills (reusable knowledge patterns), agents, and MCP server integrations.

## Repository Structure

```
reflex/
├── plugins/reflex/           # Main plugin (where most development happens)
│   ├── .claude-plugin/       # Plugin manifest (plugin.json)
│   ├── agents/               # Sub-agents (rag-proxy, workflow-orchestrator)
│   ├── commands/             # Slash commands (/reflex:*)
│   ├── skills/               # 42 skill definitions (SKILL.md files)
│   ├── hooks/                # Session hooks (hooks.json)
│   ├── scripts/              # Helper scripts (bash)
│   ├── mcp-catalog.json      # MCP server catalog (registry)
│   └── CLAUDE.md             # Plugin-specific instructions
├── docker/                   # Docker Compose services
│   ├── qdrant/               # Vector database (port 6333)
│   └── langfuse/             # LLM observability (port 3000)
├── release-please-config.json  # Release automation
└── VERSION                   # Current version
```

## Development

### Local Testing

```bash
# Run Claude Code with local plugin
claude --plugin-dir /path/to/reflex
```

### Plugin Components

- **Skills**: Markdown files in `plugins/reflex/skills/<name>/SKILL.md`
- **Commands**: Markdown files in `plugins/reflex/commands/<name>.md`
- **Agents**: Markdown files in `plugins/reflex/agents/<name>.md`
- **Hooks**: Configured in `plugins/reflex/hooks/hooks.json`
- **MCP Servers**: Catalog in `plugins/reflex/mcp-catalog.json`, runtime config generated to `~/.mcp.json`

### Docker Services

```bash
# Start Qdrant (required for RAG features)
cd docker/qdrant && cp .env.example .env && docker compose up -d

# Start LangFuse (optional, for observability)
cd docker/langfuse && cp .env.example .env && docker compose up -d
```

## Versioning and Releases

This project uses [release-please](https://github.com/googleapis/release-please) with conventional commits:

- `feat:` - New features (bumps minor version)
- `fix:` - Bug fixes (bumps patch version)
- `feat!:` or `BREAKING CHANGE:` - Breaking changes (bumps major version)

Version is tracked in `VERSION` file.

## Git Commit Format

See root `CLAUDE.md` — no AI attribution in commits.

## Key Files

| File | Purpose |
|------|---------|
| `plugins/reflex/.claude-plugin/plugin.json` | Plugin manifest |
| `plugins/reflex/mcp-catalog.json` | MCP server catalog (registry) |
| `plugins/reflex/hooks/hooks.json` | Hook configurations |
| `plugins/reflex/CLAUDE.md` | Plugin-specific instructions for Claude |
