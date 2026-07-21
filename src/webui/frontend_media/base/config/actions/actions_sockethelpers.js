/**
 * connectLogsSocket helper functions -- split out of actions_socket.js to
 * keep the main function under the line cap. Each helper receives the
 * mutable `state` object created in connectLogsSocket so it can read/update
 * reconnect bookkeeping without relying on shared module-level closures.
 */
function _scheduleLogsReconnect(state) {
  if (state.reconnectAttempts >= state.maxReconnectAttempts) {
    socketNotice.textContent = t('socket.reconnectLimit');
    return;
  }
  var delay = Math.min(state.baseReconnectDelay * Math.pow(2, Math.min(state.reconnectAttempts, 8)), state.maxReconnectDelay);
  state.reconnectAttempts++;
  socketNotice.textContent = t('socket.reconnecting', {
    delay: (delay / 1000).toFixed(1),
    attempt: state.reconnectAttempts,
  });
  setTimeout(function() {
    connectLogsSocket();
  }, delay);
}

function _updateLogsConnStatus(connected) {
  var el = document.getElementById('logConnStatus');
  var dot = document.getElementById('logConnDot');
  var text = document.getElementById('logConnText');
  if (el) el.classList.toggle('connected', connected);
  if (dot) {
    dot.classList.toggle('connected', connected);
    dot.classList.toggle('disconnected', !connected);
  }
  if (text) text.textContent = connected ? t('logs.connConnected') : t('logs.connDisconnected');
}

function _handleLogsStaticChanged(state, payload) {
  var now = Date.now();
  if (now - state.staticChangedToastAt < state.staticChangedToastCooldownMs) return;
  state.staticChangedToastAt = now;
  toast(payload.message || t('socket.staticHint'), 'info');
}

function _handleLogsPluginProgress(payload) {
  if (typeof window.PluginsPanel !== 'undefined' && typeof window.PluginsPanel.onProgress === 'function') {
    window.PluginsPanel.onProgress(payload.progress);
  }
}

function _handleLogsLogMessage(payload) {
  // 支持新格式（完整级别名 "INFO"）和旧格式（单字母 "I"）
  var level = payload.level || 'INFO';
  if (level.length === 1) {
    var levelMap = { 'D': 'DEBUG', 'I': 'INFO', 'W': 'WARNING', 'E': 'ERROR', 'C': 'CRITICAL', 'S': 'SUCCESS' };
    level = levelMap[level.toUpperCase()] || 'INFO';
  }
  addLogEntry({
    id: payload.id || '',
    timestamp: payload.timestamp || new Date().toISOString(),
    level: level,
    module: payload.module || '',
    message: payload.message,
    moduleColor: payload.moduleColor || '',
  });
}

function _dispatchLogsSocketMessage(state, event) {
  try {
    var payload = JSON.parse(event.data);
    if (payload.type === 'static_changed') {
      _handleLogsStaticChanged(state, payload);
      return;
    }
    if (payload.type === 'plugin_progress' && payload.progress) {
      _handleLogsPluginProgress(payload);
      return;
    }
    if (payload.type === 'summary_changed') {
      refreshAll();
      return;
    }
    if (payload.type === 'log' && payload.message) {
      _handleLogsLogMessage(payload);
    }
  } catch (error) {
    // Ignore parse errors
  }
}
