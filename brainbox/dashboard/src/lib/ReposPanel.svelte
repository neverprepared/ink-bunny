<script>
  import { onMount, onDestroy } from 'svelte';
  import { fetchRepos, addRepo, updateRepo, deleteRepo, connectSSE } from './api.js';
  import Badge from './Badge.svelte';

  let repos = $state([]);
  let loading = $state(true);
  let error = $state(null);
  let showAddForm = $state(false);
  let eventSource = null;

  // Add form state
  let newUrl = $state('');
  let newName = $state('');
  let newMergeQueue = $state(false);
  let newPrShepherd = $state(false);
  let newTargetBranch = $state('main');
  let newIsFork = $state(false);
  let newUpstreamUrl = $state('');
  let adding = $state(false);

  async function refresh() {
    try {
      repos = await fetchRepos();
      error = null;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  async function handleAdd() {
    adding = true;
    try {
      await addRepo({
        url: newUrl,
        name: newName || undefined,
        merge_queue: newMergeQueue,
        pr_shepherd: newPrShepherd,
        target_branch: newTargetBranch,
        is_fork: newIsFork,
        upstream_url: newIsFork ? newUpstreamUrl : undefined,
      });
      showAddForm = false;
      newUrl = '';
      newName = '';
      newMergeQueue = false;
      newPrShepherd = false;
      newTargetBranch = 'main';
      newIsFork = false;
      newUpstreamUrl = '';
      await refresh();
    } catch (e) {
      error = e.message;
    } finally {
      adding = false;
    }
  }

  async function handleToggle(repo, field) {
    try {
      await updateRepo(repo.name, { [field]: !repo[field] });
      await refresh();
    } catch (e) {
      error = e.message;
    }
  }

  async function handleDelete(name) {
    if (!confirm(`Remove repository "${name}"?`)) return;
    try {
      await deleteRepo(name);
      await refresh();
    } catch (e) {
      error = e.message;
    }
  }

  onMount(() => {
    refresh();
    eventSource = connectSSE((data) => {
      try {
        const parsed = JSON.parse(data);
        if (parsed.hub) refresh();
      } catch { /* ignore */ }
    });
  });

  onDestroy(() => {
    if (eventSource) eventSource.close();
  });
</script>

<div class="repos-panel">
  <div class="panel-header">
    <h2>Repositories</h2>
    <button class="btn-add" onclick={() => showAddForm = !showAddForm}>
      {showAddForm ? 'Cancel' : '+ Add Repo'}
    </button>
  </div>

  {#if error}
    <div class="error">{error}</div>
  {/if}

  {#if showAddForm}
    <form class="add-form" onsubmit={(e) => { e.preventDefault(); handleAdd(); }}>
      <label>
        <span>GitHub URL</span>
        <input type="text" bind:value={newUrl} placeholder="https://github.com/owner/repo" required />
      </label>
      <label>
        <span>Name (optional)</span>
        <input type="text" bind:value={newName} placeholder="auto-derived from URL" />
      </label>
      <label>
        <span>Target Branch</span>
        <input type="text" bind:value={newTargetBranch} />
      </label>
      <div class="toggles">
        <label class="toggle">
          <input type="checkbox" bind:checked={newMergeQueue} />
          <span>Merge Queue</span>
        </label>
        <label class="toggle">
          <input type="checkbox" bind:checked={newPrShepherd} />
          <span>PR Shepherd</span>
        </label>
        <label class="toggle">
          <input type="checkbox" bind:checked={newIsFork} />
          <span>Fork</span>
        </label>
      </div>
      {#if newIsFork}
        <label>
          <span>Upstream URL</span>
          <input type="text" bind:value={newUpstreamUrl} placeholder="https://github.com/upstream/repo" />
        </label>
      {/if}
      <button type="submit" class="btn-submit" disabled={adding || !newUrl}>
        {adding ? 'Adding...' : 'Add Repository'}
      </button>
    </form>
  {/if}

  {#if loading}
    <div class="loading">Loading repositories...</div>
  {:else if repos.length === 0}
    <div class="empty">
      <p>No repositories tracked yet.</p>
      <p class="hint">Add a repository to enable merge-queue and PR shepherd agents.</p>
    </div>
  {:else}
    <div class="repo-grid">
      {#each repos as repo (repo.name)}
        <div class="repo-card">
          <div class="repo-header">
            <h3>{repo.name}</h3>
            <button class="btn-delete" onclick={() => handleDelete(repo.name)} title="Remove">x</button>
          </div>
          <div class="repo-url">{repo.url}</div>
          <div class="repo-branch">branch: {repo.target_branch}</div>

          <div class="repo-agents">
            <button
              class="agent-toggle"
              class:active={repo.merge_queue_enabled}
              onclick={() => handleToggle(repo, 'merge_queue_enabled')}
            >
              <Badge variant={repo.merge_queue_enabled ? 'success' : 'muted'}>merge-queue</Badge>
            </button>
            <button
              class="agent-toggle"
              class:active={repo.pr_shepherd_enabled}
              onclick={() => handleToggle(repo, 'pr_shepherd_enabled')}
            >
              <Badge variant={repo.pr_shepherd_enabled ? 'success' : 'muted'}>pr-shepherd</Badge>
            </button>
            {#if repo.is_fork}
              <Badge variant="info">fork</Badge>
            {/if}
          </div>

          {#if Object.keys(repo.containers || {}).length > 0}
            <div class="repo-containers">
              {#each Object.entries(repo.containers) as [role, session]}
                <span class="container-tag">{role}: {session}</span>
              {/each}
            </div>
          {/if}
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .repos-panel { padding: 24px; }
  .panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 20px;
  }
  h2 {
    font-size: 18px;
    font-weight: 600;
    color: #e2e8f0;
    margin: 0;
  }
  .btn-add {
    background: rgba(59, 130, 246, 0.1);
    border: 1px solid rgba(59, 130, 246, 0.3);
    color: #60a5fa;
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
  }
  .btn-add:hover { background: rgba(59, 130, 246, 0.2); }

  .add-form {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 20px;
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
  .add-form label {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .add-form label > span {
    font-size: 12px;
    color: #94a3b8;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }
  .add-form input[type="text"] {
    background: #0f172a;
    border: 1px solid #334155;
    color: #e2e8f0;
    padding: 8px 12px;
    border-radius: 6px;
    font-size: 13px;
  }
  .toggles {
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
  }
  .toggle {
    display: flex;
    flex-direction: row !important;
    align-items: center;
    gap: 6px;
    cursor: pointer;
  }
  .toggle span {
    font-size: 13px !important;
    color: #cbd5e1 !important;
    text-transform: none !important;
    letter-spacing: normal !important;
  }
  .btn-submit {
    background: #3b82f6;
    border: none;
    color: white;
    padding: 8px 16px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 13px;
    align-self: flex-start;
  }
  .btn-submit:disabled { opacity: 0.5; cursor: not-allowed; }

  .error {
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid rgba(239, 68, 68, 0.3);
    color: #fca5a5;
    padding: 10px 14px;
    border-radius: 6px;
    font-size: 13px;
    margin-bottom: 16px;
  }

  .loading, .empty {
    color: #64748b;
    text-align: center;
    padding: 40px 20px;
  }
  .hint { font-size: 13px; margin-top: 8px; }

  .repo-grid {
    display: grid;
    gap: 16px;
    grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  }
  .repo-card {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 16px;
  }
  .repo-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }
  .repo-header h3 {
    font-size: 15px;
    font-weight: 600;
    color: #e2e8f0;
    margin: 0;
  }
  .btn-delete {
    background: none;
    border: none;
    color: #64748b;
    cursor: pointer;
    font-size: 16px;
    padding: 2px 6px;
    border-radius: 4px;
  }
  .btn-delete:hover { color: #ef4444; background: rgba(239, 68, 68, 0.1); }

  .repo-url {
    font-size: 12px;
    color: #64748b;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    margin-bottom: 4px;
    word-break: break-all;
  }
  .repo-branch {
    font-size: 12px;
    color: #475569;
    margin-bottom: 12px;
  }

  .repo-agents {
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 8px;
  }
  .agent-toggle {
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    opacity: 0.7;
    transition: opacity 0.15s;
  }
  .agent-toggle:hover, .agent-toggle.active { opacity: 1; }

  .repo-containers {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-top: 8px;
  }
  .container-tag {
    background: rgba(16, 185, 129, 0.1);
    border: 1px solid rgba(16, 185, 129, 0.2);
    color: #6ee7b7;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
  }
</style>
