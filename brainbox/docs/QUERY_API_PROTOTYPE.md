# Query API Prototype

## Overview

The `/api/sessions/{name}/query` endpoint allows the orchestrator to send prompts to Claude Code running inside containers. This enables fully autonomous development workflows where all work (file editing, testing, commits) happens inside the container against volume-mounted host files.

## Architecture

```
┌──────────────────┐
│   Orchestrator   │
│  (main Claude)   │
└────────┬─────────┘
         │ HTTP POST /api/sessions/{name}/query
         ▼
┌──────────────────────────────────┐
│     Brainbox API (port 8000)     │
│  - Validates session exists      │
│  - Gets container IP address     │
│  - Proxies request to container  │
└────────┬─────────────────────────┘
         │ HTTP POST http://{container_ip}:9000/query
         ▼
┌──────────────────────────────────┐
│  Container API Server (port 9000)│
│  (brainbox.container_api)        │
│  - Wraps Claude CLI              │
│  - Executes in working_dir       │
│  - Returns output + metadata     │
└────────┬─────────────────────────┘
         │ subprocess
         ▼
┌──────────────────────────────────┐
│      Claude CLI in container     │
│  - Operates on mounted files     │
│  - Has access to container tools │
│  - Uses container's skills       │
└──────────────────────────────────┘
```

## Volume Mount Flow

```
Host: /Users/you/myproject
  ↓ (docker volume mount)
Container: /home/developer/workspace/myproject
  ↓ (Claude CLI operates here)
Claude edits: /home/developer/workspace/myproject/src/foo.py
  ↓ (volume mount persists)
Host sees changes immediately at: /Users/you/myproject/src/foo.py
```

## API Endpoints

### Brainbox API: `/api/sessions/{name}/query`

**Request:**
```json
POST /api/sessions/myproject/query
{
  "prompt": "Run pytest and fix any failing tests",
  "working_dir": "/home/developer/workspace/myproject",
  "timeout": 300,
  "fork_session": false
}
```

**Response:**
```json
{
  "success": true,
  "conversation_id": "abc-123-def",
  "output": "...Claude's response...",
  "error": null,
  "exit_code": 0,
  "duration_seconds": 45.2,
  "files_modified": []
}
```

**Error Codes:**
- `404` - Container not found
- `400` - Container not running
- `503` - Container API server not available (not running on port 9000)
- `504` - Query timed out
- `422` - Validation error (invalid prompt, etc.)

### Container API: `/query` (port 9000)

**Request:**
```json
POST http://{container_ip}:9000/query
{
  "prompt": "Run pytest and fix any failing tests",
  "working_dir": "/home/developer/workspace/myproject",
  "timeout": 300,
  "fork_session": false
}
```

**Response:** Same as above

**Health Check:**
```bash
GET http://{container_ip}:9000/health
```

## Usage Example

### 1. Create Container with Volume Mount

```bash
curl -X POST http://127.0.0.1:8000/api/create \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "myproject",
    "volume": "/Users/you/myproject:/home/developer/workspace/myproject"
  }'
```

### 2. Start Container API Server (Manual - Temporary)

```bash
# Exec into container
docker exec -it developer-myproject bash

# Start container API server
python3 -m brainbox.container_api &

# Verify it's running
curl http://localhost:9000/health
```

### 3. Send Query from Orchestrator

```bash
curl -X POST http://127.0.0.1:8000/api/sessions/myproject/query \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Run pytest tests/, fix any failures, and report results",
    "working_dir": "/home/developer/workspace/myproject",
    "timeout": 300
  }'
```

### 4. Claude Works Inside Container

Claude CLI inside container:
1. Changes to `/home/developer/workspace/myproject`
2. Runs `pytest tests/`
3. Reads test output
4. Uses `Edit` tool on files (e.g., `/home/developer/workspace/myproject/src/api.py`)
5. Runs `pytest tests/` again to verify
6. Returns summary

### 5. Changes Visible on Host

```bash
# On host - changes are immediately visible
git diff  # Shows edits made by in-container Claude
```

## Implementation Status

### ✅ Completed
- [x] Pydantic model: `QuerySessionRequest`
- [x] Brainbox API endpoint: `/api/sessions/{name}/query`
- [x] Container API server: `brainbox.container_api`
- [x] Rate limiting: 5 req/min
- [x] Audit logging
- [x] Error handling and timeouts
- [x] Health check endpoint

### 🚧 In Progress
- [ ] Auto-start container API on container boot
- [ ] File change tracking (report `files_modified`)
- [ ] Conversation thread management
- [ ] Streaming output via SSE

### 🔮 Future Enhancements
- [ ] WebSocket support for real-time streaming
- [ ] Automatic container API installation in Dockerfile
- [ ] Multi-turn conversation tracking
- [ ] Pause/resume support
- [ ] Agent handoff protocol

## Testing

### Unit Tests

```bash
# TODO: Add tests for query endpoint
cd brainbox
just bb-test
```

### Manual Testing

1. Start brainbox API:
   ```bash
   just bb-dashboard
   ```

2. Create test container:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/create \
     -H 'Content-Type: application/json' \
     -d '{"name": "test-query", "volume": "/tmp:/home/developer/workspace"}'
   ```

3. Install brainbox in container and start API:
   ```bash
   docker exec -it developer-test-query bash
   # Inside container:
   pip install /host/path/to/brainbox  # Mount host brainbox
   python3 -m brainbox.container_api &
   ```

4. Test query:
   ```bash
   curl -X POST http://127.0.0.1:8000/api/sessions/test-query/query \
     -H 'Content-Type: application/json' \
     -d '{
       "prompt": "List files in the workspace using ls -la",
       "working_dir": "/home/developer/workspace"
     }'
   ```

## Security Considerations

- **Network Isolation**: Container API only accessible from brainbox API (no external exposure)
- **Rate Limiting**: 5 queries/minute to prevent abuse
- **Timeout Enforcement**: Maximum 1 hour (3600s) per query
- **Audit Logging**: All queries logged with client IP, user agent, success/failure
- **Input Validation**: Pydantic models validate all inputs

## Performance

- **Overhead**: ~100ms proxy latency (brainbox API → container API)
- **Concurrency**: Multiple containers can run queries simultaneously
- **Resource Limits**: Inherits container resource limits (CPU, memory)

## Troubleshooting

### "Container API server not available"

Container API isn't running on port 9000:

```bash
# Check if container is running
docker ps | grep developer-{name}

# Exec into container
docker exec -it developer-{name} bash

# Start container API manually
python3 -m brainbox.container_api &

# Check logs
tail -f /home/developer/.container-api.log
```

### "Query timed out"

Increase timeout or check if Claude CLI is stuck:

```bash
# Inside container
ps aux | grep claude

# Kill stuck process
kill {pid}
```

### "Working directory does not exist"

Ensure volume mount is correct:

```bash
# Check container volumes
docker inspect developer-{name} | jq '.[0].Mounts'
```

## Next Steps

1. **Auto-start container API**: Update Dockerfile to start API on boot
2. **File tracking**: Implement git-based change detection
3. **Conversation management**: Store conversation threads in container
4. **Streaming**: Add SSE support for real-time output
5. **Integration tests**: End-to-end tests with real containers
