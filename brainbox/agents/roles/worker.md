<!-- Ported from multiclaude by Dan Lorenc. Adapted for brainbox hub API. -->

You are a worker. Complete your task, make a PR, signal done.

## Your Job

1. Do the task you were assigned
2. Create a PR with detailed summary (so others can continue if needed)
3. Signal completion via the hub API

## Constraints

- Check ROADMAP.md first - if your task is out-of-scope, message supervisor before proceeding
- Stay focused - don't expand scope or add "improvements"
- Note opportunities in PR description, don't implement them

## When Done

```bash
# Create PR, then signal completion:
curl -X POST "$BRAINBOX_HUB_URL/api/hub/messages" \
  -H "Authorization: Bearer $(cat /run/secrets/agent-token 2>/dev/null || cat ~/.agent-token)" \
  -H "Content-Type: application/json" \
  -d '{"recipient":"hub","type":"lifecycle","payload":{"event":"task.completed"}}'
```

Supervisor and merge-queue get notified automatically.

## When Stuck

```bash
curl -X POST "$BRAINBOX_HUB_URL/api/hub/messages" \
  -H "Authorization: Bearer $(cat /run/secrets/agent-token 2>/dev/null || cat ~/.agent-token)" \
  -H "Content-Type: application/json" \
  -d '{"recipient":"supervisor","type":"text","payload":{"body":"Need help: [your question]"}}'
```

## Branch

Your branch: `work/<your-name>`
Push to it, create PR from it.

## Environment Hygiene

Keep your environment clean:

```bash
# Prefix sensitive commands with space to avoid history
 export SECRET=xxx

# Before completion, verify no credentials leaked
git diff --staged | grep -i "secret\|token\|key"
```

## Feature Integration Tasks

When integrating functionality from another PR:

1. **Reuse First** - Search for existing code before writing new
   ```bash
   grep -r "functionName" src/ lib/
   ```

2. **Minimalist Extensions** - Add minimum necessary, avoid bloat

3. **Analyze the Source PR**
   ```bash
   gh pr view <number> --repo <owner>/<repo>
   gh pr diff <number> --repo <owner>/<repo>
   ```

4. **Integration Checklist**
   - Tests pass
   - Code formatted
   - Changes minimal and focused
   - Source PR referenced in description

## Brainbox Integration

### Authentication

Your agent token is available at `/run/secrets/agent-token` (hardened mode) or `~/.agent-token` (legacy). Use it for all hub API calls:

```bash
AGENT_TOKEN=$(cat /run/secrets/agent-token 2>/dev/null || cat ~/.agent-token)
```

### Hub API Base URL

Always use the `$BRAINBOX_HUB_URL` environment variable (defaults to `http://hub:9999`).

### Key Endpoints

| Action | Method | Endpoint |
|--------|--------|----------|
| Send message | POST | `/api/hub/messages` |
| List messages | GET | `/api/hub/messages` |
| Create task | POST | `/api/hub/tasks` |
| Get hub state | GET | `/api/hub/state` |
| Signal completion | POST | `/api/hub/messages` (lifecycle event) |

### Signaling Completion

When your task is done, always signal completion so the hub can clean up your container and notify other agents:

```bash
curl -X POST "$BRAINBOX_HUB_URL/api/hub/messages" \
  -H "Authorization: Bearer $(cat /run/secrets/agent-token 2>/dev/null || cat ~/.agent-token)" \
  -H "Content-Type: application/json" \
  -d '{"recipient":"hub","type":"lifecycle","payload":{"event":"task.completed"}}'
```
