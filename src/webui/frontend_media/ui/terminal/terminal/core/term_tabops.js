/**
 * TerminalManager tab-management helpers: title updates, tab switching,
 * pane visibility. Hangs its methods onto the shared ctx object.
 */
function _tmUpdateTabTitle(ctx, tab) {
  if (!tab || !ctx.bar) return;

  var title = tab.name;
  if (tab._hasRunningSubprocess && tab._childCommandLabel) {
    title += ' [' + tab._childCommandLabel + ']';
  }

  ctx.bar.setTitle(tab.id, title);
}

function _tmCreateTab(ctx, kind, options) {
  return ctx.createTabCore(kind, options);
}

function _tmInitTerminal(ctx, tab) {
  ctx.initTerminalCore(tab);
}

function _tmShowTabPane(ctx, tabId) {
  var panes = ctx.body.querySelectorAll('.terminal-pane');
  for (var i = 0; i < panes.length; i++) {
    panes[i].style.display = panes[i].id === 'terminal-pane-' + tabId ? 'block' : 'none';
  }

  var emptyState = document.getElementById('terminalEmptyState');
  if (emptyState) {
    emptyState.style.display = ctx.tabs.length > 0 ? 'none' : 'flex';
  }
}

function _tmResolveActiveTerminalTarget(ctx) {
  var tab = ctx.getActiveTab();
  if (!tab) return null;
  if (tab.split && tab._activePane === 'split') {
    return tab.split;
  }
  return tab;
}

function _tmFocusPane(ctx, tabId, pane) {
  var switchingTab = ctx.activeTabId !== tabId;
  if (switchingTab) {
    ctx.activeTabId = tabId;
    if (ctx.bar) ctx.bar.setActive(tabId);
    ctx.showTabPane(tabId);
    try { localStorage.setItem('term_last_active_tab', tabId); } catch (e) {}
  }

  var tab = ctx.getTabById(tabId);
  if (!tab) return;
  if (pane === 'split' && !tab.split) pane = 'primary';
  tab._activePane = pane;
  if (ctx.bar && ctx.bar.setActivePane) ctx.bar.setActivePane(tabId, pane);
  if (typeof ctx.persistSplitActivePane === 'function') ctx.persistSplitActivePane(tab);

  var target = pane === 'split' ? tab.split : tab;
  if (!target) return;
  setTimeout(function () {
    ctx.fitAndResize(target, true);
    if (target.xterm) target.xterm.focus();
  }, switchingTab ? 50 : 0);
}

function _tmSwitchToTab(ctx, tabId) {
  _tmFocusPane(ctx, tabId, 'primary');
}

function _attachTerminalManagerTabOps(ctx) {
  ctx.createTab = function (kind, options) { return _tmCreateTab(ctx, kind, options); };
  ctx.initTerminal = function (tab) { return _tmInitTerminal(ctx, tab); };
  ctx.showTabPane = function (tabId) { return _tmShowTabPane(ctx, tabId); };
  ctx.switchToTab = function (tabId) { return _tmSwitchToTab(ctx, tabId); };
  ctx.focusPane = function (tabId, pane) { return _tmFocusPane(ctx, tabId, pane); };
  ctx.updateTabTitle = function (tab) { return _tmUpdateTabTitle(ctx, tab); };
  ctx.resolveActiveTerminalTarget = function () { return _tmResolveActiveTerminalTarget(ctx); };
}

/**
 * Builds the shared mutable ctx object used by TerminalManager and all its
 * submodules. Extracted from term.js so the IIFE there stays a thin facade.
 */
function _createTerminalManagerCtx() {
  return {
    tabs: [],
    activeTabId: null,
    tabCounter: 0,
    savedConnections: [],
    contextMenu: null,
    discoveryProcessed: false, // guard against double-processing existing sessions
    terminalBgMode: 'theme', // 'theme' | 'original' | 'custom'
    customBgImage: '', // custom background image data URL
    customBgOpacity: 0.3, // custom background opacity (0-1)
    utf8Decoder: new TextDecoder('utf-8'),
    // DOM references (set in init)
    container: null,
    tabBarEl: null,
    body: null,
    bar: null, // TabBar instance
  };
}

/**
 * Wires every terminal submodule's _attachXxxMethods(ctx) onto the shared
 * ctx object. Extracted from term.js for the same reason as
 * _createTerminalManagerCtx above.
 */
function _wireTerminalManagerSubmodules(ctx) {
  _attachLinksMethods(ctx);
  _attachPaneMethods(ctx);
  _attachResizeMethods(ctx);
  _attachInitMethods(ctx);
  _attachThumbnailMethods(ctx);
  _attachThemeMethods(ctx);
  _attachColorMethods(ctx);
  _attachSearchMethods(ctx);
  _attachContextMenuMethods(ctx);
  _attachSplitMethods(ctx);
  _attachSplitPersistMethods(ctx);
  _attachChooserMethods(ctx);
  _attachSshMethods(ctx);
  _attachWebSocketMethods(ctx);
  _attachLifecycleMethods(ctx);
  _attachReconnectMethods(ctx);
  _attachTerminalManagerTabOps(ctx);
}

function _refreshTerminalTheme(ctx) {
  if (ctx.terminalBgMode !== 'theme') return;
  var theme = ctx.getTerminalTheme('theme');
  for (var i = 0; i < ctx.tabs.length; i++) {
    if (ctx.tabs[i].xterm) {
      ctx.tabs[i].xterm.options.theme = theme;
    }
  }
}

/**
 * Builds the public API object returned by the TerminalManager IIFE.
 * Extracted from term.js for the same reason as _createTerminalManagerCtx
 * above.
 */
function _buildTerminalManagerPublicApi(ctx, init) {
  return {
    init: init,
    createTab: ctx.createTab,
    closeTab: ctx.closeTab,
    closeAllTabs: ctx.closeAllTabs,
    closeOtherTabs: ctx.closeOtherTabs,
    renameTab: ctx.renameTab,
    showSSHDialog: ctx.showSSHDialog,
    getActiveTab: ctx.getActiveTab,
    convertChooserTabToSSH: ctx.convertChooserTabToSSH,
    sendToActiveTab: function (text) {
      var target = ctx.resolveActiveTerminalTarget();
      if (!target || !target.ws || target.ws.readyState !== WebSocket.OPEN) return false;
      target.ws.send(JSON.stringify({ type: 'input', data: text }));
      return true;
    },
    refreshTheme: function () { _refreshTerminalTheme(ctx); },
  };
}

