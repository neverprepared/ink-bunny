/** Reactive stores for panel routing and sidebar state. */

// ---------------------------------------------------------------------------
// Sidebar collapsed state (localStorage-persisted)
// ---------------------------------------------------------------------------

const SIDEBAR_KEY = 'sidebar-collapsed';

function loadCollapsed() {
  try {
    return localStorage.getItem(SIDEBAR_KEY) === 'true';
  } catch {
    return false;
  }
}

let _collapsed = $state(loadCollapsed());

export const sidebarCollapsed = {
  get value() { return _collapsed; },
  set value(v) {
    _collapsed = v;
    try { localStorage.setItem(SIDEBAR_KEY, String(v)); } catch { /* noop */ }
  },
  toggle() { this.value = !this.value; },
};

// ---------------------------------------------------------------------------
// Current panel (hash-synced)
// ---------------------------------------------------------------------------

const DEFAULT_PANEL = 'containers';

function panelFromHash() {
  const h = location.hash.replace('#', '');
  return h || DEFAULT_PANEL;
}

let _panel = $state(panelFromHash());

export const currentPanel = {
  get value() { return _panel; },
  set value(id) {
    _panel = id;
    history.replaceState(null, '', `#${id}`);
  },
};

// Listen for hash changes (back/forward navigation)
if (typeof window !== 'undefined') {
  window.addEventListener('hashchange', () => {
    _panel = panelFromHash();
  });
}
