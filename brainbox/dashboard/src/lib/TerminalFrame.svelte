<script>
  import { stopSession } from './api.js';

  let { session, onUpdate } = $props();

  let confirmStop = $state(false);
  let confirmTimeout = null;

  function resetConfirm() {
    if (confirmTimeout) clearTimeout(confirmTimeout);
    confirmStop = false;
  }

  function handleStop(e) {
    e.preventDefault();
    if (confirmStop) {
      resetConfirm();
      stopSession(session.name).then(onUpdate);
      return;
    }
    confirmStop = true;
    confirmTimeout = setTimeout(resetConfirm, 3000);
  }

  let iframeSrc = $derived(session.url);
  let refreshKey = $state(0);

  function refreshFrame(e) {
    e.preventDefault();
    refreshKey++;
  }

  let displayName = $derived(session.name.replace('developer-', ''));
</script>

<div class="frame">
  <div class="frame-bar">
    <span>{displayName}</span>
    <div class="frame-actions">
      <a href={'#'} class="frame-stop" onclick={handleStop}>{confirmStop ? 'stop?' : 'stop'}</a>
      <a href={'#'} onclick={refreshFrame}>refresh</a>
      <a href={session.url} target="_blank">open</a>
    </div>
  </div>
  {#key refreshKey}
    <iframe src={iframeSrc} title={displayName}></iframe>
  {/key}
</div>

<style>
  .frame {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 8px;
    overflow: hidden;
  }
  .frame-bar {
    padding: 10px 16px;
    border-bottom: 1px solid #1e293b;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 13px;
    color: #94a3b8;
  }
  .frame-actions {
    display: flex;
    gap: 12px;
  }
  .frame-bar a {
    color: #f59e0b;
    text-decoration: none;
    font-size: 12px;
  }
  .frame-bar a:hover { text-decoration: underline; }
  iframe {
    width: 100%;
    height: 400px;
    border: none;
    background: #000;
  }
</style>
