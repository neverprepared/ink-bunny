<script>
  import { onMount, onDestroy } from 'svelte';
  import { fetchHubState, connectSSE } from './api.js';

  let hubState = $state(null);
  let eventSource = null;

  async function refresh() {
    try {
      hubState = await fetchHubState();
    } catch { /* noop */ }
  }

  onMount(() => {
    refresh();
    eventSource = connectSSE((data) => {
      try {
        const parsed = JSON.parse(data);
        if (parsed.hub) refresh();
      } catch { /* ignore non-JSON */ }
    });
  });

  onDestroy(() => {
    if (eventSource) eventSource.close();
  });

  let taskCounts = $derived(() => {
    if (!hubState) return { pending: 0, running: 0, completed: 0, total: 0 };
    const tasks = hubState.tasks || [];
    return {
      pending: tasks.filter(t => t.status === 'pending').length,
      running: tasks.filter(t => t.status === 'running').length,
      completed: tasks.filter(t => t.status === 'completed' || t.status === 'cancelled').length,
      total: tasks.length,
    };
  });

  let agentCount = $derived(hubState ? (hubState.agents || []).length : 0);
  let messageCount = $derived(hubState ? (hubState.messages || []).length : 0);
</script>

<div class="hub-section">
  <h3>Hub Activity</h3>

  <div class="hub-stats">
    <div class="hub-stat">
      <span class="hub-stat-value">{taskCounts().total}</span>
      <span class="hub-stat-label">Tasks</span>
    </div>
    <div class="hub-stat">
      <span class="hub-stat-value pending">{taskCounts().pending}</span>
      <span class="hub-stat-label">Pending</span>
    </div>
    <div class="hub-stat">
      <span class="hub-stat-value running">{taskCounts().running}</span>
      <span class="hub-stat-label">Running</span>
    </div>
    <div class="hub-stat">
      <span class="hub-stat-value completed">{taskCounts().completed}</span>
      <span class="hub-stat-label">Done</span>
    </div>
  </div>

  <div class="hub-meta">
    <span>{agentCount} agent{agentCount !== 1 ? 's' : ''} registered</span>
    <span class="sep">&middot;</span>
    <span>{messageCount} message{messageCount !== 1 ? 's' : ''}</span>
  </div>

  {#if hubState && (hubState.agents || []).length > 0}
    <div class="agent-list">
      {#each hubState.agents as agent (agent.name)}
        <span class="agent-tag">{agent.name}</span>
      {/each}
    </div>
  {/if}
</div>

<style>
  .hub-section {
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

  .hub-stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 16px;
  }
  .hub-stat {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }
  .hub-stat-value {
    font-size: 24px;
    font-weight: 600;
    color: #e2e8f0;
  }
  .hub-stat-value.pending { color: #f59e0b; }
  .hub-stat-value.running { color: #3b82f6; }
  .hub-stat-value.completed { color: #10b981; }
  .hub-stat-label {
    font-size: 11px;
    color: #475569;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .hub-meta {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 12px;
  }
  .sep { margin: 0 6px; }

  .agent-list {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
  }
  .agent-tag {
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.2);
    color: #60a5fa;
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
  }
</style>
