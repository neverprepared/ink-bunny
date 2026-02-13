<script>
  let { total, active, stopped, portRange } = $props();
</script>

<div class="stats">
  <div class="stat-card">
    <div class="stat-label">Total Sessions</div>
    <div class="stat-value">{total}</div>
  </div>
  <div class="stat-card stat-active">
    <div class="stat-label">Active</div>
    <div class="stat-value">{active}</div>
  </div>
  <div class="stat-card stat-stopped">
    <div class="stat-label">Stopped</div>
    <div class="stat-value">{stopped}</div>
  </div>
  <div class="stat-card stat-ports">
    <div class="stat-label">Port Range</div>
    <div class="stat-value">{portRange}</div>
  </div>
</div>

<style>
  .stats {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
    margin-bottom: 24px;
  }
  @media (max-width: 600px) {
    .stats { grid-template-columns: repeat(2, 1fr); }
  }
  .stat-card {
    background: #111827;
    border: 1px solid #1e293b;
    border-radius: 8px;
    padding: 16px 20px;
  }
  .stat-label {
    font-size: 11px;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 8px;
  }
  .stat-value {
    font-size: 28px;
    font-weight: 600;
    color: #e2e8f0;
  }
  .stat-active .stat-value { color: #10b981; }
  .stat-stopped .stat-value { color: #64748b; }
  .stat-ports .stat-value {
    font-size: 20px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
  }
</style>
