"""In-container API server that wraps Claude Code CLI.

This runs inside brainbox containers on port 9000 and provides an HTTP
interface for the orchestrator to send prompts to the in-container Claude
Code instance.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import shlex
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Brainbox Container API", version="0.1.0")


class QueryRequest(BaseModel):
    """Request to execute a Claude Code query."""

    prompt: str = Field(..., description="Prompt to send to Claude Code")
    working_dir: str | None = Field(None, description="Working directory")
    timeout: int = Field(300, ge=10, le=3600)
    fork_session: bool = Field(False, description="Fork a new conversation")


class QueryResponse(BaseModel):
    """Response from Claude Code query execution."""

    success: bool
    conversation_id: str
    output: str
    error: str | None = None
    exit_code: int
    duration_seconds: float
    files_modified: list[str] = Field(default_factory=list)


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "brainbox-container-api",
        "claude_available": _check_claude_available(),
    }


async def _prepare_working_dir(request: QueryRequest) -> str:
    """Resolve and validate the working directory; verify the tmux session is live."""
    working_dir = request.working_dir or os.getcwd()
    if not Path(working_dir).exists():
        raise HTTPException(
            status_code=400, detail=f"Working directory does not exist: {working_dir}"
        )

    session_check = await asyncio.create_subprocess_exec(
        "tmux",
        "has-session",
        "-t",
        "main",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await session_check.wait()

    if session_check.returncode != 0:
        raise HTTPException(
            status_code=503,
            detail="Claude tmux session not found. Is the container running?",
        )

    return working_dir


async def _build_claude_command(request: QueryRequest, working_dir: str) -> int:
    """Prime the tmux session and send the prompt; return the pre-prompt line count."""
    # Clear any existing input in the prompt
    await asyncio.create_subprocess_exec(
        "tmux",
        "send-keys",
        "-t",
        "main",
        "C-c",
    )
    await asyncio.sleep(0.5)

    # Change to working directory if specified
    if request.working_dir:
        cd_cmd = f"cd {shlex.quote(request.working_dir)}"
        await asyncio.create_subprocess_exec(
            "tmux",
            "send-keys",
            "-t",
            "main",
            cd_cmd,
            "Enter",
        )
        await asyncio.sleep(0.5)

    # Capture pane before sending prompt (to compare later)
    before_process = await asyncio.create_subprocess_exec(
        "tmux",
        "capture-pane",
        "-t",
        "main",
        "-p",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    before_output, _ = await before_process.communicate()
    before_line_count = len(before_output.decode("utf-8", errors="replace").splitlines())

    # Send prompt to tmux session
    await asyncio.create_subprocess_exec(
        "tmux",
        "send-keys",
        "-t",
        "main",
        request.prompt,
        "Enter",
    )

    return before_line_count


async def _run_and_capture(before_line_count: int, timeout: int) -> str:
    """Poll the tmux pane until output stabilises; return the final pane text."""
    stable_count = 0
    last_line_count = before_line_count
    max_wait = timeout
    waited = 0
    poll_interval = 1.0

    while waited < max_wait:
        await asyncio.sleep(poll_interval)
        waited += poll_interval

        # Capture current pane content
        capture_process = await asyncio.create_subprocess_exec(
            "tmux",
            "capture-pane",
            "-t",
            "main",
            "-p",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        current_output, _ = await capture_process.communicate()
        current_lines = current_output.decode("utf-8", errors="replace").splitlines()
        current_line_count = len(current_lines)

        # Check if output has stabilized (no new lines for 3 polls)
        # Also check for the prompt character "❯" indicating Claude is ready
        last_line = current_lines[-1] if current_lines else ""

        if current_line_count == last_line_count and "❯" in last_line:
            stable_count += 1
            if stable_count >= 3:  # Stable for 3 seconds
                break
        else:
            stable_count = 0
            last_line_count = current_line_count

    if waited >= max_wait:
        raise HTTPException(
            status_code=408,
            detail=f"Query execution timed out after {timeout}s",
        )

    # Capture final output
    final_process = await asyncio.create_subprocess_exec(
        "tmux",
        "capture-pane",
        "-t",
        "main",
        "-p",
        "-S",
        "-100",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    final_output, _ = await final_process.communicate()
    return final_output.decode("utf-8", errors="replace")


def _format_query_response(
    output: str,
    prompt: str,
    conversation_id: str,
    start_time: datetime,
) -> QueryResponse:
    """Parse the raw pane capture and build the response model."""
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()

    # Extract just the response part (after the prompt)
    # Look for the prompt line and extract everything after it
    lines = output.splitlines()
    response_lines = []
    found_prompt = False

    for line in lines:
        if prompt in line and "❯" in line:
            found_prompt = True
            continue
        if found_prompt:
            response_lines.append(line)

    cleaned_output = "\n".join(response_lines).strip()

    # TODO: Parse git status to detect modified files
    files_modified = []

    return QueryResponse(
        success=True,
        conversation_id=conversation_id,
        output=cleaned_output or output,  # Fallback to full output if parsing fails
        error=None,
        exit_code=0,
        duration_seconds=duration,
        files_modified=files_modified,
    )


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Execute a Claude Code query via tmux and return results.

    This endpoint:
    1. Sends prompt to the running Claude instance in tmux session "main"
    2. Waits for Claude to process the request
    3. Captures output from the tmux pane
    4. Returns results to the orchestrator
    """
    conversation_id = str(uuid.uuid4())
    start_time = datetime.now(timezone.utc)

    working_dir = await _prepare_working_dir(request)

    try:
        before_line_count = await _build_claude_command(request, working_dir)
        output = await _run_and_capture(before_line_count, request.timeout)
        return _format_query_response(output, request.prompt, conversation_id, start_time)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query execution failed: {e}")


def _check_claude_available() -> bool:
    """Check if Claude CLI is available."""
    try:
        result = subprocess.run(["which", "claude"], capture_output=True, text=True, timeout=5)
        return result.returncode == 0
    except Exception:
        return False


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("CONTAINER_API_PORT", "9000"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
