<script>
  import { onMount, onDestroy } from 'svelte';
  import { fetchContainerMetrics, connectSSE } from './api.js';
  import Badge from './Badge.svelte';

  let metrics = $state([]);
  let sseConn = null;
  let abortController = null;

  function formatUptime(seconds) {
    if (seconds < 60) return `${seconds}s`;
    const m = Math.floor(seconds / 60);
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    const rm = m % 60;
    if (h < 24) return `${h}h ${rm}m`;
    const d = Math.floor(h / 24);
    const rh = h % 24;
    return `${d}d ${rh}h`;
  }

  async function poll() {
    // Cancel previous request if still in flight
    if (abortController) {
      abortController.abort();
    }

    abortController = new AbortController();

    try {
      metrics = await fetchContainerMetrics(abortController.signal);
    } catch (err) {
      // Ignore AbortError - it's expected when cancelling requests
      if (err.name !== 'AbortError') {
        console.error('Failed to fetch container metrics:', err);
      }
    }
  }

  onMount(() => {
    poll();
    sseConn = connectSSE(() => poll());
  });

  onDestroy(() => {
    if (sseConn) sseConn.close();
    if (abortController) abortController.abort();
  });
</script>

<div class="metrics-section">
  <h3>Container Metrics</h3>
  {#if metrics.length === 0}
    <p class="empty">No running containers</p>
  {:else}
    <table class="metrics-table">
      <thead>
        <tr>
          <th>Container</th>
          <th>Role</th>
          <th>Profile</th>
          <th>LLM</th>
          <th>CPU</th>
          <th>Memory</th>
          <th>Uptime</th>
          <th>Traces</th>
          <th>Errors</th>
        </tr>
      </thead>
      <tbody>
        {#each metrics as m (m.name)}
          <tr>
            <td class="name">{m.session_name || m.name}</td>
            <td class="role-cell"><Badge type="role" variant={m.role || 'developer'} text={m.role || 'developer'} /></td>
            <td class="profile-cell">{#if m.workspace_profile}<Badge type="profile" variant="workspace" text={m.workspace_profile.toUpperCase()} />{:else}<span class="empty-cell">—</span>{/if}</td>
            <td class="llm-cell"><Badge type="provider" variant={m.llm_provider === 'ollama' ? 'private' : 'public'} text={m.llm_provider === 'ollama' ? 'private' : 'public'} /></td>
            <td class="num">{m.cpu_percent.toFixed(1)}%</td>
            <td class="num">{m.mem_usage_human} / {m.mem_limit_human}</td>
            <td class="num">{formatUptime(m.uptime_seconds)}</td>
            <td class="num">{m.trace_count ?? 0}</td>
            <td class="num" class:error-count={m.error_count > 0}>{m.error_count ?? 0}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .metrics-section {
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border-primary);
    border-radius: var(--radius-xl);
    padding: var(--spacing-xl);
  }
  h3 {
    font-size: 14px;
    font-weight: 600;
    color: var(--color-text-secondary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: var(--spacing-lg);
  }
  .empty {
    color: var(--color-text-tertiary);
    font-size: 14px;
  }
  .metrics-table {
    width: 100%;
    border-collapse: collapse;
  }
  th {
    text-align: left;
    font-size: 11px;
    color: var(--color-text-tertiary);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: var(--spacing-sm) var(--spacing-md);
    border-bottom: 1px solid var(--color-border-primary);
  }
  td {
    padding: 10px var(--spacing-md);
    font-size: 14px;
    border-bottom: 1px solid rgba(30, 41, 59, 0.5);
  }
  .name {
    color: var(--color-text-primary);
    font-weight: 500;
  }
  .num {
    color: var(--color-text-secondary);
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    font-size: 13px;
  }
  .role-cell { padding: 10px var(--spacing-md); }
  .llm-cell { padding: 10px var(--spacing-md); }
  .profile-cell { padding: 10px var(--spacing-md); }
  .empty-cell { color: #374151; }
  .error-count { color: var(--color-error); font-weight: 600; }
</style>
