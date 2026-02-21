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
  let expandedSessions = $state(new Set());
  let activeProfile = $state(null);

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

  function toggleTerminal(sessionName) {
    const newExpanded = new Set(expandedSessions);
    if (newExpanded.has(sessionName)) {
      newExpanded.delete(sessionName);
    } else {
      newExpanded.add(sessionName);
    }
    expandedSessions = newExpanded;
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

  // Group sessions by profile
  let profiles = $derived([...new Set(sessions.map(s => s.workspace_profile || '').filter(p => p))].sort());

  // Set active profile to first available if not set or if current profile has no sessions
  $effect(() => {
    if (profiles.length > 0 && (!activeProfile || !profiles.includes(activeProfile))) {
      activeProfile = profiles[0];
    }
  });

  // Filter sessions by active profile
  let filteredSessions = $derived(
    activeProfile ? sessions.filter(s => s.workspace_profile === activeProfile) : sessions
  );

  let activeSessions = $derived(filteredSessions.filter(s => s.active));
  let stoppedCount = $derived(filteredSessions.length - activeSessions.length);
  // Only show terminal frames for Docker sessions (UTM uses SSH)
  let dockerSessions = $derived(activeSessions.filter(s => (s.backend || 'docker') === 'docker'));
  let ports = $derived(activeSessions.map(s => s.port).filter(Boolean).map(Number));
  let portRange = $derived(
    ports.length === 0 ? '\u2014' :
    ports.length === 1 ? String(ports[0]) :
    `${Math.min(...ports)}\u2013${Math.max(...ports)}`
  );
</script>

<header>
  <h1><span class="accent">containers</span></h1>
  <button class="new-btn" onclick={() => showNewModal = true} aria-label="Create new session">+ new session</button>
</header>

{#if sessions.length === 0}
  <EmptyState {tip} />
{:else}
  {#if profiles.length > 0}
    <div class="profile-tabs">
      {#each profiles as profile}
        <button
          class="profile-tab"
          class:active={activeProfile === profile}
          onclick={() => activeProfile = profile}
          aria-label={`Switch to ${profile.toUpperCase()} profile`}
        >
          {profile.toUpperCase()}
        </button>
      {/each}
    </div>
  {/if}
  <StatsGrid
    total={filteredSessions.length}
    active={activeSessions.length}
    stopped={stoppedCount}
    {portRange}
  />

  <div class="session-grid">
    {#each filteredSessions as session (session.name)}
      <div class="session-container">
        <SessionCard
          {session}
          onUpdate={handleSessionUpdate}
          onInfo={(name) => infoSession = name}
          isExpanded={expandedSessions.has(session.name)}
          onToggleTerminal={() => toggleTerminal(session.name)}
          showTerminalToggle={session.active && (session.backend || 'docker') === 'docker'}
        />
        {#if expandedSessions.has(session.name) && session.active && (session.backend || 'docker') === 'docker'}
          <div class="terminal-container">
            <TerminalFrame {session} onUpdate={handleSessionUpdate} />
          </div>
        {/if}
      </div>
    {/each}
  </div>
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

  .profile-tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
    border-bottom: 1px solid var(--color-border-primary);
    padding-bottom: 2px;
  }

  .profile-tab {
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    color: var(--color-text-muted);
    padding: 8px 16px;
    cursor: pointer;
    font-family: inherit;
    font-size: 13px;
    font-weight: 500;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    transition: all 0.2s;
    position: relative;
    bottom: -2px;
  }

  .profile-tab:hover {
    color: var(--color-text-primary);
    border-bottom-color: rgba(245, 158, 11, 0.3);
  }

  .profile-tab.active {
    color: #f59e0b;
    border-bottom-color: #f59e0b;
  }

  .session-grid {
    display: grid;
    grid-template-columns: 1fr;
    gap: 16px;
    margin-bottom: 24px;
  }

  .session-container {
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 100%;
    overflow: hidden;
  }

  .terminal-container {
    width: 100%;
    max-height: 500px;
    overflow: hidden;
    animation: slideDown 0.2s ease-out;
  }

  @keyframes slideDown {
    from {
      opacity: 0;
      transform: scaleY(0);
    }
    to {
      opacity: 1;
      transform: scaleY(1);
    }
  }

  .attribution {
    text-align: center;
    padding: 24px 0 8px;
    font-size: 11px;
    color: #64748b;
  }
  .attribution a {
    color: #f59e0b;
    text-decoration: none;
  }
  .attribution a:hover { text-decoration: underline; }
</style>
