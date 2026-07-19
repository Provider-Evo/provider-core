/**
 * Terminal tab/pane creation -- builds tab records, DOM panes, and wires
 * xterm.js instances (input/output plumbing, resize observers).
 *
 * Exposes via _attachPaneMethods(ctx):
 * - ctx.createTabCore(kind, options)
 * - ctx.initTerminalCore(tab)
 */
function _attachPaneMethods(ctx) {
  ctx.createTabCore = function (kind, options) {
    return _createTabCore(ctx, kind, options);
  };
  ctx.initTerminalCore = function (tab) {
    _initTerminalCore(ctx, tab);
  };
}

function _buildTabRecord(tabId, kind, name, options) {
  return {
    id: tabId,
    kind: kind,
    name: name,
    status: 'connecting',
    xterm: null,
    fitAddon: null,
    ws: null,
    sessionId: null,
    options: options,
    _resizeObserver: null,
    _container: null,
    _readOnly: false,
    _closing: false,
    _reconnectAttempts: 0,
    _reconnectTimer: null,
    color: options.color || '',
    split: null,
    _activePane: 'primary',
  };
}

function _registerTabInBar(ctx, tab) {
  if (!ctx.bar) return;
  ctx.bar.addTab({
    id: tab.id,
    type: 'terminal',
    icon: '',
    title: tab.name,
    closable: true,
    status: 'connecting',
  });
  ctx.bar.setActive(tab.id);
  if (tab.color) ctx.bar.setColor(tab.id, tab.color);
}

function _createTabCore(ctx, kind, options) {
  options = options || {};

  // Ensure the terminal sidebar tab is visible so the pane has dimensions
  if (typeof switchTab === 'function') {
    switchTab('terminal');
  }

  ctx.tabCounter++;
  var tabId = 'term-' + ctx.tabCounter + '-' + Date.now();
  var name = options.name || (kind === 'ssh' ? t('terminal.remote') : t('terminal.local')) + ' ' + ctx.tabCounter;

  var tab = _buildTabRecord(tabId, kind, name, options);
  ctx.tabs.push(tab);
  _registerTabInBar(ctx, tab);

  ctx.activeTabId = tabId;
  ctx.showTabPane(tabId);
  ctx.initTerminalCore(tab);
  return tab;
}

function _teardownTabXterm(tab) {
  // Dispose any existing xterm instance to prevent ghost cursors
  // or duplicate xterm instances on reattach/reconnect.
  if (tab._resizeObserver) {
    try { tab._resizeObserver.disconnect(); } catch (e) {}
    tab._resizeObserver = null;
  }
  if (tab.xterm) {
    try { tab.xterm.dispose(); } catch (e) {}
    tab.xterm = null;
  }
  if (tab.fitAddon) {
    try { tab.fitAddon.dispose(); } catch (e) {}
    tab.fitAddon = null;
  }
  if (tab.ws) {
    try { tab.ws.close(); } catch (e) {}
    tab.ws = null;
  }
}

function _createTerminalPane(ctx, tab) {
  // Remove any pre-existing pane for this tab to avoid orphaned DOM nodes.
  var oldPane = document.getElementById('terminal-pane-' + tab.id);
  if (oldPane) oldPane.remove();

  var termDiv = document.createElement('div');
  termDiv.className = 'terminal-pane';
  termDiv.id = 'terminal-pane-' + tab.id;
  termDiv.style.cssText = 'width:100%;height:100%;display:none;';
  ctx.body.appendChild(termDiv);

  var xtermContainer = document.createElement('div');
  xtermContainer.className = 'xterm-container';
  termDiv.appendChild(xtermContainer);

  tab._container = xtermContainer;
  return { termDiv: termDiv, xtermContainer: xtermContainer };
}

function _wireXtermIO(ctx, tab, xterm, xtermContainer, termDiv) {
  // ResizeObserver: detect container size changes and propagate to backend.
  // Fires when the pane becomes visible, when the window is resized,
  // or when the sidebar/layout changes.
  var ro = new ResizeObserver(function () {
    ctx.fitAndResize(tab);
  });
  ro.observe(termDiv);
  tab._resizeObserver = ro;

  // Keyboard input -> WebSocket.
  // xterm.js captures all keystrokes via its internal <textarea> and
  // fires onData with the properly encoded terminal input string.
  // The backend PTY (ConPTY or pipe) handles character echo;
  // xterm.js renders whatever the backend sends back via {type:'output'}.
  // No local echo is needed on the frontend.
  xterm.onData(function (data) {
    if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
      tab.ws.send(JSON.stringify({ type: 'input', data: data }));
    }
  });

  // Binary input handler for mouse events (TUI apps like htop, vim, mc).
  // xterm.js emits binary mouse protocol data via onBinary when the
  // application enables mouse tracking (DECSET 1000/1002/1003).
  xterm.onBinary(function (data) {
    if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
      tab.ws.send(JSON.stringify({ type: 'input', data: data }));
    }
  });

  function _focusPrimaryPane() {
    ctx.focusPane(tab.id, 'primary');
  }

  // Ensure xterm gets focus on click/focus inside its container.
  xtermContainer.addEventListener('click', _focusPrimaryPane);
  xtermContainer.addEventListener('focusin', _focusPrimaryPane);
}

function _createXtermInstance(ctx, xtermContainer) {
  // Verify xterm.js loaded from CDN
  if (typeof Terminal === 'undefined') {
    xtermContainer.innerHTML =
      '<div style="color:#f44747;padding:16px;font-family:monospace;">' +
      t('terminal.xtermLoadFailed') + '</div>';
    return null;
  }

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
  xterm.open(xtermContainer);
  ctx.installTerminalLinkProvider(xterm);
  try { fitAddon.fit(); } catch (e) { /* ignore initial fit errors */ }

  return { xterm: xterm, fitAddon: fitAddon };
}

function _initTerminalCore(ctx, tab) {
  _teardownTabXterm(tab);

  var pane = _createTerminalPane(ctx, tab);
  var termDiv = pane.termDiv;
  var xtermContainer = pane.xtermContainer;

  var created = _createXtermInstance(ctx, xtermContainer);
  if (!created) {
    tab.status = 'disconnected';
    if (ctx.bar) ctx.bar.setStatus(tab.id, 'disconnected');
    return;
  }

  tab.xterm = created.xterm;
  tab.fitAddon = created.fitAddon;
  ctx.loadCanvasAddon(created.xterm);
  tab._lastThumbnailAt = 0;

  _wireXtermIO(ctx, tab, created.xterm, xtermContainer, termDiv);

  // Show this terminal pane and measure its real size BEFORE connecting.
  // Without this, the WS init message carries xterm's default 80x24 (its
  // size before any layout pass), so the backend replays stored scrollback
  // wrapped at 80 cols even though the pane is actually e.g. 160 cols wide -
  // this is what produces garbled/misaligned text when reattaching to an
  // existing session (tab switch back, or reconnect after page refresh).
  ctx.showTabPane(tab.id);
  try { tab.fitAddon.fit(); } catch (e) { /* ignore, pane may still be 0-sized */ }

  // Connect WebSocket
  ctx.connectWebSocket(tab);

  // Re-fit once more after WS handshake in case layout settled late
  // (e.g. sidebar/host panel becoming visible asynchronously).
  setTimeout(function () {
    ctx.fitAndResize(tab, true);
  }, 100);
}
