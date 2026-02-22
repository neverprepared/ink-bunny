<script>
  import { onMount, onDestroy } from 'svelte';
  import { fetchLangfuseHealth, fetchQdrantHealth } from './api.js';
  import StatCard from './StatCard.svelte';

  let langfuseHealth = $state({ healthy: false, mode: 'off', url: null });
  let qdrantHealth = $state({ healthy: false, url: null });
  let langfuseLoading = $state(true);
  let qdrantLoading = $state(true);
  let interval = null;

  async function refreshHealth() {
    try {
      langfuseHealth = await fetchLangfuseHealth();
    } catch { langfuseHealth = { healthy: false, mode: 'unknown', url: null }; }
    finally { langfuseLoading = false; }

    try {
      qdrantHealth = await fetchQdrantHealth();
    } catch { qdrantHealth = { healthy: false, url: null }; }
    finally { qdrantLoading = false; }
  }

  onMount(() => {
    refreshHealth();
    interval = setInterval(refreshHealth, 30_000);
  });

  onDestroy(() => {
    if (interval) clearInterval(interval);
  });
</script>

<header>
  <h1><span class="accent">observability</span></h1>
</header>

<div class="stats">
  <StatCard label="LangFuse" value={langfuseLoading ? '...' : (langfuseHealth.healthy ? 'Online' : 'Offline')} variant={langfuseLoading ? 'default' : (langfuseHealth.healthy ? 'healthy' : 'unhealthy')} />
  <StatCard label="Qdrant" value={qdrantLoading ? '...' : (qdrantHealth.healthy ? 'Online' : 'Offline')} variant={qdrantLoading ? 'default' : (qdrantHealth.healthy ? 'healthy' : 'unhealthy')} />
</div>

<div class="services">
  <div class="service-card">
    <div class="service-header">
      <div class="service-title">
        <span class="dot" class:online={langfuseHealth.healthy} class:offline={!langfuseHealth.healthy}></span>
        LangFuse
      </div>
      {#if langfuseHealth.healthy && langfuseHealth.url}
        <a href={langfuseHealth.url} target="_blank" rel="noopener noreferrer" class="open-link">
          Open →
        </a>
      {/if}
    </div>
    <p class="service-desc">Trace observability for LLM sessions</p>
    {#if !langfuseHealth.healthy}
      <p class="service-offline">Service unavailable</p>
    {/if}
  </div>

  <div class="service-card">
    <div class="service-header">
      <div class="service-title">
        <span class="dot" class:online={qdrantHealth.healthy} class:offline={!qdrantHealth.healthy}></span>
        Qdrant
      </div>
      {#if qdrantHealth.healthy && qdrantHealth.url}
        <a href={qdrantHealth.url} target="_blank" rel="noopener noreferrer" class="open-link">
          Open →
        </a>
      {/if}
    </div>
    <p class="service-desc">Vector database for RAG and memory</p>
    {#if qdrantHealth.healthy && qdrantHealth.url}
      <p class="service-url">{qdrantHealth.url}</p>
    {:else if !qdrantHealth.healthy}
      <p class="service-offline">Service unavailable</p>
    {/if}
  </div>
</div>

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

  .stats {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
    margin-bottom: 24px;
    max-width: 400px;
  }

  .services {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 16px;
  }
  @media (max-width: 700px) {
    .services { grid-template-columns: 1fr; }
  }

  .service-card {
    background: #0f172a;
    border: 1px solid #1e293b;
    border-radius: 10px;
    padding: 20px;
  }

  .service-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
  }

  .service-title {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 15px;
    font-weight: 600;
    color: #e2e8f0;
  }

  .dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .dot.online  { background: #22c55e; box-shadow: 0 0 6px #22c55e88; }
  .dot.offline { background: #ef4444; }

  .open-link {
    font-size: 13px;
    color: #f59e0b;
    text-decoration: none;
    font-weight: 500;
    transition: color 0.15s;
  }
  .open-link:hover { color: #fbbf24; }

  .service-desc {
    font-size: 13px;
    color: #64748b;
    margin: 0;
  }

  .service-url {
    font-size: 12px;
    color: #475569;
    margin: 6px 0 0;
    font-family: monospace;
    word-break: break-all;
  }

  .service-offline {
    font-size: 13px;
    color: #ef4444;
    margin: 6px 0 0;
  }
</style>
