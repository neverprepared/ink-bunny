<script>
  import { createSession } from './api.js';
  import { notifications } from './notifications.svelte.js';
  import Modal from './Modal.svelte';
  import { onMount } from 'svelte';

  let { existingNames, onClose, onCreate } = $props();

  let name = $state('');
  let role = $state('developer');
  let volume = $state('');
  let query = $state('');
  let llmProvider = $state('claude');
  let llmModel = $state('');
  let ollamaHost = $state('');
  let backend = $state('docker');
  let vmTemplate = $state('brainbox-macos-template');
  let openTab = $state(false);
  let error = $state('');
  let isCreating = $state(false);

  let modalElement;
  let previousActiveElement;

  let sanitized = $derived(name.replace(/ /g, '-').toLowerCase().trim() || 'default');
  let nameExists = $derived(existingNames.includes(sanitized));

  onMount(() => {
    previousActiveElement = document.activeElement;
    const firstInput = modalElement?.querySelector('input');
    if (firstInput) firstInput.focus();

    return () => {
      if (previousActiveElement) previousActiveElement.focus();
    };
  });

  function handleInput(e) {
    name = e.target.value;
    error = '';
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
        backend,
        vm_template: backend === 'utm' ? vmTemplate : null,
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

<Modal {onClose}>
  {#snippet children()}
    <div bind:this={modalElement}>
      <h2 id="modal-title">new session</h2>
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
      <label for="session-backend">backend</label>
      <select id="session-backend" bind:value={backend}>
        <option value="docker">docker container</option>
        <option value="utm">UTM macOS VM</option>
      </select>
      <p class="modal-hint">
        {#if backend === 'docker'}
          Linux container — fast, lightweight, web terminal access
        {:else}
          macOS VM via UTM — for Xcode/iOS development, SSH access only
        {/if}
      </p>
    </div>

    {#if backend === 'utm'}
      <div class="modal-field">
        <label for="session-vm-template">VM template</label>
        <input type="text" id="session-vm-template" placeholder="brainbox-macos-template (default)" bind:value={vmTemplate} />
        <p class="modal-hint">name of the golden image VM in UTM to clone</p>
      </div>
    {/if}

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
  {/snippet}
</Modal>

