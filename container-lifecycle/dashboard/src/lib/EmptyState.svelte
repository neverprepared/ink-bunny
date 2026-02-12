<script>
  let { tip } = $props();
</script>

<div class="empty">
  <p>no sessions</p>
  <table class="help">
    <tbody>
      <tr><td><code>./scripts/run.sh</code></td><td>default session</td></tr>
      <tr><td><code>./scripts/run.sh -s name</code></td><td>named session</td></tr>
      <tr><td><code>./scripts/run.sh -n</code></td><td>skip opening browser</td></tr>
      <tr><td><code>./scripts/run.sh -v ~/myproject:/home/developer/myproject</code></td><td>mount volume</td></tr>
      <tr><td><code>./scripts/run.sh -q "question"</code></td><td>start with query</td></tr>
    </tbody>
  </table>
  <p class="tip">tip: {tip}</p>
</div>

<style>
  .empty {
    color: #64748b;
    padding: 48px 16px;
    text-align: center;
    max-width: 700px;
    margin: 0 auto;
  }
  .empty > p {
    font-size: 20px;
    margin-bottom: 24px;
    color: #94a3b8;
  }
  .help {
    margin: 0 auto;
    border-collapse: collapse;
    max-width: 100%;
  }
  .help td {
    padding: 8px 12px;
    font-size: 14px;
    vertical-align: top;
  }
  .help td:first-child {
    max-width: 350px;
    word-break: break-all;
  }
  .help code {
    color: #e2e8f0;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, monospace;
    background: rgba(255, 255, 255, 0.05);
    padding: 2px 6px;
    border-radius: 3px;
    font-size: 13px;
  }
  .help td:last-child { color: #475569; }
  .tip {
    margin-top: 24px;
    font-size: 13px;
    color: #475569;
  }
</style>
