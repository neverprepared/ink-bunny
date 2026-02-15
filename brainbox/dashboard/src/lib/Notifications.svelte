<script>
  import { notifications } from './notifications.svelte.js';
</script>

<div class="notifications-container">
  {#each notifications.value as notification (notification.id)}
    <div
      class="notification"
      data-type={notification.type}
      onclick={() => notifications.dismiss(notification.id)}
      role="alert"
    >
      <span class="icon">
        {#if notification.type === 'success'}✓{/if}
        {#if notification.type === 'error'}✗{/if}
        {#if notification.type === 'warning'}⚠{/if}
        {#if notification.type === 'info'}ℹ{/if}
      </span>
      <span class="message">{notification.message}</span>
      <button class="close" onclick={() => notifications.dismiss(notification.id)}>×</button>
    </div>
  {/each}
</div>

<style>
  .notifications-container {
    position: fixed;
    top: 20px;
    right: 20px;
    z-index: 9999;
    display: flex;
    flex-direction: column;
    gap: 12px;
    max-width: 400px;
  }

  .notification {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 16px;
    border-radius: 6px;
    background: #1e293b;
    border: 1px solid #334155;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    cursor: pointer;
    transition: all 0.2s ease;
    animation: slideIn 0.3s ease;
  }

  .notification:hover {
    transform: translateX(-4px);
    box-shadow: 0 6px 16px rgba(0, 0, 0, 0.4);
  }

  .notification[data-type="success"] {
    border-left: 4px solid #10b981;
  }

  .notification[data-type="error"] {
    border-left: 4px solid #ef4444;
  }

  .notification[data-type="warning"] {
    border-left: 4px solid #f59e0b;
  }

  .notification[data-type="info"] {
    border-left: 4px solid #3b82f6;
  }

  .icon {
    font-size: 18px;
    font-weight: bold;
    flex-shrink: 0;
  }

  .notification[data-type="success"] .icon {
    color: #10b981;
  }

  .notification[data-type="error"] .icon {
    color: #ef4444;
  }

  .notification[data-type="warning"] .icon {
    color: #f59e0b;
  }

  .notification[data-type="info"] .icon {
    color: #3b82f6;
  }

  .message {
    flex: 1;
    color: #e2e8f0;
    font-size: 14px;
    line-height: 1.5;
  }

  .close {
    background: none;
    border: none;
    color: #94a3b8;
    font-size: 24px;
    line-height: 1;
    cursor: pointer;
    padding: 0;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 4px;
    transition: all 0.2s ease;
    flex-shrink: 0;
  }

  .close:hover {
    background: rgba(148, 163, 184, 0.1);
    color: #e2e8f0;
  }

  @keyframes slideIn {
    from {
      opacity: 0;
      transform: translateX(20px);
    }
    to {
      opacity: 1;
      transform: translateX(0);
    }
  }

  @media (prefers-reduced-motion: reduce) {
    .notification {
      animation: none;
    }
  }

  @media (max-width: 768px) {
    .notifications-container {
      right: 12px;
      left: 12px;
      max-width: none;
    }
  }
</style>
