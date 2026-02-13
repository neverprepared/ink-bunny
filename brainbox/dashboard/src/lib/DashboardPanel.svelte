<script>
  import { onMount, onDestroy } from 'svelte';
  import { fetchSessions, connectSSE } from './api.js';
  import StatsGrid from './StatsGrid.svelte';
  import MetricsTable from './MetricsTable.svelte';
  import HubActivity from './HubActivity.svelte';

  let sessions = $state([]);
  let eventSource = null;

  const DOCKER_EVENTS = ['create', 'start', 'stop', 'die', 'destroy'];

  async function refresh() {
    try {
      sessions = await fetchSessions();
    } catch { /* noop */ }
  }

  onMount(() => {
    refresh();
    eventSource = connectSSE((data) => {
      if (DOCKER_EVENTS.includes(data)) {
        refresh();
      } else {
        try {
          const parsed = JSON.parse(data);
          if (parsed.hub) refresh();
        } catch { /* ignore */ }
      }
    });
  });

  onDestroy(() => {
    if (eventSource) eventSource.close();
  });

  let activeSessions = $derived(sessions.filter(s => s.active));
  let stoppedCount = $derived(sessions.length - activeSessions.length);
  let ports = $derived(activeSessions.map(s => s.port).filter(Boolean).map(Number));
  let portRange = $derived(
    ports.length === 0 ? '\u2014' :
    ports.length === 1 ? String(ports[0]) :
    `${Math.min(...ports)}\u2013${Math.max(...ports)}`
  );
</script>

<header>
  <h1><span class="accent">dashboard</span></h1>
</header>

<StatsGrid
  total={sessions.length}
  active={activeSessions.length}
  stopped={stoppedCount}
  {portRange}
/>

<div class="widgets">
  <MetricsTable />
  <HubActivity />
</div>

<style>
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 24px;
  }
  h1 {
    font-size: 22px;
    font-weight: 600;
    color: #e2e8f0;
  }
  .accent { color: #f59e0b; }

  .widgets {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }
  @media (max-width: 900px) {
    .widgets { grid-template-columns: 1fr; }
  }
</style>
