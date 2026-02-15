<script>
  import { createSession } from './api.js';
  import { notifications } from './notifications.svelte.js';

  let { existingNames, onClose, onCreate } = $props();

  let name = $state('');
  let role = $state('developer');
  let volume = $state('');
  let query = $state('');
  let llmProvider = $state('claude');
  let llmModel = $state('');
  let ollamaHost = $state('');
  let openTab = $state(false);
  let error = $state('');
  let isCreating = $state(false);

  let sanitized = $derived(name.replace(/ /g, '-').toLowerCase().trim() || 'default');
  let nameExists = $derived(existingNames.includes(sanitized));

  function handleInput(e) {
    name = e.target.value;
    error = '';
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') onClose();
  }

  function handleOverlayClick(e) {
    if (e.target === e.currentTarget) onClose();
  }

  async function handleSubmit() {
    if (nameExists) {
      error = `session "${sanitized}" already seems to exist`;
      return;
    }

    isCreating = true;
    try {
      const data = await createSession({
        name: sanitized,
        role,
        volume,
        query,
        openTab,
        llm_provider: llmProvider,
        llm_model: llmProvider === 'ollama' ? llmModel : '',
        ollama_host: llmProvider === 'ollama' ? ollamaHost : '',
      });

      if (data.success) {
        notifications.success(`Created session: ${sanitized}`);
        if (openTab && data.url) window.open(data.url, '_blank');
        onClose();
        onCreate();
      } else {
        error = data.error || 'Failed to create session';
        notifications.error(`Failed to create session: ${error}`);
      }
    } catch (err) {
      error = err.message;
      notifications.error(`Failed to create session: ${err.message}`);
    } finally {
      isCreating = false;
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<!-- svelte-ignore a11y_click_events_have_key_events -->
<!-- svelte-ignore a11y_no_static_element_interactions -->
<div class="modal-overlay" onclick={handleOverlayClick}>
  <div class="modal">
    <h2>new session</h2>
    <p class="modal-subtitle">each session runs in its own isolated container</p>

    <div class="modal-field">
      <label for="session-name">session name</label>
      <input
        type="text"
        id="session-name"
        placeholder="default"
        value={name}
        oninput={handleInput}
        class:error={nameExists || error}
      />
      <p class="modal-hint" class:error={nameExists || error}>
        {#if nameExists}
          session "{sanitized}" already seems to exist
        {:else if error}
          {error}
        {:else}
          use a unique name to create a new session
        {/if}
      </p>
    </div>

    <div class="modal-field">
      <label for="session-role">role</label>
      <select id="session-role" bind:value={role}>
        <option value="developer">developer</option>
        <option value="researcher">researcher</option>
        <option value="performer">performer</option>
      </select>
      <p class="modal-hint">
        {#if role === 'developer'}
          general development — read-only HTTP, full git access
        {:else if role === 'researcher'}
          research only — Qdrant read/write, web search, no HTTP writes
        {:else}
          infrastructure actions — full network access, cloud CLIs
        {/if}
      </p>
    </div>

    <div class="modal-field">
      <label for="session-provider">llm provider</label>
      <select id="session-provider" bind:value={llmProvider}>
        <option value="claude">claude (anthropic api)</option>
        <option value="ollama">ollama (local)</option>
      </select>
      <p class="modal-hint">
        {#if llmProvider === 'claude'}
          uses Anthropic API — requires valid API key
        {:else}
          uses a local Ollama instance — data stays on your network
        {/if}
      </p>
    </div>

    {#if llmProvider === 'ollama'}
      <div class="modal-field">
        <label for="session-model">model</label>
        <input type="text" id="session-model" placeholder="qwen3-coder (default)" bind:value={llmModel} />
        <p class="modal-hint">recommended: qwen3-coder, glm-4.7, deepseek-r1</p>
      </div>

      <div class="modal-field">
        <label for="session-ollama-host">ollama host</label>
        <input type="text" id="session-ollama-host" placeholder="http://host.docker.internal:11434 (default)" bind:value={ollamaHost} />
        <p class="modal-hint">override if Ollama runs on a different host</p>
      </div>
    {/if}

    <div class="modal-field">
      <label for="session-volume">volume mount</label>
      <input type="text" id="session-volume" placeholder="~/myproject:/home/developer/myproject" bind:value={volume} />
    </div>

    <div class="modal-field">
      <label for="session-query">initial query</label>
      <input type="text" id="session-query" placeholder="Research topic X..." bind:value={query} />
    </div>

    <div class="modal-field-checkbox">
      <input type="checkbox" id="session-open-tab" bind:checked={openTab} />
      <label for="session-open-tab">open in new tab</label>
    </div>

    <div class="modal-actions">
      <button class="modal-cancel" onclick={onClose} disabled={isCreating}>cancel</button>
      <button class="modal-submit" onclick={handleSubmit} disabled={isCreating}>
        {isCreating ? 'creating...' : 'create'}
      </button>
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
    margin-bottom: 6px;
    color: #e2e8f0;
  }
  .modal-subtitle {
    font-size: 13px;
    color: #64748b;
    margin-bottom: 24px;
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
    transition: border-color 0.15s;
  }
  .modal-field input[type="text"]:focus {
    outline: none;
    border-color: #3b82f6;
  }
  .modal-field input[type="text"]::placeholder { color: #374151; }
  .modal-field input[type="text"].error { border-color: #ef4444; }
  .modal-field select {
    width: 100%;
    padding: 10px 12px;
    background: #0a0e1a;
    border: 1px solid #1e293b;
    border-radius: 6px;
    color: #e2e8f0;
    font-family: inherit;
    font-size: 14px;
    cursor: pointer;
    appearance: auto;
  }
  .modal-field select:focus { outline: none; border-color: #3b82f6; }

  .modal-hint {
    font-size: 11px;
    color: #64748b;
    margin-top: 4px;
  }
  .modal-hint.error { color: #f87171; }

  .modal-field-checkbox {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
  }
  .modal-field-checkbox input[type="checkbox"] {
    width: 16px;
    height: 16px;
    accent-color: #3b82f6;
    color-scheme: dark;
  }
  .modal-field-checkbox label {
    font-size: 14px;
    color: #e2e8f0;
    cursor: pointer;
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
