// ========================= Terminal: Split Pane =========================
// Split from terminal.js. Handles splitting a tab into two side-by-side panes.

function _attachSplitMethods(ctx) {
  var _createSplitXterm = _attachSplitSubXterm(ctx);
  _attachSplitCloseMethods(ctx);
  _attachSplitSubTab(ctx, _createSplitXterm);
}

function _wireSplitXtermIo(xterm, splitState) {
  function _sendInput(data) {
    if (splitState.ws && splitState.ws.readyState === WebSocket.OPEN) {
      splitState.ws.send(JSON.stringify({ type: 'input', data: data }));
    }
  }
  xterm.onData(_sendInput);
  xterm.onBinary(_sendInput);
}

function _wireSplitXtermFocus(ctx, splitState, splitXtermContainer) {
  function _focusSplitPane() {
    ctx.focusPane(splitState._parentId, 'split');
  }
  splitXtermContainer.addEventListener('click', function (e) {
    e.stopPropagation();
    _focusSplitPane();
  });
  splitXtermContainer.addEventListener('focusin', function (e) {
    e.stopPropagation();
    _focusSplitPane();
  });
}

function _attachSplitSubXterm(ctx) {
  function _createSplitXterm(splitState, splitXtermContainer) {
    var xterm = new Terminal({
      cursorBlink: true,
      cursorStyle: 'block',
      fontFamily: '"Cascadia Code","Fira Code","JetBrains Mono",Menlo,Monaco,monospace',
      fontSize: ctx.termFontSize || 14,
      lineHeight: 1.15,
      scrollback: 5000,
      allowProposedApi: true,
      allowTransparency: true,
      theme: ctx.getTerminalTheme(),
    });
    var fitAddon = new FitAddon.FitAddon();
    xterm.loadAddon(fitAddon);
    xterm.open(splitXtermContainer);
    ctx.installTerminalLinkProvider(xterm);
    try { fitAddon.fit(); } catch (e) { /* ignore */ }

    splitState.xterm = xterm;
    splitState.fitAddon = fitAddon;

    var ro = new ResizeObserver(function () {
      ctx.fitAndResize(splitState);
    });
    ro.observe(splitXtermContainer.parentNode);
    splitState._resizeObserver = ro;

    _wireSplitXtermIo(xterm, splitState);
    _wireSplitXtermFocus(ctx, splitState, splitXtermContainer);
    ctx.connectWebSocket(splitState);
  }

  return _createSplitXterm;
}

// Wrap the existing xterm container in a split layout, then add a
// second pane hosting a brand-new xterm + WebSocket connection.
function _buildSplitDom(pane, tab) {
  var splitContainer = document.createElement('div');
  splitContainer.className = 'terminal-split-container terminal-split-vertical';

  var leftPane = document.createElement('div');
  leftPane.className = 'terminal-split-pane terminal-split-left';

  var rightPane = document.createElement('div');
  rightPane.className = 'terminal-split-pane terminal-split-right';

  // Move the existing xterm container into the left pane
  pane.removeChild(tab._container);
  leftPane.appendChild(tab._container);

  splitContainer.appendChild(leftPane);
  splitContainer.appendChild(rightPane);
  pane.appendChild(splitContainer);

  var splitXtermContainer = document.createElement('div');
  splitXtermContainer.className = 'xterm-container';
  rightPane.appendChild(splitXtermContainer);

  return splitXtermContainer;
}

function _createSplitState(tabId, tab, splitXtermContainer) {
  return {
    id: tabId + '-split',
    kind: tab.kind,
    options: tab.options,
    xterm: null,
    fitAddon: null,
    ws: null,
    sessionId: null,
    _container: splitXtermContainer,
    _resizeObserver: null,
    _closing: false,
    _readOnly: false,
    _reconnectAttempts: 0,
    _reconnectTimer: null,
    // Marks this state object as a split pane rather than a primary tab,
    // so _connectWebSocket routes its status updates to the TabBar's
    // secondary (paired) dot instead of trying to look up a nonexistent
    // '<tabId>-split' tab element.
    _isSplit: true,
    _parentId: tabId,
  };
}

function _attachSplitSubDom(ctx) {
  return { buildSplitDom: _buildSplitDom, createSplitState: _createSplitState };
}

function _teardownPaneResources(paneState, markClosing) {
  if (markClosing !== false) paneState._closing = true;
  if (paneState._reconnectTimer) {
    clearTimeout(paneState._reconnectTimer);
    paneState._reconnectTimer = null;
  }
  if (paneState.ws && paneState.ws.readyState === WebSocket.OPEN) {
    try { paneState.ws.send(JSON.stringify({ type: 'close_session' })); } catch (e) {}
  }
  var wsRef = paneState.ws;
  setTimeout(function () {
    if (wsRef) { try { wsRef.close(); } catch (e) {} }
  }, 50);
  if (paneState._resizeObserver) {
    try { paneState._resizeObserver.disconnect(); } catch (e) {}
    paneState._resizeObserver = null;
  }
  if (paneState.xterm) {
    try { paneState.xterm.dispose(); } catch (e) {}
    paneState.xterm = null;
  }
  if (paneState.fitAddon) {
    try { paneState.fitAddon.dispose(); } catch (e) {}
    paneState.fitAddon = null;
  }
  paneState.ws = null;
}

function _unsplitDom(pane, tab) {
  var splitContainer = pane.querySelector('.terminal-split-container');
  if (!splitContainer || !tab._container) return;
  pane.removeChild(splitContainer);
  pane.appendChild(tab._container);
}

function _splitClosePane(ctx, tab) {
  if (!tab.split) return;
  ctx.teardownSplitState(tab.split);
  tab.split = null;
  tab._activePane = 'primary';
  if (typeof ctx.clearSplitLayout === 'function') ctx.clearSplitLayout(tab);
  var pane = document.getElementById('terminal-pane-' + tab.id);
  if (pane) _unsplitDom(pane, tab);
  if (ctx.bar) {
    ctx.bar.setSplitStatus(tab.id, null);
    ctx.bar.setActivePane(tab.id, 'primary');
  }
  setTimeout(function () { ctx.fitAndResize(tab, true); }, 50);
}

function _splitPromotePane(ctx, tab) {
  var survivor = tab.split;
  if (!survivor) return;

  _teardownPaneResources(tab, true);
  tab._closing = false;

  survivor._isSplit = false;
  survivor.id = tab.id;
  survivor._parentId = null;
  survivor._closing = false;

  tab.xterm = survivor.xterm;
  tab.fitAddon = survivor.fitAddon;
  tab.ws = survivor.ws;
  tab.sessionId = survivor.sessionId;
  tab._container = survivor._container;
  tab._resizeObserver = survivor._resizeObserver;
  tab._reconnectAttempts = survivor._reconnectAttempts || 0;
  tab._reconnectTimer = survivor._reconnectTimer || null;
  tab.status = survivor.status || tab.status || '';
  tab.split = null;
  tab._activePane = 'primary';

  var pane = document.getElementById('terminal-pane-' + tab.id);
  if (pane) _unsplitDom(pane, tab);

  if (ctx.bar) {
    ctx.bar.setStatus(tab.id, tab.status || '');
    ctx.bar.setSplitStatus(tab.id, null);
    ctx.bar.setActivePane(tab.id, 'primary');
  }
  if (typeof ctx.clearSplitLayout === 'function') ctx.clearSplitLayout(tab);
  setTimeout(function () { ctx.fitAndResize(tab, true); }, 50);
}

function _splitCloseTabPane(ctx, tabId, pane) {
  var tab = ctx.getTabById(tabId);
  if (!tab) return;
  if (!tab.split) {
    if (ctx.bar) {
      ctx.bar.setSplitStatus(tabId, null);
      ctx.bar.setActivePane(tabId, 'primary');
    }
    return;
  }
  if (pane === 'split') {
    _splitClosePane(ctx, tab);
    return;
  }
  _splitPromotePane(ctx, tab);
}

function _attachSplitCloseMethods(ctx) {
  ctx.closeTabPane = function (tabId, pane) {
    _splitCloseTabPane(ctx, tabId, pane);
  };
}

function _splitApplyToTab(ctx, domHelpers, createSplitXterm, tabId, tab, splitSessionId, activePane) {
  var pane = document.getElementById('terminal-pane-' + tabId);
  if (!pane || !tab._container) return false;

  var splitXtermContainer = domHelpers.buildSplitDom(pane, tab);
  var splitState = domHelpers.createSplitState(tabId, tab, splitXtermContainer);
  if (splitSessionId) splitState.sessionId = splitSessionId;
  tab.split = splitState;
  tab._activePane = activePane || 'primary';

  if (ctx.bar) {
    ctx.bar.setSplitStatus(tabId, 'connecting');
    ctx.bar.setActivePane(tabId, tab._activePane);
  }

  if (typeof Terminal !== 'undefined') {
    createSplitXterm(splitState, splitXtermContainer);
  }

  if (tab.fitAddon) {
    setTimeout(function () { ctx.fitAndResize(tab, true); }, 50);
  }
  return true;
}

function _attachSplitSubTab(ctx, _createSplitXterm) {
  var domHelpers = _attachSplitSubDom(ctx);

  function _splitTab(tabId) {
    var tab = ctx.getTabById(tabId);
    if (!tab || tab.kind === 'chooser') return;
    if (tab.split) {
      if (typeof toast === 'function') toast(t('terminal.maxSplits'), 'info');
      return;
    }
    _splitApplyToTab(ctx, domHelpers, _createSplitXterm, tabId, tab, null, 'primary');
  }

  function _restoreSplitPane(parentTab, splitSessionId, activePane) {
    if (!parentTab || parentTab.split) return;
    _splitApplyToTab(ctx, domHelpers, _createSplitXterm, parentTab.id, parentTab, splitSessionId, activePane || 'primary');
  }

  ctx.splitTab = _splitTab;
  ctx.restoreSplitPane = _restoreSplitPane;
}
