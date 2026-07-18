// ========================= Terminal: Session Discovery & Reconnect =========================
// Split from terminal.js. Handles startup session discovery (WS probe raced
// against a REST pre-fetch, whichever resolves first wins and recreates tab
// UI for surviving sessions) and manual single-tab reconnect from the
// context menu. Connection lifecycle and per-message dispatch live in the
// sibling term_wsock.js.

function _attachReconnectMethods(ctx) {
  _attachReconnectSubDiscovery(ctx);
  _attachReconnectSubProbeWs(ctx);
  _attachReconnectSubRestFetch(ctx);
  _attachReconnectSubManual(ctx);
}

function _buildReconnectTabRecord(sessionId, kind, name, options) {
  return {
    id: sessionId,
    kind: kind,
    name: name,
    status: 'connecting',
    xterm: null,
    fitAddon: null,
    ws: null,
    sessionId: sessionId,
    options: options || {},
    _resizeObserver: null,
    _container: null,
    _readOnly: false,
    _closing: false,
    _reconnectAttempts: 0,
    _reconnectTimer: null,
    color: null,
    split: null,
  };
}

function _resolveLastActiveTabId(sessions) {
  var lastId = null;
  try { lastId = localStorage.getItem('term_last_active_tab'); } catch (e) {}
  if (lastId) {
    for (var i = 0; i < sessions.length; i++) {
      if (sessions[i].session_id === lastId) return lastId;
    }
  }
  return null;
}

function _attachReconnectSubDiscovery(ctx) {

  function _recreateTabForSession(sess) {
    if (ctx.getTabById(sess.session_id)) return;
    var name = sess.name || (sess.kind === 'ssh' ? 'SSH' : t('terminal.localShell'));
    var options = {};
    if (sess.kind === 'ssh') {
      options.host = sess.host || '';
      options.port = sess.port || 22;
      options.username = sess.username || '';
    }
    var tab = _buildReconnectTabRecord(sess.session_id, sess.kind, name, options);
    tab._readOnly = !sess.alive;
    ctx.tabs.push(tab);
    ctx.bar.addTab({ id: tab.id, name: tab.name, kind: tab.kind, status: tab.status });
    ctx.initTerminal(tab);
  }

  function _reconnectExistingSessions(sessions) {
    if (ctx.discoveryProcessed) return;
    ctx.discoveryProcessed = true;
    for (var i = 0; i < sessions.length; i++) {
      if (!sessions[i].alive) continue;
      _recreateTabForSession(sessions[i]);
    }
    // 恢复上次激活的 tab；没有记录时默认第一个
    var targetId = _resolveLastActiveTabId(sessions);
    if (!targetId && ctx.tabs.length > 0) targetId = ctx.tabs[0].id;
    if (targetId) ctx.switchToTab(targetId);
  }

  ctx.reconnectExistingSessions = _reconnectExistingSessions;
}

function _attachReconnectSubProbeWs(ctx) {

  function _probeForDiscovery() {
    // Opening any terminal WS connection makes the backend send an
    // "existing_sessions" message before anything else (see
    // wshandlers._send_existing_sessions). Use a disposable session id so
    // this probe never collides with a real tab's session.
    var proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var probeId = 'probe-' + Date.now() + '-' + Math.random().toString(36).slice(2);
    var wsUrl = proto + '//' + window.location.host + '/v1/webui/ws/terminal/' + probeId;
    var probeWs;
    try {
      probeWs = new WebSocket(wsUrl);
    } catch (e) {
      return;
    }
    probeWs.onopen = function () {
      // 后端在 _sessions 为空时不发送 existing_sessions，probe 会永远挂起。
      // 3 秒后强制关闭，避免泄漏，与 backup v2.2.266 行为一致。
      setTimeout(function () {
        try { probeWs.close(); } catch (e) {}
      }, 3000);
    };
    probeWs.onmessage = function (event) {
      try {
        var msg = JSON.parse(event.data);
        if (msg.type === 'existing_sessions' && msg.sessions && msg.sessions.length > 0) {
          ctx.reconnectExistingSessions(msg.sessions);
        }
      } catch (e) {
        // ignore JSON parse errors
      }
      probeWs.close();
    };
    probeWs.onerror = function () {
      try { probeWs.close(); } catch (e) { /* ignore */ }
    };
  }

  ctx.probeForDiscovery = _probeForDiscovery;
}

function _attachReconnectSubRestFetch(ctx) {

  function _restPreFetch() {
    fetch('/v1/webui/terminal/sessions')
      .then(function (resp) { return resp.json(); })
      .then(function (sessions) {
        if (ctx.discoveryProcessed) return;
        if (!sessions || !Array.isArray(sessions)) return;
        var alive = sessions.filter(function (s) { return s.alive; });
        if (alive.length > 0) {
          ctx.reconnectExistingSessions(alive);
        }
      })
      .catch(function () {
        // ignore network errors; the WS probe may still succeed
      });
  }

  ctx.restPreFetch = _restPreFetch;
}

function _attachReconnectSubManual(ctx) {

  function _reconnectTab(tabId) {
    var tab = ctx.getTabById(tabId);
    if (!tab) return;
    if (tab.ws && tab.status === 'connected') return;
    tab._readOnly = false;
    tab._reconnectAttempts = 0;
    if (tab._reconnectTimer) {
      clearTimeout(tab._reconnectTimer);
      tab._reconnectTimer = null;
    }
    ctx.initTerminal(tab);
  }

  ctx.reconnectTab = _reconnectTab;
}
