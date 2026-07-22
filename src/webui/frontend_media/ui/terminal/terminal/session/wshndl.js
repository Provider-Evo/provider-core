// ========================= Terminal: WebSocket Message Handlers =========================
// Split from term_wsock.js -- per-message-type handler functions and
// the WS_MSG_HANDLERS dispatch table used by _attachWebSocketMethods. Kept
// as top-level functions (not nested closures) so each stays independently
// under the line-length budget; ctx is threaded through explicitly.

function _handleWsBinaryMessage(ctx, tab, data) {
  if (tab.xterm && data.byteLength > 5) {
    var payload = new Uint8Array(data, 5);
    var text = ctx.utf8Decoder.decode(payload);
    var filtered = ctx.stripDecResponses(text);
    if (filtered) tab.xterm.write(filtered);
  }
}

function _handleWsReady(ctx, tab) {
  tab.status = 'connected';
  tab._reconnectAttempts = 0;
  if (tab._reconnectTimer) {
    clearTimeout(tab._reconnectTimer);
    tab._reconnectTimer = null;
  }
  ctx.setBarStatus(tab, 'connected');
  // Send initial dimensions after backend is ready
  ctx.fitAndResize(tab, true);
}

function _handleWsOutput(ctx, tab, msg) {
  if (!tab.xterm) return;
  // Filter out DEC private mode responses that leak through ConPTY
  // (e.g. ^[[?1;2c device-attributes response).  xterm.js handles
  // these internally; they should not appear as visible text.
  var filtered = ctx.stripDecResponses(msg.data);
  if (filtered) {
    tab.xterm.write(filtered);
  }
}

function _handleWsExit(ctx, tab, msg) {
  if (tab._closing) return;
  if (tab.xterm) {
    if (msg.code === -1) {
      // Non-reattachable session (recovered after server restart)
      tab.xterm.write(ctx.stripDecResponses(
        '\r\n\x1b[33m[' + t('terminal.sessionHistorical') + ']\x1b[0m\r\n'
      ));
      tab._readOnly = true;
      if (ctx.bar) ctx.bar.setTitle(tab.id, tab.name + ' [' + t('terminal.historical') + ']');
    } else {
      tab.xterm.write(ctx.stripDecResponses(
        '\r\n\x1b[33m[' + t('terminal.processExited', { code: msg.code }) + ']\x1b[0m'
      ));
    }
  }
  tab.status = 'disconnected';
  ctx.setBarStatus(tab, 'disconnected');
}

function _handleWsMetadata(ctx, tab, msg) {
  // Subprocess monitoring metadata
  if (msg.has_running_subprocess !== undefined) {
    tab._hasRunningSubprocess = msg.has_running_subprocess;
    tab._childCommandLabel = msg.child_command_label || null;
    ctx.updateTabTitle(tab);
  }
}

function _handleWsReadyMsg(ctx, tab, msg) {
  tab.sessionId = msg.session_id;
  _handleWsReady(ctx, tab);
  if (tab._isSplit && typeof ctx.onSplitPaneReady === 'function') {
    ctx.onSplitPaneReady(tab);
  } else if (tab.split && tab.split.sessionId && typeof ctx.saveSplitLayout === 'function') {
    ctx.saveSplitLayout(tab, tab.split, tab._activePane);
  }
}

function _handleWsModeMsg(ctx, tab, msg) {
  // Backend signals ConPTY (real PTY) or pipe fallback.  With xterm.js,
  // both modes work the same way on the frontend: all input is
  // forwarded, all output is rendered.  The PTY/pipe echo behavior is
  // handled entirely by the backend.
  tab._mode = msg.mode;
}

function _handleWsErrorMsg(ctx, tab, msg) {
  if (tab._closing) return;
  if (tab.xterm) {
    tab.xterm.write(ctx.stripDecResponses('\r\n\x1b[31m' + t('terminal.errorPrefix', { message: msg.message }) + '\x1b[0m'));
  }
  tab.status = 'disconnected';
  ctx.setBarStatus(tab, 'disconnected');
}

function _handleWsSessionClosedMsg() {
  // Backend confirms the session was killed (response to close_session)
  // Tab is already being cleaned up by closeTab()
}

function _handleWsExistingSessionsMsg(ctx, tab, msg) {
  // Backend advertises surviving sessions from a previous connection.
  // Recreate tab UI and reconnect WebSocket for each alive session.
  // Skip if discovery was already handled by probe or REST pre-fetch.
  if (!ctx.discoveryProcessed && msg.sessions && msg.sessions.length > 0) {
    ctx.reconnectExistingSessions(msg.sessions);
  }
}

// Dispatch table: msg.type -> handler(ctx, tab, msg).
var WS_MSG_HANDLERS = {
  ready: _handleWsReadyMsg,
  mode: _handleWsModeMsg,
  output: _handleWsOutput,
  error: _handleWsErrorMsg,
  exit: _handleWsExit,
  session_closed: _handleWsSessionClosedMsg,
  metadata: _handleWsMetadata,
  existing_sessions: _handleWsExistingSessionsMsg,
};

function _handleWsJsonMessage(ctx, tab, msg) {
  var handler = WS_MSG_HANDLERS[msg.type];
  if (handler) handler(ctx, tab, msg);
}
