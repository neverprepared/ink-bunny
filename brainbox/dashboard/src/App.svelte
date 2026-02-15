<script>
  import AppShell from './lib/AppShell.svelte';
  import Notifications from './lib/Notifications.svelte';
</script>

<AppShell />
<Notifications />

<style>
  :global(*) { box-sizing: border-box; margin: 0; padding: 0; }
  :global(body) {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Inter, sans-serif;
    background: #0a0e1a;
    color: #e2e8f0;
  }
</style>
