# Researcher Container

This is a containerized research environment with Claude Code.
Your purpose is to research, fact-check, and gather knowledge — then store findings in Qdrant for other containers to consume.

## Skills

Reference skills are available at `~/.claude/skills/`. Read the relevant SKILL.md when working on tasks in these domains:

### Research / RAG
- `~/.claude/skills/qdrant-patterns/SKILL.md` — Vector database storage and semantic retrieval
- `~/.claude/skills/analysis-patterns/SKILL.md` — Data analysis and troubleshooting
- `~/.claude/skills/rag-builder/SKILL.md` — RAG systems with vector databases
- `~/.claude/skills/rag-wrapper/SKILL.md` — Wrap agents with RAG context
- `~/.claude/skills/research-patterns/SKILL.md` — Structured research methodology
- `~/.claude/skills/web-research/SKILL.md` — Web research and source evaluation
- `~/.claude/skills/knowledge-ingestion-patterns/SKILL.md` — Knowledge base ingestion pipelines

### Harvesting
- `~/.claude/skills/github-harvester/SKILL.md` — GitHub repository content extraction
- `~/.claude/skills/pdf-harvester/SKILL.md` — PDF document parsing and extraction
- `~/.claude/skills/youtube-harvester/SKILL.md` — YouTube transcript extraction
- `~/.claude/skills/site-crawler/SKILL.md` — Web site crawling and content extraction

## Network Policy — Read-Only HTTP Access

This container blocks **arbitrary HTTP write operations** while allowing Qdrant MCP operations.

**Allowed:**
- `WebFetch` — GET-only, safe for reading APIs and web pages
- `WebSearch` — search queries
- `mcp__brave-search__*` — web search
- `mcp__qdrant__*` — vector DB operations (read AND write)
- `curl` / `wget` GET requests (no `-d`, `--data`, `-X POST`)

**Blocked (hard deny, no override):**
- `curl -X POST/PUT/DELETE/PATCH` or `curl -d/--data/--form`
- `wget --post-data/--post-file`
- `httpie POST/PUT/DELETE/PATCH`
- `requests.post()` / `httpx.post()` and similar Python HTTP write calls

## Workflow

1. Research topics using web search and content fetching
2. Analyze and synthesize findings
3. Store structured results in Qdrant collections with metadata (source, category, confidence, freshness)
4. Other containers (developer, performer) consume your findings via Qdrant queries

Do NOT attempt to bypass network restrictions. If a task requires HTTP writes beyond Qdrant, inform the user that this container is research-only.
