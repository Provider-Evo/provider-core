/**
 * Terminal bootstrap wiring -- TabBar construction, background/resize
 * control wiring, and the Router activate/deactivate handlers.
 *
 * Exposes via _attachInitMethods(ctx):
 * - ctx.runInit()  -- full init() sequence, called once on DOMContentLoaded
 */
function _tiOnTabBarToggleCollapsed(ctx, collapsed) {
  propagateTabBarCollapsed(ctx.bar, collapsed);
}

function _tiCreateTerminalTabBar(ctx) {
  if (typeof TabBar === 'undefined') return;

  ctx.bar = TabBar.create(ctx.container, {
    tabBarEl: ctx.tabBarEl,
    bodyEl: ctx.body,
    layout: 'horizontal',
    collapsed: false,
    closeAllThreshold: 6,
    onSwitch: function (id) { ctx.switchToTab(id); },
    onClose: function (id) { ctx.closeTab(id); },
    onSplitPaneSelect: function (id, pane) { ctx.focusPane(id, pane); },
    onPaneClose: function (id, pane) { ctx.closeTabPane(id, pane); },
    onContextMenu: function (id, event) { ctx.showContextMenu(event, id); },
    onAdd: function () { ctx.createChooserTab(); },
    onCloseAll: function () { ctx.closeAllTabs(); },
    onPreviewRequest: function (tabId) {
      var tab = ctx.getTabById(tabId);
      if (tab) ctx.captureThumbnail(tab);
    },
    onToggleCollapsed: function (collapsed) { _tiOnTabBarToggleCollapsed(ctx, collapsed); },
  });

  // Register in global registry for bootstrap.js layout toggle
  if (window._tabBars) {
    window._tabBars.terminal = ctx.bar;
  }

  // Apply current layout from _tabLayoutConfig (may have been loaded from persist)
  if (typeof _tabLayoutConfig !== 'undefined') {
    ctx.bar.setLayout(_tabLayoutConfig.layout || 'horizontal', _tabLayoutConfig.sidebarCompressed || false);
  }
}

function _tiWireFontSizeControl(ctx) {
  var fontSizeRange = document.getElementById('terminalFontSizeRange');
  if (!fontSizeRange) return;
  fontSizeRange.value = ctx.termFontSize || 14;
  var fontSizeDisplay = document.getElementById('terminalFontSizeDisplay');
  if (fontSizeDisplay) fontSizeDisplay.textContent = (ctx.termFontSize || 14) + 'px';
  fontSizeRange.addEventListener('input', function (e) {
    var size = parseInt(e.target.value) || 14;
    ctx.termFontSize = size;
    if (fontSizeDisplay) fontSizeDisplay.textContent = size + 'px';
    ctx.tabs.forEach(function (tab) {
      if (tab.xterm) tab.xterm.options = { fontSize: size };
      if (tab.fitAddon) { try { tab.fitAddon.fit(); } catch (ex) {} }
      if (tab.split && tab.split.xterm) tab.split.xterm.options = { fontSize: size };
      if (tab.split && tab.split.fitAddon) { try { tab.split.fitAddon.fit(); } catch (ex) {} }
    });
    ctx.saveTerminalBgMode();
  });
}

function _tiWireBackgroundControls(ctx) {
  // Load terminal background mode preference (await before UI updates)
  ctx.loadTerminalBgMode().then(function () {
    ctx.updateBgModeButton();
    ctx.updateCustomBgControls();
  });

  // Background mode button click handler
  var bgModeBtn = document.getElementById('terminalBgModeBtn');
  if (bgModeBtn) {
    bgModeBtn.addEventListener('click', function () {
      ctx.toggleTerminalBgMode();
      ctx.updateBgModeButton();
      ctx.updateCustomBgControls();
    });
  }
  ctx.updateBgModeButton();

  // Custom background controls
  var bgImageBtn = document.getElementById('terminalBgImageBtn');
  if (bgImageBtn) {
    bgImageBtn.addEventListener('click', function () {
      ctx.showImagePicker();
    });
  }

  var bgOpacityRange = document.getElementById('terminalBgOpacityRange');
  if (bgOpacityRange) {
    bgOpacityRange.addEventListener('input', function (e) {
      ctx.setCustomBgOpacity(parseInt(e.target.value) / 100);
    });
  }

  _tiWireFontSizeControl(ctx);
  ctx.updateCustomBgControls();
}

function _tiWireWindowResize(ctx) {
  // Window resize: trigger fit on active terminal.
  // Per-tab ResizeObservers handle their own pane sizing,
  // but window resize may not fire ResizeObserver on hidden panes.
  var _resizeTimer = null;
  window.addEventListener('resize', function () {
    if (_resizeTimer) clearTimeout(_resizeTimer);
    _resizeTimer = setTimeout(function () {
      if (!ctx.isMainTerminalPanelVisible()) return;
      var tab = ctx.getActiveTab();
      if (tab) ctx.fitAndResize(tab, true);
    }, 150);
  });
}

function _tiWireBodyClickHandlers(ctx) {
  // Click on terminal body to focus the active xterm instance
  ctx.body.addEventListener('click', function () {
    var target = ctx.resolveActiveTerminalTarget();
    if (target && target.xterm) target.xterm.focus();
  });

  // Close context menu on click outside
  document.addEventListener('click', function () {
    ctx.hideContextMenu();
  });
}

function _tiOnActivate(ctx) {
  // Fit the active terminal when tab becomes visible
  var tab = ctx.getActiveTab();
  if (tab && tab.fitAddon) {
    setTimeout(function () {
      ctx.fitAndResize(tab, true);
      if (tab.xterm) tab.xterm.focus();
    }, 100);
  }
}

function _tiOnDeactivate() {
  // Dimensions are preserved in tab._lastCols/_lastRows; no resize while hidden.
}

function _tiWirePostSetup(ctx) {
  // Load saved connections
  ctx.loadSavedConnections();

  _tiWireBackgroundControls(ctx);
  _tiWireWindowResize(ctx);

  ctx.watchMainTabVisibility();

  // Register with Router for activate/deactivate
  if (typeof Router !== 'undefined') {
    Router.register('terminal', {
      activate: function () { _tiOnActivate(ctx); },
      deactivate: function () { _tiOnDeactivate(); },
    });
  }
}

function _tiRunInit(ctx) {
  ctx.container = document.getElementById('terminalContainer');
  ctx.tabBarEl = document.getElementById('terminalTabBar');
  ctx.body = document.getElementById('terminalBody');

  if (!ctx.container || !ctx.tabBarEl || !ctx.body) return;

  // Open a lightweight WS probe immediately to discover surviving
  // sessions from a previous page load.  The backend sends an
  // existing_sessions message as soon as any WS connects.  By
  // launching the probe here (before the rest of init finishes),
  // the session list arrives while TabBar is being set up, so
  // tabs appear instantly when the response comes back.
  ctx.probeForDiscovery();

  // Also fire a REST pre-fetch in parallel — whichever returns first
  // (WS or REST) creates the tab UI; the other is dedup-guarded.
  ctx.restPreFetch();

  _tiCreateTerminalTabBar(ctx);
  _tiWireBodyClickHandlers(ctx);
  _tiWirePostSetup(ctx);

  // Session discovery is handled by ctx.probeForDiscovery() at the start
  // of init(), which uses a WebSocket to receive existing_sessions.
}

function _attachInitMethods(ctx) {
  ctx.runInit = function () { _tiRunInit(ctx); };
}
