<script>
  let { type = 'role', variant, text } = $props();
</script>

<span class="badge" class:badge-backend={type === 'backend'} class:badge-role={type === 'role'} class:badge-provider={type === 'provider'} class:badge-profile={type === 'profile'} data-variant={variant}>
  {text}
</span>

<style>
  .badge {
    font-size: 10px;
    padding: 2px 6px;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    font-weight: 600;
    flex-shrink: 0;
  }

  /* Role badges */
  .badge-role[data-variant="developer"] {
    background: rgba(59, 130, 246, 0.15);
    color: #3b82f6;
  }
  .badge-role[data-variant="researcher"] {
    background: rgba(168, 85, 247, 0.15);
    color: #a855f7;
  }
  .badge-role[data-variant="performer"] {
    background: rgba(249, 115, 22, 0.15);
    color: #f97316;
  }

  /* Provider badges */
  .badge-provider {
    letter-spacing: 0.02em;
    font-weight: 500;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
  }
  .badge-provider[data-variant="public"] {
    background: rgba(236, 72, 153, 0.15);
    color: #ec4899;
  }
  .badge-provider[data-variant="private"] {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
  }

  /* Profile badges */
  .badge-profile {
    text-transform: lowercase;
    letter-spacing: 0.02em;
    font-weight: 500;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    background: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
  }

  /* Backend badges */
  .badge-backend {
    letter-spacing: 0.02em;
    font-weight: 500;
  }
  .badge-backend[data-variant="docker"] {
    background: rgba(59, 130, 246, 0.15);
    color: #3b82f6;
  }
  .badge-backend[data-variant="utm"] {
    background: rgba(139, 92, 246, 0.15);
    color: #8b5cf6;
  }
</style>
