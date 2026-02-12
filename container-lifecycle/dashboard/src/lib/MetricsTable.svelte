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
          <th>CPU</th>
          <th>Memory</th>
          <th>Uptime</th>
        </tr>
      </thead>
      <tbody>
        {#each metrics as m (m.name)}
          <tr>
            <td class="name">{m.name.replace('developer-', '')}</td>
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
</style>
