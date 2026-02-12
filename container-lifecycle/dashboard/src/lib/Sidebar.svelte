<script>
  import { panels } from './panels.js';
  import { currentPanel, sidebarCollapsed } from './stores.svelte.js';
</script>

<nav class="sidebar" class:collapsed={sidebarCollapsed.value}>
  <div class="sidebar-header">
    {#if !sidebarCollapsed.value}
      <span class="brand">developer</span>
    {/if}
  </div>

  <ul class="nav-items">
    {#each panels as panel (panel.id)}
      <li>
        <button
          class="nav-btn"
          class:active={currentPanel.value === panel.id}
          onclick={() => currentPanel.value = panel.id}
          title={panel.label}
        >
          <span class="nav-icon">{@html panel.icon}</span>
          {#if !sidebarCollapsed.value}
            <span class="nav-label">{panel.label}</span>
          {/if}
        </button>
      </li>
    {/each}
  </ul>

  <div class="sidebar-footer">
    <button class="collapse-btn" onclick={() => sidebarCollapsed.toggle()} title={sidebarCollapsed.value ? 'Expand sidebar' : 'Collapse sidebar'}>
      {#if sidebarCollapsed.value}
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"/></svg>
      {:else}
        <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="15 18 9 12 15 6"/></svg>
      {/if}
    </button>
  </div>
</nav>

<style>
  .sidebar {
    display: flex;
    flex-direction: column;
    width: 220px;
    min-height: 100vh;
    background: #0d1117;
    border-right: 1px solid #1e293b;
    transition: width 0.2s ease;
    overflow: hidden;
  }
  .sidebar.collapsed {
    width: 60px;
  }

  .sidebar-header {
    padding: 20px 16px 12px;
    min-height: 52px;
  }
  .brand {
    font-size: 16px;
    font-weight: 600;
    color: #f59e0b;
    white-space: nowrap;
  }

  .nav-items {
    list-style: none;
    flex: 1;
    padding: 0 8px;
  }
  .nav-items li {
    margin-bottom: 2px;
  }

  .nav-btn {
    display: flex;
    align-items: center;
    gap: 12px;
    width: 100%;
    padding: 10px 12px;
    background: none;
    border: none;
    border-radius: 6px;
    color: #94a3b8;
    cursor: pointer;
    font-family: inherit;
    font-size: 14px;
    white-space: nowrap;
    transition: all 0.15s;
  }
  .nav-btn:hover {
    background: rgba(255, 255, 255, 0.05);
    color: #e2e8f0;
  }
  .nav-btn.active {
    background: rgba(59, 130, 246, 0.1);
    color: #3b82f6;
  }

  .nav-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
    width: 20px;
    height: 20px;
  }

  .nav-label {
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .sidebar-footer {
    padding: 12px 8px;
    border-top: 1px solid #1e293b;
  }
  .collapse-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    padding: 8px;
    background: none;
    border: none;
    border-radius: 6px;
    color: #475569;
    cursor: pointer;
    transition: all 0.15s;
  }
  .collapse-btn:hover {
    background: rgba(255, 255, 255, 0.05);
    color: #94a3b8;
  }
</style>
