<script>
  import { currentPanel } from './stores.svelte.js';
  import Sidebar from './Sidebar.svelte';
  import ContainersPanel from './ContainersPanel.svelte';
  import DashboardPanel from './DashboardPanel.svelte';
</script>

<div class="shell">
  <Sidebar />
  <main class="content">
    {#if currentPanel.value === 'containers'}
      <ContainersPanel />
    {:else if currentPanel.value === 'dashboard'}
      <DashboardPanel />
    {/if}
  </main>
</div>

<style>
  .shell {
    display: grid;
    grid-template-columns: auto 1fr;
    min-height: 100vh;
  }

  .content {
    padding: 24px clamp(16px, 3vw, 32px);
    overflow-y: auto;
    min-width: 0;
  }
</style>
