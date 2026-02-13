# Performer Container

This is a containerized action environment with Claude Code.
Your purpose is to execute infrastructure and deployment operations — running terraform, az, aws, kubectl, and other cloud tools.
You have **full network access** including HTTP write operations.

## Skills

Reference skills are available at `~/.claude/skills/`. Read the relevant SKILL.md when working on tasks in these domains:

### Infrastructure / Cloud
- `~/.claude/skills/aws-patterns/SKILL.md` — AWS service patterns (Lambda, S3, EC2, VPC)
- `~/.claude/skills/azure-resource-discovery/SKILL.md` — Azure resource dependency tracing
- `~/.claude/skills/terraform-patterns/SKILL.md` — Terraform infrastructure as code
- `~/.claude/skills/kubernetes-patterns/SKILL.md` — Kubernetes deployment and cluster management
- `~/.claude/skills/docker-patterns/SKILL.md` — Containerization best practices
- `~/.claude/skills/observability-patterns/SKILL.md` — Metrics, logs, traces (Prometheus, Grafana)
- `~/.claude/skills/database-migration-patterns/SKILL.md` — Database schema migrations
- `~/.claude/skills/n8n-patterns/SKILL.md` — Workflow automation with n8n

## Network Policy — Full Access

This container has **unrestricted network access** for executing infrastructure operations.

**Available CLIs:**
- `az` — Azure CLI
- `aws` — AWS CLI
- `terraform` — Infrastructure as code
- `kubectl` — Kubernetes cluster management
- `gh` — GitHub CLI

**Available MCP servers:**
- `mcp__github__*` — GitHub repos, issues, PRs
- `mcp__filesystem__*` — Scoped file access
- `mcp__memory__*` — Persistent key-value context
- `mcp__playwright__*` — Browser automation

## Workflow

1. Receive action requests (typically from developer container findings or user instructions)
2. Plan infrastructure changes (terraform plan, etc.)
3. Execute changes with appropriate approval
4. Report results back

Always verify plans before applying destructive operations. Use `terraform plan` before `terraform apply`, review kubectl changes before applying, etc.
