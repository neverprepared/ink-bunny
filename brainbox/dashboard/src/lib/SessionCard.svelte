<script>
  import { stopSession, deleteSession, startSession } from './api.js';

  let { session, onUpdate, onInfo } = $props();

  let confirmAction = $state(null); // 'stop' | 'delete' | null
  let confirmTimeout = null;

  function resetConfirm() {
    if (confirmTimeout) clearTimeout(confirmTimeout);
    confirmAction = null;
  }

  function handleStop() {
    if (confirmAction === 'stop') {
      resetConfirm();
      stopSession(session.name).then(onUpdate);
      return;
    }
    confirmAction = 'stop';
    confirmTimeout = setTimeout(resetConfirm, 3000);
  }

  function handleDelete() {
    if (confirmAction === 'delete') {
      resetConfirm();
      deleteSession(session.name).then(onUpdate);
      return;
    }
    confirmAction = 'delete';
    confirmTimeout = setTimeout(resetConfirm, 3000);
  }

  async function handleStart() {
    const data = await startSession(session.name);
    if (data.success) onUpdate();
  }

  let displayName = $derived(session.name.replace('developer-', ''));
  let displayUrl = $derived(session.url ? session.url.replace('http://', '') : '');
</script>

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div
  class="session-card"
  class:active={session.active}
  class:inactive={!session.active}
  onclick={(e) => { if (!e.target.closest('button, a')) resetConfirm(); }}
>
  <div class="card-header">
    <span class="status-dot" class:active={session.active}></span>
    <a href={'#'} class="session-name" onclick={(e) => { e.preventDefault(); onInfo(session.name); }}>{displayName}</a>
  </div>

  <div class="card-url">
    {#if session.active}
      <a href={session.url} target="_blank">{displayUrl}</a>
    {:else}
      <button class="start-btn" onclick={handleStart}>start</button>
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
      <button class="stop-btn" onclick={handleStop}>
        {confirmAction === 'stop' ? 'stop?' : 'stop'}
      </button>
    {:else}
      <button class="delete-btn" onclick={handleDelete}>
        {confirmAction === 'delete' ? 'delete?' : 'delete'}
      </button>
    {/if}
  </div>
</div>

<style>
  .session-card {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 16px 20px;
    border-left: 3px solid #1e293b;
    transition: opacity 0.2s;
  }
  .session-card.active { border-left-color: #10b981; }
  .session-card.inactive { opacity: 0.5; }

  .card-header {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 12px;
  }
  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #374151;
    flex-shrink: 0;
  }
  .status-dot.active {
    background: #10b981;
    box-shadow: 0 0 6px rgba(16, 185, 129, 0.4);
  }
  .session-name {
    color: #e2e8f0;
    text-decoration: none;
    font-weight: 500;
    font-size: 15px;
  }
  .session-name:hover { color: #f59e0b; }

  .card-url { margin-bottom: 6px; }
  .card-url a {
    color: #f59e0b;
    text-decoration: none;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    font-size: 12px;
  }
  .card-url a:hover { text-decoration: underline; }

  .card-detail {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 6px;
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .card-detail-label {
    color: #475569;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
    min-width: 50px;
  }
  .card-volume {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    font-size: 11px;
    color: #475569;
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
    margin-top: 12px;
    padding-top: 12px;
    border-top: 1px solid #1e293b;
    display: flex;
    gap: 8px;
  }

  .stop-btn {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #ef4444;
    padding: 4px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    transition: all 0.15s;
  }
  .stop-btn:hover {
    background: rgba(239, 68, 68, 0.2);
    border-color: #ef4444;
  }
  .delete-btn {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.2);
    color: #f87171;
    padding: 4px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    transition: all 0.15s;
  }
  .delete-btn:hover {
    background: rgba(239, 68, 68, 0.2);
    border-color: #ef4444;
  }
  .start-btn {
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.3);
    color: #10b981;
    padding: 4px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-family: inherit;
    font-size: 12px;
    transition: all 0.15s;
  }
  .start-btn:hover {
    background: rgba(16, 185, 129, 0.2);
    border-color: #10b981;
  }
</style>
