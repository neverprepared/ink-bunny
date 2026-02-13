<script>
  let { name, onClose } = $props();

  let displayName = $derived(name.replace('developer-', ''));
  let execCmd = $derived(`docker exec -it ${name} tmux attach -t main`);
  let copied = $state(false);

  function handleKeydown(e) {
    if (e.key === 'Escape') onClose();
  }

  function handleOverlayClick(e) {
    if (e.target === e.currentTarget) onClose();
  }

  function copyCmd() {
    navigator.clipboard.writeText(execCmd);
    copied = true;
    setTimeout(() => copied = false, 1500);
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay" onclick={handleOverlayClick}>
  <div class="modal">
    <h2>{displayName}</h2>
    <div class="modal-field">
      <label for="exec-cmd">enter container</label>
      <input type="text" id="exec-cmd" readonly value={execCmd} onclick={(e) => e.target.select()} />
    </div>
    <div class="modal-actions">
      <button class="modal-cancel" onclick={onClose}>close</button>
      <button class="modal-submit" onclick={copyCmd}>{copied ? 'copied' : 'copy'}</button>
    </div>
  </div>
</div>

<style>
  .modal-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0, 0, 0, 0.6);
    backdrop-filter: blur(4px);
    z-index: 100;
    display: flex;
    justify-content: center;
    align-items: center;
  }
  .modal {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 12px;
    padding: 28px;
    min-width: 420px;
    max-width: 90vw;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
  }
  h2 {
    font-size: 18px;
    font-weight: 600;
    margin-bottom: 16px;
    color: #e2e8f0;
  }
  .modal-field { margin-bottom: 16px; }
  .modal-field label {
    display: block;
    font-size: 12px;
    color: #94a3b8;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }
  .modal-field input[type="text"] {
    width: 100%;
    padding: 10px 12px;
    background: #0a0e1a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    color: #e2e8f0;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    font-size: 14px;
  }
  .modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 12px;
    margin-top: 24px;
  }
  .modal-cancel {
    background: transparent;
    border: 1px solid #1e293b;
    color: #94a3b8;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-family: inherit;
    font-size: 14px;
    transition: all 0.15s;
  }
  .modal-cancel:hover { background: #1e293b; color: #e2e8f0; }
  .modal-submit {
    background: #3b82f6;
    border: 1px solid #3b82f6;
    color: #fff;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-family: inherit;
    font-size: 14px;
    font-weight: 500;
    transition: all 0.15s;
  }
  .modal-submit:hover { background: #2563eb; }
</style>
