function connectLogsSocket() {
  if (!window.WebSocket) {
    socketNotice.textContent = t('socket.unsupported');
    return;
  }
  if (logsSocket && (logsSocket.readyState === WebSocket.CONNECTING || logsSocket.readyState === WebSocket.OPEN)) {
    return;
  }

  var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  var url = protocol + '//' + window.location.host + '/v1/webui/ws/logs';
  logsSocket = new WebSocket(url);

  // Mutable bookkeeping shared with the helpers in actions_socket_helpers.js
  // (must load before this file, see index.html script order).
  var state = {
    reconnectAttempts: 0,
    maxReconnectAttempts: 999,
    maxReconnectDelay: 30000,
    baseReconnectDelay: 1000,
    staticChangedToastAt: 0,
    staticChangedToastCooldownMs: 60000,
  };

  logsSocket.onopen = function() {
    state.reconnectAttempts = 0;
    socketNotice.textContent = t('socket.connected');
    _updateLogsConnStatus(true);
  };
  logsSocket.onmessage = function(event) {
    _dispatchLogsSocketMessage(state, event);
  };
  logsSocket.onerror = function() {
    socketNotice.textContent = t('socket.error');
    _updateLogsConnStatus(false);
  };
  logsSocket.onclose = function() {
    socketNotice.textContent = t('socket.closed');
    _updateLogsConnStatus(false);
    // 页面进入 BFCache 时跳过 reconnect，pageshow 恢复时再重连
    if (!document.hidden) {
      _scheduleLogsReconnect(state);
    }
  };
}

window.addEventListener('pageshow', function(event) {
  if (event.persisted) {
    connectLogsSocket();
  }
});
