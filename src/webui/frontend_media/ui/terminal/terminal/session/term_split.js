// ========================= Terminal: Split Pane =========================
// Split from terminal.js. Handles splitting a tab into two side-by-side panes.

function _attachSplitMethods(ctx) {
  var _createSplitXterm = _attachSplitSubXterm(ctx);
  _attachSplitSubTab(ctx, _createSplitXterm);
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

    xterm.onData(function (data) {
      if (splitState.ws && splitState.ws.readyState === WebSocket.OPEN) {
        splitState.ws.send(JSON.stringify({ type: 'input', data: data }));
      }
    });
    xterm.onBinary(function (data) {
      if (splitState.ws && splitState.ws.readyState === WebSocket.OPEN) {
        splitState.ws.send(JSON.stringify({ type: 'input', data: data }));
      }
    });
    splitXtermContainer.addEventListener('click', function (e) {
      e.stopPropagation();
      xterm.focus();
    });

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

function _attachSplitSubTab(ctx, _createSplitXterm) {
  var domHelpers = _attachSplitSubDom(ctx);
  var _buildSplitDom = domHelpers.buildSplitDom;
  var _createSplitState = domHelpers.createSplitState;

  /**
   * Split the given tab into two side-by-side (vertical) panes, each
   * hosting an independent terminal of the same kind/options as the
   * source tab. Limited to a single split (max 2 panes) per NOTE.md 17.2.3.
   */
  function _splitTab(tabId) {
    var tab = ctx.getTabById(tabId);
    if (!tab || tab.kind === 'chooser') return;

    if (tab.split) {
      if (typeof toast === 'function') toast(t('terminal.maxSplits'), 'info');
      return;
    }

    var pane = document.getElementById('terminal-pane-' + tabId);
    if (!pane || !tab._container) return;

    var splitXtermContainer = _buildSplitDom(pane, tab);
    var splitState = _createSplitState(tabId, tab, splitXtermContainer);
    tab.split = splitState;
    if (ctx.bar) ctx.bar.setSplitStatus(tabId, 'connecting');

    if (typeof Terminal !== 'undefined') {
      _createSplitXterm(splitState, splitXtermContainer);
    }

    // Re-fit the original (now left-pane) xterm to its new, narrower width
    if (tab.fitAddon) {
      setTimeout(function () { ctx.fitAndResize(tab, true); }, 50);
    }
  }

  ctx.splitTab = _splitTab;
}
