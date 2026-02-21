<script>
  import { onMount, onDestroy } from 'svelte';
  import { fetchLangfuseHealth, fetchQdrantHealth, fetchSessions, fetchSessionSummary, connectSSE } from './api.js';
  import TraceTimeline from './TraceTimeline.svelte';
  import ToolBreakdown from './ToolBreakdown.svelte';
  import StatCard from './StatCard.svelte';

  let langfuseHealth = $state({ healthy: false, mode: 'off' });
  let qdrantHealth = $state({ healthy: false, url: null });
  let sessions = $state([]);
  let summaries = $state([]);
  let selectedSession = $state('');
  let eventSource = null;

  const DOCKER_EVENTS = ['create', 'start', 'stop', 'die', 'destroy'];

  async function refreshHealth() {
    try {
      langfuseHealth = await fetchLangfuseHealth();
    } catch { langfuseHealth = { healthy: false, mode: 'unknown' }; }

    try {
      qdrantHealth = await fetchQdrantHealth();
    } catch { qdrantHealth = { healthy: false, url: null }; }
  }

  async function refreshSessions() {
    try {
      const all = await fetchSessions();
      sessions = all.filter(s => s.active);
    } catch { /* noop */ }
  }

  async function refreshSummaries() {
    try {
      const results = await Promise.all(
        activeSessions.map(name =>
          fetchSessionSummary(name).catch(() => ({
            session_id: name,
            total_traces: 0,
            total_observations: 0,
            error_count: 0,
            tool_counts: {},
          }))
        )
      );
      summaries = results;
    } catch { /* noop */ }
  }

  onMount(() => {
    refreshHealth();
    refreshSessions();
    eventSource = connectSSE((data) => {
      if (DOCKER_EVENTS.includes(data)) {
        refreshSessions();
      }
    });
  });

  onDestroy(() => {
    if (eventSource) eventSource.close();
  });

  let activeSessions = $derived(sessions.map(s => s.session_name));

  // Re-fetch summaries when sessions change
  $effect(() => {
    if (activeSessions.length > 0) {
      refreshSummaries();
    } else {
      summaries = [];
    }
  });

  let totalTraces = $derived(summaries.reduce((n, s) => n + (s.total_traces || 0), 0));
  let totalErrors = $derived(summaries.reduce((n, s) => n + (s.error_count || 0), 0));
  let activeCount = $derived(activeSessions.length);
</script>

<header>
  <h1><span class="accent">observability</span></h1>
  {#if activeSessions.length > 0}
    <div class="session-filter">
      <select bind:value={selectedSession}>
        <option value="">All sessions</option>
        {#each activeSessions as name (name)}
          <option value={name}>{name}</option>
        {/each}
      </select>
    </div>
  {/if}
</header>

<div class="stats">
  <StatCard label="LangFuse" value={langfuseHealth.healthy ? 'Connected' : 'Offline'} variant={langfuseHealth.healthy ? 'healthy' : 'unhealthy'} />
  <StatCard label="Qdrant" value={qdrantHealth.healthy ? 'Connected' : 'Offline'} variant={qdrantHealth.healthy ? 'healthy' : 'unhealthy'} />
  <StatCard label="Total Traces" value={totalTraces} />
  <StatCard label="Errors" value={totalErrors} variant={totalErrors > 0 ? 'errors' : 'default'} />
  <StatCard label="Active Sessions" value={activeCount} variant="sessions" />
</div>

<div class="widgets">
  <TraceTimeline sessions={activeSessions} {selectedSession} />
  <ToolBreakdown sessions={selectedSession ? [selectedSession] : activeSessions} />
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

  .session-filter select {
    background: #111827;
    border: 1px solid #1e293b;
    color: #e2e8f0;
    padding: 6px 12px;
    border-radius: 6px;
    font-size: 13px;
    cursor: pointer;
  }
  .session-filter select:focus {
    outline: none;
    border-color: #f59e0b;
  }

  .stats {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }
  @media (max-width: 900px) {
    .stats { grid-template-columns: repeat(3, 1fr); }
  }
  @media (max-width: 600px) {
    .stats { grid-template-columns: repeat(2, 1fr); }
  }

  .widgets {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }
  @media (max-width: 900px) {
    .widgets { grid-template-columns: 1fr; }
  }
</style>
