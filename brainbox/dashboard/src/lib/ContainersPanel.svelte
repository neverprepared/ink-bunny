<script>
  import { onMount, onDestroy } from 'svelte';
  import { fetchSessions, connectSSE } from './api.js';
  import { notifications } from './notifications.svelte.js';
  import StatsGrid from './StatsGrid.svelte';
  import SessionCard from './SessionCard.svelte';
  import TerminalFrame from './TerminalFrame.svelte';
  import NewSessionModal from './NewSessionModal.svelte';
  import SessionInfoModal from './SessionInfoModal.svelte';
  import EmptyState from './EmptyState.svelte';

  let sessions = $state([]);
  let showNewModal = $state(false);
  let infoSession = $state(null);
  let eventSource = null;

  const DOCKER_EVENTS = ['create', 'start', 'stop', 'die', 'destroy'];
  const TIPS = [
    'in a session, press q or scroll to the bottom to exit scroll mode and resume typing',
    'on this dashboard, press tab and enter to quickly create a new session',
    'run manage-secrets to manage environment variables',
  ];
  const tip = TIPS[Math.floor(Math.random() * TIPS.length)];

  async function refresh() {
    try {
      sessions = await fetchSessions();
    } catch (err) {
      // Only show error on explicit user actions, not on background SSE refreshes
      console.error('Failed to fetch sessions:', err);
    }
  }

  function handleSessionUpdate() {
    refresh();
  }

  onMount(async () => {
    await refresh();
    eventSource = connectSSE((data) => {
      if (DOCKER_EVENTS.includes(data)) {
        refresh();
      } else {
        try {
          const parsed = JSON.parse(data);
          if (parsed.hub) refresh();
        } catch { /* plain text event, ignore */ }
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
  <h1><span class="accent">containers</span></h1>
  <button class="new-btn" onclick={() => showNewModal = true}>+ new session</button>
</header>

{#if sessions.length === 0}
  <EmptyState {tip} />
{:else}
  <StatsGrid
    total={sessions.length}
    active={activeSessions.length}
    stopped={stoppedCount}
    {portRange}
  />

  <div class="session-grid">
    {#each sessions as session (session.name)}
      <SessionCard
        {session}
        onUpdate={handleSessionUpdate}
        onInfo={(name) => infoSession = name}
      />
    {/each}
  </div>

  {#if activeSessions.length > 0}
    <div class="frames" class:single={activeSessions.length === 1}>
      {#each activeSessions as session (session.name)}
        <TerminalFrame {session} onUpdate={handleSessionUpdate} />
      {/each}
    </div>
  {/if}
{/if}

{#if showNewModal}
  <NewSessionModal
    existingNames={sessions.map(s => s.session_name || s.name)}
    onClose={() => showNewModal = false}
    onCreate={handleSessionUpdate}
  />
{/if}

{#if infoSession}
  <SessionInfoModal
    name={infoSession}
    onClose={() => infoSession = null}
  />
{/if}

<footer class="attribution">
  dashboard inspired by <a href="https://github.com/ykdojo/safeclaw" target="_blank">safeclaw</a> by <a href="https://github.com/ykdojo" target="_blank">ykdojo</a>
</footer>

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

  .new-btn {
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.3);
    color: #3b82f6;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-family: inherit;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.15s;
  }
  .new-btn:hover {
    background: rgba(59, 130, 246, 0.2);
    border-color: #3b82f6;
  }

  .session-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }
  @media (max-width: 768px) {
    .session-grid { grid-template-columns: 1fr; }
  }

  .frames {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }
  .frames.single { grid-template-columns: 1fr; }
  @media (max-width: 900px) {
    .frames { grid-template-columns: 1fr; }
  }

  .attribution {
    text-align: center;
    padding: 24px 0 8px;
    font-size: 11px;
    color: #475569;
  }
  .attribution a {
    color: #f59e0b;
    text-decoration: none;
  }
  .attribution a:hover { text-decoration: underline; }
</style>
