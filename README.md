# ink-bunny

A monorepo for an agentic development platform:

| Package | Description |
|---------|-------------|
| **[brainbox](brainbox/)** | Sandboxed Docker container orchestration for Claude Code with a web dashboard |
| **[reflex](reflex/)** | Claude Code plugin providing skills, agents, slash commands, and MCP server management |
| **[shell-profiler](shell-profiler/)** | Go CLI for managing workspace-specific environment profiles via direnv |
| **[docker](docker/)** | Container images and Compose configs for brainbox, Qdrant, LangFuse, and MinIO |
| **[docs](docs/)** | Three-phase architectural documentation for the broader agentic platform vision |

## Install

All packages are available via Homebrew:

```bash
brew install neverprepared/ink-bunny/brainbox
brew install neverprepared/ink-bunny/shell-profiler
brew install neverprepared/ink-bunny/reflex
```

Reflex is also available from the Claude Code plugin marketplace:

```
/plugin marketplace add mindmorass/reflex
/plugin install reflex
```

## Development

Requires [Just](https://github.com/casey/just) as the task runner. Run `just` to see all recipes.

```bash
# Brainbox (Python)
just bb-api              # Start FastAPI backend
just bb-test             # Run pytest
just bb-lint             # Run ruff

# Shell Profiler (Go)
just sp-build            # Build Go binary
just sp-test             # Run Go tests
just sp-lint             # Run golangci-lint

# Reflex (Plugin)
just reflex-dev          # Launch Claude Code with local plugin

# Cross-cutting
just test-all            # Run all test suites
just lint-all            # Run all linters
```

## License

MIT
