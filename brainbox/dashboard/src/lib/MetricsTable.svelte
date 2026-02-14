<script>
  import { onMount, onDestroy } from 'svelte';
  import { fetchContainerMetrics } from './api.js';

  let metrics = $state([]);
  let timer = null;

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
    try {
      metrics = await fetchContainerMetrics();
    } catch { /* noop */ }
  }

  onMount(() => {
    poll();
    timer = setInterval(poll, 5000);
  });

  onDestroy(() => {
    if (timer) clearInterval(timer);
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
          <th>LLM</th>
          <th>CPU</th>
          <th>Memory</th>
          <th>Uptime</th>
        </tr>
      </thead>
      <tbody>
        {#each metrics as m (m.name)}
          <tr>
            <td class="name">{m.session_name || m.name}</td>
            <td class="role-cell"><span class="role-badge" data-role={m.role || 'developer'}>{m.role || 'developer'}</span></td>
            <td class="llm-cell"><span class="llm-badge" data-visibility={m.llm_provider === 'ollama' ? 'private' : 'public'}>{m.llm_provider === 'ollama' ? 'private' : 'public'}</span></td>
            <td class="num">{m.cpu_percent.toFixed(1)}%</td>
            <td class="num">{m.mem_usage_human} / {m.mem_limit_human}</td>
            <td class="num">{formatUptime(m.uptime_seconds)}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</div>

<style>
  .metrics-section {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 20px;
  }
  h3 {
    font-size: 14px;
    font-weight: 600;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 16px;
  }
  .empty {
    color: #475569;
    font-size: 14px;
  }
  .metrics-table {
    width: 100%;
    border-collapse: collapse;
  }
  th {
    text-align: left;
    font-size: 11px;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 8px 12px;
    border-bottom: 1px solid #1e293b;
  }
  td {
    padding: 10px 12px;
    font-size: 14px;
    border-bottom: 1px solid rgba(30, 41, 59, 0.5);
  }
  .name {
    color: #e2e8f0;
    font-weight: 500;
  }
  .num {
    color: #94a3b8;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    font-size: 13px;
  }
  .role-cell { padding: 10px 12px; }
  .role-badge {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
  }
  .role-badge[data-role="developer"] { background: rgba(59, 130, 246, 0.15); color: #3b82f6; }
  .role-badge[data-role="researcher"] { background: rgba(168, 85, 247, 0.15); color: #a855f7; }
  .role-badge[data-role="performer"] { background: rgba(249, 115, 22, 0.15); color: #f97316; }
  .llm-cell { padding: 10px 12px; }
  .llm-badge {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.02em;
    font-weight: 500;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
  }
  .llm-badge[data-visibility="public"] { background: rgba(236, 72, 153, 0.15); color: #ec4899; }
  .llm-badge[data-visibility="private"] { background: rgba(34, 197, 94, 0.15); color: #22c55e; }
</style>
