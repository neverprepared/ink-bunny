# Code Review Findings
Generated: 2026-02-23

---

## Critical — Security

- [x] #1: `os.system()` with shell-interpolated path allows command injection via special characters in VM path — `brainbox/src/brainbox/backends/utm.py:411` _(fixed: replaced with `subprocess.run(["open", vm_path], capture_output=True)`)_
- [x] #2: Unescaped `working_dir` concatenated into shell command sent via tmux `send-keys` — `brainbox/src/brainbox/container_api.py:104` _(fixed: wrapped with `shlex.quote(request.working_dir)`; added `import shlex`)_

---

## High — Security

- [x] #3: PARTIALLY FIXED — added `require_api_key` to 8 sensitive read endpoints (hub/tasks, hub/tasks/{id}, hub/tokens, hub/state, artifacts list, langfuse traces/summary/trace-detail); updated dashboard `api.js` with `readHeaders()` helper to send key on those calls. Remaining public: sessions list, SSE stream (EventSource can't set headers), health endpoints, hub/agents — `brainbox/src/brainbox/api.py`, `brainbox/dashboard/src/lib/api.js`
- [x] #4: DOCUMENTED — added docstring to `api_get_key` explaining the fail-closed behavior when `request.client` is None, and guidance for proxy deployments. Code is correct as-is for the primary local-dev use case — `brainbox/src/brainbox/api.py:265`
- [x] #5: World-readable profile cache file warnings are logged but not enforced — `brainbox/src/brainbox/lifecycle.py:96-102,307-313` _(fixed: added `cache_env.chmod(0o600)` in both `_read_profile_cache_env()` and `_read_profile_env_content()` immediately after the warning log)_
- [x] #6: World-writable agent YAML warnings are logged but not enforced; allows unprivileged modification of agent definitions — `brainbox/src/brainbox/registry.py:41-45` _(fixed: added `f.chmod(mode & ~stat.S_IWOTH)` inside the existing world-writable detection branch to strip the world-write bit in place)_

---

## High — Duplications

- [ ] #7: DEFERRED — docker.py and utm.py patterns are remote exec strings (exec_run/SSH), not local Python; they cannot share a function. hub.py's pattern is a correct 2-line atomic write (tmp+rename). No useful refactoring available without significant redesign — `brainbox/src/brainbox/backends/docker.py:237-239,256-258`, `backends/utm.py:550`, `hub.py:87`
- [ ] #8: DEFERRED — scripts have divergent error-handling philosophies (ingest.py raises on failure; qdrant-websearch-store.py is fail-open with bare except pass). Extracting a shared util would couple them and risk breaking the fail-open hook design. Duplication is intentional — `reflex/plugins/reflex/scripts/ingest.py:540-579`, `reflex/plugins/reflex/scripts/qdrant-websearch-store.py:363-396`

---

## Medium — Quality

- [x] #9: `_query_via_tmux()` is 175 lines — complex state + polling logic, difficult to test — `brainbox/src/brainbox/api.py:833` _(fixed: extracted `_tmux_verify_container()`, `_tmux_send_and_wait()`, `_tmux_parse_output()` helpers; `_query_via_tmux()` is now an orchestrator)_
- [x] #10: `query()` is 174 lines — `brainbox/src/brainbox/container_api.py:55` _(fixed: extracted `_prepare_working_dir()`, `_build_claude_command()`, `_run_and_capture()`, `_format_query_response()` helpers)_
- [ ] #11: `provision()` is 179 lines — `brainbox/src/brainbox/backends/utm.py:254`
- [ ] #12: `configure()` is 168 lines — `brainbox/src/brainbox/backends/utm.py:434`
- [x] #13: `_resolve_profile_mounts()` is 132 lines — `brainbox/src/brainbox/lifecycle.py:129` _(fixed: extracted `_compute_mount_context()` and `_build_volume_map()` helpers)_
- [x] #14: Silent `except Exception: pass` in task completion routing — silently drops completed tasks — `brainbox/src/brainbox/api.py:1205` _(fixed: replaced with `log.warning("hub.task_completion_error", ...)`)_
- [x] #15: Silent `except Exception: pass` in Docker event watcher — hides stream errors — `brainbox/src/brainbox/api.py:159,164` _(fixed: replaced with `log.warning("docker.events.watcher_error", ...)`)_
- [x] #16: PARTIALLY FIXED — broad `except Exception` clauses in utm.py replaced with structured `log.debug`/`log.warning`; daemon.py, artifacts.py, langfuse_client.py not yet addressed — multiple files
- [ ] #17: TODO: git-based modified-file detection not implemented — `brainbox/src/brainbox/api.py:999`, `brainbox/src/brainbox/container_api.py:214`
- [x] #18: SA token passed via environment variable; visible to privileged processes and subprocess env dicts — `brainbox/src/brainbox/secrets.py:32,50,96` _(documented: added docstring to `_op_run()` warning that SA token is visible in subprocess env dict)_
- [x] #19: Secure file write pattern (`mkdir + write + chmod 0o600`) duplicated in auth.py and manage_secrets.py — `brainbox/src/brainbox/auth.py:25-29`, `manage_secrets.py:121` _(fixed: extracted `write_secure_file(path, content, mode=0o600)` in auth.py; manage_secrets.py now imports and uses it)_

---

## Low — Optimizations

- [x] #20: PARTIALLY FIXED — blocking `read_text()` in lifecycle.py wrapped with `run_in_executor`; utm.py and hub.py not yet addressed — `brainbox/src/brainbox/lifecycle.py:109,325`, `backends/utm.py:230-231,325-326,838-839`, `hub.py:96,101`
- [x] #21: N+1 pattern: `_get_container_metrics()` calls `c.stats(stream=False)` + LangFuse HTTP request individually per container — `brainbox/src/brainbox/api.py:1053-1106` _(fixed: stats calls now run concurrently via `ThreadPoolExecutor(max_workers=min(len(containers), 8))`)_
- [x] #22: Race condition: `_trace_cache` dict mutated without locks in concurrent ThreadPoolExecutor context — `brainbox/src/brainbox/api.py:1014,1040` _(fixed: added `_trace_cache_lock = threading.Lock()`; reads and writes wrapped with `with _trace_cache_lock`)_
- [x] #23: `MetricsTable` polls every 5 s independently instead of subscribing to existing SSE stream — `brainbox/dashboard/src/lib/MetricsTable.svelte:42` _(fixed: replaced `setInterval` with `EventSource` subscription; metrics refresh on Docker events)_
- [ ] #24: DEFERRED — `TraceTimeline` fetches traces per-session in parallel rather than a batched multi-session query — `brainbox/dashboard/src/lib/TraceTimeline.svelte:23-26` _(no batch endpoint exists; comment added noting a future `/api/langfuse/traces?limit=N` endpoint would eliminate the fan-out)_
- [x] #25: `registry.list_tokens()` iterates and rebuilds full token list on every call to expire stale entries — `brainbox/src/brainbox/registry.py:133-136` _(fixed: added `_last_token_sweep` guard; expiry sweep runs at most every 60 s or when token count exceeds 100)_
- [x] #26: `_broadcast_sse()` copies the entire queue set on every call (`list(_sse_queues)`) with no backpressure — `brainbox/src/brainbox/api.py:122-133` _(fixed: added `if not _sse_queues: return` short-circuit before snapshot)_
- [x] #27: `cache_env.read_text()` called twice for same file in same module — `brainbox/src/brainbox/lifecycle.py:109,325` _(fixed: extracted `_load_cache_env_text()` helper; both call sites use it)_
- [x] #28: Docker event stream restart uses fixed 1 s sleep with no exponential backoff — `brainbox/src/brainbox/api.py:147-168` _(fixed: replaced with `await asyncio.sleep(min(2**retry, 60))`; retry counter resets on successful stream run)_
- [x] #29: `questionary` and `rich` are main deps but only used in CLI tool `manage_secrets.py`; should be optional/extra group — `brainbox/pyproject.toml` _(fixed: moved to `[project.optional-dependencies] cli = [...]`)_
