<script>
  import { stopSession, deleteSession, startSession } from './api.js';
  import { notifications } from './notifications.svelte.js';
  import Badge from './Badge.svelte';

  let { session, onUpdate, onInfo } = $props();

  let confirmAction = $state(null); // 'stop' | 'delete' | null
  let confirmTimeout = null;
  let isStarting = $state(false);

  function resetConfirm() {
    if (confirmTimeout) clearTimeout(confirmTimeout);
    confirmAction = null;
  }

  async function handleStop() {
    if (confirmAction === 'stop') {
      resetConfirm();
      try {
        await stopSession(session.name);
        notifications.success(`Stopped session: ${session.session_name || session.name}`);
        onUpdate();
      } catch (err) {
        notifications.error(`Failed to stop session: ${err.message}`);
      }
      return;
    }
    confirmAction = 'stop';
    confirmTimeout = setTimeout(resetConfirm, 3000);
  }

  async function handleDelete() {
    if (confirmAction === 'delete') {
      resetConfirm();
      try {
        await deleteSession(session.name);
        notifications.success(`Deleted session: ${session.session_name || session.name}`);
        onUpdate();
      } catch (err) {
        notifications.error(`Failed to delete session: ${err.message}`);
      }
      return;
    }
    confirmAction = 'delete';
    confirmTimeout = setTimeout(resetConfirm, 3000);
  }

  async function handleStart() {
    isStarting = true;
    try {
      const data = await startSession(session.name);
      if (data.success) {
        notifications.success(`Started session: ${session.session_name || session.name}`);
        onUpdate();
      } else {
        notifications.error('Failed to start session');
      }
    } catch (err) {
      notifications.error(`Failed to start session: ${err.message}`);
    } finally {
      isStarting = false;
    }
  }

  let displayName = $derived(session.session_name || session.name);
  let displayRole = $derived(session.role || 'developer');
  let displayUrl = $derived(session.url ? session.url.replace('http://', '') : '');
  let llmVisibility = $derived(session.llm_provider === 'ollama' ? 'private' : 'public');
  let workspaceProfile = $derived((session.workspace_profile || '').toUpperCase());
  let backend = $derived(session.backend || 'docker');
  let isUTM = $derived(backend === 'utm');
  let sshCommand = $derived(isUTM ? `ssh -p ${session.ssh_port || 2200} developer@localhost` : '');
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<div
  class="session-card"
  class:active={session.active}
  class:inactive={!session.active}
  role="article"
  aria-label={`Session ${displayName}, ${session.active ? 'active' : 'inactive'}, ${displayRole} role, ${llmVisibility} provider`}
  onclick={(e) => { if (!e.target.closest('button, a')) resetConfirm(); }}
  onkeydown={(e) => { if (e.key === 'Escape' && confirmAction) resetConfirm(); }}
>
  <div class="card-header">
    <span class="status-dot" class:active={session.active} aria-label={session.active ? 'Active' : 'Inactive'}></span>
    <a
      href={'#'}
      class="session-name"
      onclick={(e) => { e.preventDefault(); onInfo(session.name); }}
      onkeydown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onInfo(session.name); } }}
      aria-label={`View details for ${displayName}`}
    >{displayName}</a>
    <Badge type="backend" variant={backend} text={isUTM ? 'macOS VM' : 'Container'} />
    <Badge type="role" variant={displayRole} text={displayRole} />
    <Badge type="provider" variant={llmVisibility} text={llmVisibility} />
    {#if workspaceProfile}
      <Badge type="profile" variant="workspace" text={workspaceProfile} />
    {/if}
  </div>

  <div class="card-url">
    {#if session.active}
      {#if isUTM}
        <code class="ssh-command" title="Copy and paste this command to connect via SSH">{sshCommand}</code>
      {:else}
        <a href={session.url} target="_blank" aria-label={`Open ${displayName} in new tab at ${displayUrl}`}>{displayUrl}</a>
      {/if}
    {:else}
      <button class="start-btn" onclick={handleStart} disabled={isStarting} aria-label={`Start session ${displayName}`}>
        {isStarting ? 'starting...' : 'start'}
      </button>
    {/if}
  </div>

  {#if session.volume && session.volume !== '-'}
    <div class="card-detail">
      <span class="card-detail-label">vol</span>
      <span class="card-volume">{session.volume}</span>
    </div>
  {/if}

  <div class="card-actions">
    {#if session.active}
      <button class="stop-btn" onclick={handleStop} aria-label={confirmAction === 'stop' ? `Confirm stop session ${displayName}` : `Stop session ${displayName}`}>
        {confirmAction === 'stop' ? 'stop?' : 'stop'}
      </button>
    {:else}
      <button class="delete-btn" onclick={handleDelete} aria-label={confirmAction === 'delete' ? `Confirm delete session ${displayName}` : `Delete session ${displayName}`}>
        {confirmAction === 'delete' ? 'delete?' : 'delete'}
      </button>
    {/if}
  </div>
</div>

<style>
  .session-card {
    background: var(--color-bg-secondary);
    border: 1px solid var(--color-border-primary);
    border-radius: var(--radius-xl);
    padding: var(--spacing-lg) var(--spacing-xl);
    border-left: 3px solid var(--color-border-primary);
    transition: opacity 0.2s;
  }
  .session-card.active { border-left-color: var(--color-success); }
  .session-card.inactive { opacity: 0.5; }

  .card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: var(--spacing-md);
  }
  .status-dot {
    width: var(--spacing-sm);
    height: var(--spacing-sm);
    border-radius: 50%;
    background: #374151;
    flex-shrink: 0;
  }
  .status-dot.active {
    background: var(--color-success);
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.4);
  }
  .session-name {
    color: var(--color-text-primary);
    text-decoration: none;
    font-weight: 500;
    font-size: 15px;
  }
  .session-name:hover { color: var(--color-accent); }

  .card-url { margin-bottom: 6px; }
  .card-url a {
    color: var(--color-accent);
    text-decoration: none;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    font-size: 12px;
  }
  .card-url a:hover { text-decoration: underline; }

  .ssh-command {
    display: inline-block;
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.3);
    color: #3b82f6;
    padding: 4px 8px;
    border-radius: 4px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    font-size: 11px;
    user-select: all;
    cursor: text;
  }
  .ssh-command:hover {
    background: rgba(59, 130, 246, 0.15);
  }

  .card-detail {
    font-size: 13px;
    color: var(--color-text-tertiary);
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .card-detail-label {
    color: var(--color-text-muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    min-width: 50px;
  }
  .card-volume {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    font-size: 11px;
    color: var(--color-text-muted);
    max-width: 100%;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .card-volume:hover {
    overflow: visible;
    white-space: normal;
    word-break: break-all;
  }

  .card-actions {
    margin-top: var(--spacing-md);
    padding-top: var(--spacing-md);
    border-top: 1px solid var(--color-border-primary);
    display: flex;
    gap: var(--spacing-sm);
  }

  .stop-btn {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: var(--color-error);
    padding: var(--spacing-xs) var(--spacing-md);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    transition: all 0.15s;
  }
  .stop-btn:hover {
    background: rgba(239, 68, 68, 0.2);
    border-color: var(--color-error);
  }
  .delete-btn {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.2);
    color: #f87171;
    padding: var(--spacing-xs) var(--spacing-md);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    transition: all 0.15s;
  }
  .delete-btn:hover {
    background: rgba(239, 68, 68, 0.2);
    border-color: var(--color-error);
  }
  .start-btn {
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.3);
    color: var(--color-success);
    padding: var(--spacing-xs) var(--spacing-md);
    border-radius: var(--radius-md);
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    transition: all 0.15s;
  }
  .start-btn:hover {
    background: rgba(16, 185, 129, 0.2);
    border-color: var(--color-success);
  }
</style>
