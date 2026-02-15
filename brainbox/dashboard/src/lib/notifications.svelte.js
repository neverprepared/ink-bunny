/** Notification system for user feedback. */

let _notifications = $state([]);
let _idCounter = 0;

export const notifications = {
  get value() {
    return _notifications;
  },

  /**
   * Show an error notification.
   * @param {string} message - Error message to display
   * @param {number} duration - Auto-dismiss duration in ms (0 = no auto-dismiss)
   */
  error(message, duration = 5000) {
    const id = ++_idCounter;
    _notifications = [..._notifications, { id, type: 'error', message }];
    if (duration > 0) {
      setTimeout(() => this.dismiss(id), duration);
    }
    return id;
  },

  /**
   * Show a success notification.
   * @param {string} message - Success message to display
   * @param {number} duration - Auto-dismiss duration in ms (0 = no auto-dismiss)
   */
  success(message, duration = 3000) {
    const id = ++_idCounter;
    _notifications = [..._notifications, { id, type: 'success', message }];
    if (duration > 0) {
      setTimeout(() => this.dismiss(id), duration);
    }
    return id;
  },

  /**
   * Show an info notification.
   * @param {string} message - Info message to display
   * @param {number} duration - Auto-dismiss duration in ms (0 = no auto-dismiss)
   */
  info(message, duration = 3000) {
    const id = ++_idCounter;
    _notifications = [..._notifications, { id, type: 'info', message }];
    if (duration > 0) {
      setTimeout(() => this.dismiss(id), duration);
    }
    return id;
  },

  /**
   * Show a warning notification.
   * @param {string} message - Warning message to display
   * @param {number} duration - Auto-dismiss duration in ms (0 = no auto-dismiss)
   */
  warning(message, duration = 4000) {
    const id = ++_idCounter;
    _notifications = [..._notifications, { id, type: 'warning', message }];
    if (duration > 0) {
      setTimeout(() => this.dismiss(id), duration);
    }
    return id;
  },

  /**
   * Dismiss a notification by ID.
   * @param {number} id - Notification ID to dismiss
   */
  dismiss(id) {
    _notifications = _notifications.filter(n => n.id !== id);
  },

  /**
   * Clear all notifications.
   */
  clear() {
    _notifications = [];
  }
};
