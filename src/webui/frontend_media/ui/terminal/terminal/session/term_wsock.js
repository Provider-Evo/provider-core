// ========================= Terminal: WebSocket Connection & Messages =========================
// Split from terminal.js. Handles WebSocket connect, per-message-type dispatch,
// and disconnect/reconnect-on-close scheduling. Session discovery (probe/REST
// pre-fetch/existing-session recreation) and manual tab reconnect live in the
// sibling term_recon.js. Per-message-type handler functions and the
// WS_MSG_HANDLERS dispatch table live in the sibling wshndl.js.

function _attachWebSocketMethods(ctx) {
  ctx.connectWebSocket = function (tab) { _connectWebSocket(ctx, tab); };
}

function _handleWsOpen(tab) {
  // Send init message with terminal dimensions and connection parameters
  var cols = tab.xterm ? tab.xterm.cols : 80;
  var rows = tab.xterm ? tab.xterm.rows : 24;
  var initMsg = {
    type: 'init',
    kind: tab.kind,
    cols: cols,
    rows: rows,
    name: tab.name,
  };

  if (tab.kind === 'ssh') {
    initMsg.host = tab.options.host || '';
    initMsg.port = tab.options.port || 22;
    initMsg.username = tab.options.username || '';
    initMsg.password = tab.options.password || '';
    initMsg.key_data = tab.options.key_data || '';
    initMsg.connection_id = tab.options.connection_id || '';
  } else if (tab.options && tab.options.cwd) {
    initMsg.cwd = tab.options.cwd;
  }

  tab.ws.send(JSON.stringify(initMsg));
}

function _handleWsMessage(ctx, tab, event) {
  if (event.data instanceof ArrayBuffer) {
    _handleWsBinaryMessage(ctx, tab, event.data);
    return;
  }
  try {
    var msg = JSON.parse(event.data);
    _handleWsJsonMessage(ctx, tab, msg);
  } catch (e) {
    // ignore JSON parse errors
  }
}

function _scheduleWsReconnect(ctx, tab, ownerId) {
  tab._reconnectAttempts = (tab._reconnectAttempts || 0) + 1;
  if (tab._reconnectAttempts > 8) return;
  var delay = Math.min(500 * tab._reconnectAttempts, 8000);
  if (tab._reconnectTimer) clearTimeout(tab._reconnectTimer);
  tab._reconnectTimer = setTimeout(function () {
    if (tab._closing || !ctx.getTabById(ownerId)) return;
    if (tab.xterm) {
      tab.xterm.write(ctx.stripDecResponses('\r\n\x1b[33m[' + t('terminal.reconnectingMsg') + ']\x1b[0m'));
    }
    ctx.connectWebSocket(tab);
  }, delay);
}

function _handleWsClose(ctx, tab) {
  if (tab._closing) return;
  tab.ws = null;
  tab.status = 'disconnected';
  ctx.setBarStatus(tab, 'disconnected');
  // Split panes aren't tracked in ctx.tabs (only their parent tab is);
  // look up the owning tab so reconnection isn't skipped for splits.
  var ownerId = tab._isSplit ? tab._parentId : tab.id;
  if (tab._readOnly || !ctx.getTabById(ownerId)) return;
  // 页面进入 BFCache 时跳过 reconnect，pageshow 事件不会恢复 terminal session
  if (document.hidden) return;
  _scheduleWsReconnect(ctx, tab, ownerId);
}

function _handleWsError(ctx, tab) {
  tab.status = 'disconnected';
  ctx.setBarStatus(tab, 'disconnected');
  if (tab.xterm) {
    tab.xterm.write(ctx.stripDecResponses('\r\n\x1b[31m[' + t('terminal.wsError') + ']\x1b[0m'));
  }
}

function _connectWebSocket(ctx, tab) {
  var proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  var sessionId = tab.sessionId || tab.id;
  var wsUrl = proto + '//' + window.location.host + '/v1/webui/ws/terminal/' + sessionId;

  var ws = new WebSocket(wsUrl);
  ws.binaryType = 'arraybuffer';
  tab.ws = ws;

  ws.onopen = function () { _handleWsOpen(tab); };
  ws.onmessage = function (event) { _handleWsMessage(ctx, tab, event); };
  ws.onclose = function () { _handleWsClose(ctx, tab); };
  ws.onerror = function () { _handleWsError(ctx, tab); };
}
