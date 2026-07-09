function copyText(text, successMessage) {
  var copyPromise;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    copyPromise = navigator.clipboard.writeText(text);
  } else {
    // Fallback for insecure contexts (HTTP)
    var textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.style.top = '-9999px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    var success = false;
    try {
      success = document.execCommand('copy');
    } catch (e) {
      console.error('Copy failed:', e);
    }
    document.body.removeChild(textarea);
    copyPromise = success ? Promise.resolve() : Promise.reject(new Error('Copy failed'));
  }
  copyPromise.then(function() {
    toast(successMessage, 'ok');
  }).catch(function(error) {
    toast(t('actions.copyFailed', { error: String(error) }), 'error');
  });
}

function exportSummary() {
  const payload = JSON.stringify(state.summary || {}, null, 2);
  const blob = new Blob([payload], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'provider-summary.json';
  link.click();
  URL.revokeObjectURL(url);
  toast(t('actions.exportSummaryOk'), 'ok');
}

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

  var reconnectAttempts = 0;
  var maxReconnectAttempts = 999;
  var maxReconnectDelay = 30000;
  var baseReconnectDelay = 1000;
  var _staticChangedToastAt = 0;
  var _staticChangedToastCooldownMs = 60000;

  function scheduleReconnect() {
    if (reconnectAttempts >= maxReconnectAttempts) {
      socketNotice.textContent = t('socket.reconnectLimit');
      return;
    }
    var delay = Math.min(baseReconnectDelay * Math.pow(2, Math.min(reconnectAttempts, 8)), maxReconnectDelay);
    reconnectAttempts++;
    socketNotice.textContent = t('socket.reconnecting', {
      delay: (delay / 1000).toFixed(1),
      attempt: reconnectAttempts,
    });
    setTimeout(function() {
      connectLogsSocket();
    }, delay);
  }

  function _updateConnStatus(connected) {
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

  logsSocket.onopen = function() {
    reconnectAttempts = 0;
    socketNotice.textContent = t('socket.connected');
    _updateConnStatus(true);
  };
  logsSocket.onmessage = function(event) {
    try {
      var payload = JSON.parse(event.data);
      if (payload.type === 'static_changed') {
        var now = Date.now();
        if (now - _staticChangedToastAt < _staticChangedToastCooldownMs) return;
        _staticChangedToastAt = now;
        toast(payload.message || t('socket.staticHint'), 'info');
        return;
      }
      if (payload.type === 'plugin_progress' && payload.progress) {
        if (typeof window.PluginsPanel !== 'undefined' && typeof window.PluginsPanel.onProgress === 'function') {
          window.PluginsPanel.onProgress(payload.progress);
        }
        return;
      }
      if (payload.type === 'log' && payload.message) {
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
    } catch (error) {
      // Ignore parse errors
    }
  };
  logsSocket.onerror = function() {
    socketNotice.textContent = t('socket.error');
    _updateConnStatus(false);
  };
  logsSocket.onclose = function() {
    socketNotice.textContent = t('socket.closed');
    _updateConnStatus(false);
    scheduleReconnect();
  };
}

async function refreshAll() {
  try {
    const [summaryResult, healthResult] = await Promise.allSettled([
      fetchJson('/v1/webui/summary'),
      fetchJson('/health')
    ]);
    if (summaryResult.status === 'fulfilled') {
      state.summary = summaryResult.value;
      state.modelsLoaded = true;
      renderOverview(summaryResult.value);
      if (typeof renderConfig === 'function') renderConfig(summaryResult.value);
      if (state.activeTab === 'config' && typeof activateConfigPanel === 'function') {
        activateConfigPanel(summaryResult.value);
      }
      var models = summaryResult.value.models || [];
      renderModels(models);
      renderPlatforms(summaryResult.value.platforms || {});
      if (typeof populateModelDropdowns === 'function') {
        populateModelDropdowns(models);
      }
    } else {
      state.modelsLoaded = false;
      if (typeof populateModelDropdowns === 'function') {
        populateModelDropdowns(null, { error: true });
      }
      // API failed, show error state
      if (document.getElementById('versionValue')) {
        document.getElementById('versionValue').textContent = t('overview.loadFailed');
      }
      if (document.getElementById('modelsValue')) {
        document.getElementById('modelsValue').textContent = t('overview.loadFailed');
      }
      if (modelGrid) {
        modelGrid.innerHTML = '<div class="text-muted p-[18px] border border-dashed border-border rounded-xl text-center">' + t('overview.loadFailed') + '</div>';
      }
    }
    if (healthResult.status === 'fulfilled') {
      document.getElementById('healthValue').textContent = healthResult.value && healthResult.value.status ? healthResult.value.status : 'degraded';
    } else {
      if (document.getElementById('healthValue')) {
        document.getElementById('healthValue').textContent = t('overview.unknown');
      }
    }
    document.getElementById('lastRefresh').textContent = new Date().toLocaleTimeString();
  } catch (error) {
    toast(t('overview.refreshFailed', { error: String(error) }), 'error');
  }
}

async function refreshModels() {
  try {
    const result = await fetchJson('/v1/admin/refresh_models', { method: 'POST' });
    toast(t('actions.modelsRefreshOk'), 'ok');
    await refreshAll();
  } catch (error) {
    toast(t('actions.modelsRefreshFailed', { error: String(error) }), 'error');
  }
}

function populateModelDropdowns(models, options) {
  options = options || {};
  if (options.error) {
    var errOpt = [{ value: '', text: t('overview.loadFailed') }];
    ['chatModelSelect', 'voiceSttModel', 'voiceTtsModel'].forEach(function(id) {
      var dd = window._dropdowns && window._dropdowns[id];
      if (dd) dd.setOptions(errOpt, false);
    });
    return;
  }
  if (!Array.isArray(models)) return;

  function isSttModel(model) {
    var caps = model.capabilities || {};
    var id = String(model.id || '').toLowerCase();
    if (caps.audio_transcription || caps.audio_in) return true;
    if (caps.chat && caps.vision) return true;
    if (/whisper|transcribe|paraformer|speech-to-text/.test(id)) return true;
    return false;
  }

  function isTtsModel(model) {
    var caps = model.capabilities || {};
    var ownedBy = String(model.owned_by || '');
    if (!caps.audio_gen && !caps.tts) return false;
    if (ownedBy === 'edgetts' || ownedBy === 'gtts' || ownedBy === 'openaifm') return true;
    return !!(caps.audio_gen && !caps.chat);
  }

  var chatOpts = [];
  var autoSelect = null;
  for (var i = 0; i < models.length; i++) {
    var caps = models[i].capabilities || {};
    if (!caps.chat) continue;
    chatOpts.push({ value: models[i].id, text: models[i].id });
    if (models[i].id === 'qwen3.7-max') autoSelect = models[i].id;
  }
  var chatDropdown = window._dropdowns && window._dropdowns['chatModelSelect'];
  if (chatDropdown) {
    if (!chatOpts.length) {
      chatDropdown.setOptions([{ value: '', text: t('models.noMatch') }], false);
    } else {
      chatDropdown.setOptions(chatOpts, false);
      var saved = (typeof window._savedChatModel === 'string' && window._savedChatModel) ? window._savedChatModel : null;
      if (saved) {
        for (var j = 0; j < chatOpts.length; j++) {
          if (chatOpts[j].value === saved) {
            chatDropdown.setValue(saved);
            if (typeof window !== 'undefined') window._savedChatModel = null;
            saved = null;
            break;
          }
        }
      }
      if (saved === null && autoSelect) chatDropdown.setValue(autoSelect);
      else if (saved === null && chatOpts.length > 0) chatDropdown.setValue(chatOpts[0].value);
    }
  }

  var sttOpts = [{ value: '', text: t('common.notUsing') }];
  var ttsOpts = [{ value: '', text: t('common.notUsing') }];
  for (var k = 0; k < models.length; k++) {
    if (isSttModel(models[k])) {
      sttOpts.push({ value: models[k].id, text: models[k].id });
    }
    if (isTtsModel(models[k])) {
      ttsOpts.push({ value: models[k].id, text: models[k].id });
    }
  }
  var sttDropdown = window._dropdowns && window._dropdowns['voiceSttModel'];
  var ttsDropdown = window._dropdowns && window._dropdowns['voiceTtsModel'];
  if (sttDropdown) {
    if (sttOpts.length <= 1) {
      sttDropdown.setOptions([{ value: '', text: t('models.noMatch') }], false);
    } else {
      sttDropdown.setOptions(sttOpts, false);
      var vs = (typeof loadVoiceSettings === 'function') ? loadVoiceSettings() : {};
      if (vs.sttModel) sttDropdown.setValue(vs.sttModel);
    }
  }
  if (ttsDropdown) {
    if (ttsOpts.length <= 1) {
      ttsDropdown.setOptions([{ value: '', text: t('models.noMatch') }], false);
    } else {
      ttsDropdown.setOptions(ttsOpts, false);
      var vs2 = (typeof loadVoiceSettings === 'function') ? loadVoiceSettings() : {};
      if (vs2.ttsModel) ttsDropdown.setValue(vs2.ttsModel);
    }
  }
}

async function saveConfig() {
  try {
    var isWebui = typeof getConfigTarget === 'function' && getConfigTarget() === 'webui';
    var isSource = typeof getConfigEditMode === 'function' && getConfigEditMode() === 'source';

    if (isSource) {
      var editor = document.getElementById('configTomlEditor');
      var rawContent = editor ? editor.value : '';
      var rawUrl = isWebui ? '/v1/webui/config/raw' : '/v1/config/raw';
      var response = await fetch(rawUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ raw_content: rawContent }),
      });
      var result = await response.json();
      if (!response.ok || result.error) {
        var errEl = document.getElementById('configTomlError');
        var errMsg = result.error || (typeof t === 'function' ? t('actions.unknownError') : 'unknown error');
        if (errEl) {
          errEl.textContent = errMsg;
          errEl.classList.remove('hidden');
        }
        toast(t('actions.configSaveFailed', { error: errMsg }), 'error');
        return;
      }
      state.configDirty = false;
      updateConfigSaveStatus();
      if (typeof _updateConfigSaveBtn === 'function') _updateConfigSaveBtn();
      var errHide = document.getElementById('configTomlError');
      if (errHide) errHide.classList.add('hidden');
      toast(t('actions.configSaveOk'), 'ok');
      if (typeof _lastConfigSaveTime !== 'undefined') _lastConfigSaveTime = Date.now();
      if (isWebui && typeof _applyWebuiRuntime === 'function') {
        var cfgResp = await fetch('/v1/webui/config');
        if (cfgResp.ok) _applyWebuiRuntime(await cfgResp.json());
      } else if (!isWebui) {
        await refreshAll();
      }
      return;
    }

    if (typeof _syncConfigFromDOM === 'function') _syncConfigFromDOM();
    var configData;
    if (window._currentConfig) {
      configData = window._currentConfig;
    } else {
      const url = isWebui ? '/v1/webui/config' : '/v1/config';
      configData = await fetchJson(url);
    }
    const url = isWebui ? '/v1/webui/config' : '/v1/config';
    const response = await fetch(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(configData)
    });
    const result = await response.json();
    if (result.status === 'ok') {
      state.configDirty = false;
      updateConfigSaveStatus();
      if (typeof _updateConfigSaveBtn === 'function') _updateConfigSaveBtn();
      toast(t('actions.configSaveOk'), 'ok');
      if (typeof _lastConfigSaveTime !== 'undefined') _lastConfigSaveTime = Date.now();
      if (isWebui && typeof _applyWebuiRuntime === 'function') _applyWebuiRuntime(configData);
      if (!isWebui) await refreshAll();
    } else {
      toast(t('actions.configSaveFailed', { error: result.error || t('actions.unknownError') }), 'error');
    }
  } catch (error) {
    toast(t('actions.configSaveFailed', { error: String(error) }), 'error');
  }
}

// ========================= Restart Overlay =========================

var _restartState = 'idle'; // idle | requesting | restarting | checking | success | failed
var _restartProgress = 0;
var _restartElapsed = 0;
var _restartTimer = null;
var _restartProgressTimer = null;
var _restartCheckTimer = null;
var _restartCheckAttempts = 0;

var _RESTART_CONFIG = {
  INITIAL_DELAY: 3000,
  CHECK_INTERVAL: 2000,
  CHECK_TIMEOUT: 3000,
  MAX_ATTEMPTS: 60,
  PROGRESS_INTERVAL: 200,
  SUCCESS_REDIRECT_DELAY: 1500,
};

var _RESTART_KEY_MAP = {
  requesting: { title: 'restart.preparing', desc: 'restart.preparingDesc' },
  restarting: { title: 'restart.restarting', desc: 'restart.restartingDesc' },
  checking: { title: 'restart.checking', desc: 'restart.checkingDesc' },
  success: { title: 'restart.success', desc: 'restart.successDesc' },
  failed: { title: 'restart.failed', desc: 'restart.failedDesc' },
};

function _restartText(status, field) {
  var keys = _RESTART_KEY_MAP[status] || _RESTART_KEY_MAP.requesting;
  var key = keys[field];
  if (status === 'checking' && field === 'desc') {
    return t(key, {
      current: _restartCheckAttempts,
      max: _RESTART_CONFIG.MAX_ATTEMPTS,
    });
  }
  return t(key);
}

function _restartSetState(status) {
  _restartState = status;
  var overlay = document.getElementById('restartOverlay');
  var spinner = document.getElementById('restartSpinner');
  var check = document.getElementById('restartCheck');
  var fail = document.getElementById('restartFail');
  var pulse = document.getElementById('restartPulse');
  var title = document.getElementById('restartTitle');
  var desc = document.getElementById('restartDesc');
  var actions = document.getElementById('restartActions');

  if (!overlay) return;

  overlay.classList.remove('is-success', 'is-failed');
  if (status === 'success') overlay.classList.add('is-success');
  if (status === 'failed') overlay.classList.add('is-failed');

  // Icons
  var showSpinner = (status === 'requesting' || status === 'restarting' || status === 'checking');
  var showCheck = (status === 'success');
  var showFail = (status === 'failed');
  if (spinner) spinner.style.display = showSpinner ? '' : 'none';
  if (check) check.style.display = showCheck ? '' : 'none';
  if (fail) fail.style.display = showFail ? '' : 'none';
  if (pulse) pulse.classList.toggle('hidden', !showSpinner);

  // Text
  if (title) {
    title.textContent = _restartText(status, 'title');
    title.setAttribute('data-i18n', _RESTART_KEY_MAP[status] ? _RESTART_KEY_MAP[status].title : 'restart.preparing');
  }
  if (desc) {
    desc.textContent = _restartText(status, 'desc');
    if (_RESTART_KEY_MAP[status]) desc.setAttribute('data-i18n', _RESTART_KEY_MAP[status].desc);
  }

  // Actions
  if (actions) {
    actions.style.display = (status === 'success' || status === 'failed') ? '' : 'none';
  }
}

function _restartUpdateProgress(percent) {
  _restartProgress = Math.min(percent, 100);
  var bar = document.getElementById('restartProgressBar');
  var pct = document.getElementById('restartPercent');
  if (bar) bar.style.width = _restartProgress + '%';
  if (pct) pct.textContent = Math.round(_restartProgress) + '%';
}

function _restartUpdateElapsed() {
  _restartElapsed++;
  var el = document.getElementById('restartElapsed');
  if (el) el.textContent = t('restart.elapsed', { seconds: _restartElapsed });
}

function _restartStartProgressTimer() {
  _restartProgress = 0;
  _restartElapsed = 0;
  _restartUpdateProgress(0);
  _restartUpdateElapsed();
  _restartProgressTimer = setInterval(function() {
    if (_restartProgress < 90) {
      _restartUpdateProgress(_restartProgress + 1);
    }
  }, _RESTART_CONFIG.PROGRESS_INTERVAL);
  _restartTimer = setInterval(function() {
    _restartUpdateElapsed();
  }, 1000);
}

function _restartStopTimers() {
  if (_restartProgressTimer) { clearInterval(_restartProgressTimer); _restartProgressTimer = null; }
  if (_restartTimer) { clearInterval(_restartTimer); _restartTimer = null; }
  if (_restartCheckTimer) { clearTimeout(_restartCheckTimer); _restartCheckTimer = null; }
}

function _restartStartHealthCheck() {
  _restartCheckAttempts = 0;
  _restartSetState('checking');

  function _doCheck() {
    _restartCheckAttempts++;
    var controller = new AbortController();
    var timeout = setTimeout(function() { controller.abort(); }, _RESTART_CONFIG.CHECK_TIMEOUT);

    fetch('/v1/webui/system/status', {
      signal: controller.signal,
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
    })
      .then(function(resp) {
        clearTimeout(timeout);
        if (resp.ok) {
          return resp.json();
        }
        throw new Error('not ok');
      })
      .then(function(data) {
        if (data && data.running) {
          _restartOnSuccess();
          return;
        }
        _restartScheduleNext();
      })
      .catch(function() {
        clearTimeout(timeout);
        _restartScheduleNext();
      });
  }

  function _restartScheduleNext() {
    if (_restartCheckAttempts >= _RESTART_CONFIG.MAX_ATTEMPTS) {
      _restartOnFailed();
      return;
    }
    _restartCheckTimer = setTimeout(_doCheck, _RESTART_CONFIG.CHECK_INTERVAL);
  }

  _doCheck();
}

function _restartOnSuccess() {
  _restartStopTimers();
  _restartUpdateProgress(100);
  _restartSetState('success');
  setTimeout(function() { location.reload(); }, _RESTART_CONFIG.SUCCESS_REDIRECT_DELAY);
}

function _restartOnFailed() {
  _restartStopTimers();
  _restartSetState('failed');
}

function _restartShowOverlay() {
  var overlay = document.getElementById('restartOverlay');
  if (overlay) {
    overlay.style.display = 'flex';
    requestAnimationFrame(function() {
      requestAnimationFrame(function() {
        overlay.classList.add('is-visible');
      });
    });
  }
}

function triggerRestart(options) {
  options = options || {};
  var skipApiCall = Boolean(options.skipApiCall);

  if (_restartState !== 'idle' && _restartState !== 'failed') {
    return;
  }

  _restartShowOverlay();
  _restartSetState(skipApiCall ? 'restarting' : 'requesting');
  _restartStartProgressTimer();

  if (skipApiCall) {
    setTimeout(_restartStartHealthCheck, _RESTART_CONFIG.INITIAL_DELAY);
    return;
  }

  // Send restart request (server will die, so timeout is expected)
  var controller = new AbortController();
  var timeout = setTimeout(function() { controller.abort(); }, 5000);

  fetch('/v1/admin/reload', { method: 'POST', signal: controller.signal })
    .then(function(resp) {
      clearTimeout(timeout);
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp.json();
    })
    .then(function(result) {
      if (result.status === 'ok') {
        _restartSetState('restarting');
        setTimeout(_restartStartHealthCheck, _RESTART_CONFIG.INITIAL_DELAY);
      } else {
        _restartStopTimers();
        _restartSetState('failed');
      }
    })
    .catch(function() {
      // Timeout or network error = server is dying, which is expected
      clearTimeout(timeout);
      _restartSetState('restarting');
      setTimeout(_restartStartHealthCheck, _RESTART_CONFIG.INITIAL_DELAY);
    });
}

function _restartTrigger() {
  triggerRestart();
}

function reloadServer() {
  showConfirmDialog(t('restart.confirmMessage'), {
    title: t('restart.confirmTitle'),
    confirmText: t('restart.confirmButton'),
    cancelText: t('common.cancel'),
  }).then(function(confirmed) {
    if (confirmed) {
      _restartTrigger();
    }
  });
}

function retryHealthCheck() {
  _restartCheckAttempts = 0;
  _restartStartHealthCheck();
}

async function reloadConfigFromFile() {
  try {
    const isWebui = typeof getConfigTarget === 'function' && getConfigTarget() === 'webui';
    const isSource = typeof getConfigEditMode === 'function' && getConfigEditMode() === 'source';
    const url = isWebui ? '/v1/webui/config/reload' : '/v1/config/reload';
    const response = await fetch(url, { method: 'POST' });
    const result = await response.json();
    if (result.status === 'ok') {
      state.configDirty = false;
      updateConfigSaveStatus();
      if (typeof _updateConfigSaveBtn === 'function') _updateConfigSaveBtn();
      toast(t('config.reloadOk'), 'ok');
      if (isSource && typeof _loadConfigRaw === 'function') {
        _loadConfigRaw();
      } else if (typeof forceRenderConfig === 'function') {
        forceRenderConfig(state.summary);
      } else if (isWebui && typeof renderConfig === 'function') {
        renderConfig(state.summary);
      } else {
        await refreshAll();
      }
    } else {
      toast(t('config.reloadFailed', { error: result.error || t('common.failed') }), 'error');
    }
  } catch (error) {
    toast(t('config.reloadFailed', { error: String(error) }), 'error');
  }
}

function onConfigFieldChange(e) {
  // Config field changes are now handled by _onConfigChange in render.js
}

async function loadAutoupdateSettings() {
  try {
    const result = await fetchJson('/v1/admin/autoupdate');
    if (result.success) {
      const d = result.data;
      document.getElementById('autoupdateEnabled').checked = d.enabled || false;
      document.getElementById('autoupdateBranch').value = d.branch || 'dev';
      document.getElementById('autoupdateInterval').value = d.interval || 300;
      var diffEl = document.getElementById('autoupdateDiffUpdate');
      if (diffEl) diffEl.checked = d.diff_update !== false;
      document.getElementById('autoupdateStatus').textContent = d.enabled ? t('autoupdate.statusEnabled') : t('autoupdate.statusDisabled');
      // Render mirrors
      _renderMirrors(d.mirrors || []);
      // Show last check if available
      if (d.last_check && d.last_check.status) {
        _showCheckResults(d.last_check);
      }
    }
  } catch (error) {
    toast(t('autoupdate.loadFailed', { error: String(error) }), 'error');
  }
}

var _mirrorList = null;

function _renderMirrors(mirrors) {
  var list = document.getElementById('autoupdateMirrorsList');
  if (!list) return;
  if (!_mirrorList) {
    _mirrorList = new SortableList(list, {
      renderItem: function(value, index) {
        return '<input type="text" class="config-input mirror-url" value="' + escapeHtml(value) + '" style="width:100%;">';
      },
      getItemValue: function(el, index) {
        var inp = el.querySelector('.mirror-url');
        return inp ? inp.value.trim() : '';
      },
      onChange: function() { /* items changed, will be collected on save */ },
      placeholder: t('autoupdate.noMirrors'),
    });
  }
  _mirrorList.setItems(mirrors);
}

function _getMirrorsFromUI() {
  if (_mirrorList) return _mirrorList.getItems().filter(function(v) { return v; });
  var inputs = document.querySelectorAll('#autoupdateMirrorsList .mirror-url');
  var arr = [];
  inputs.forEach(function(inp) { if (inp.value.trim()) arr.push(inp.value.trim()); });
  return arr;
}

async function saveAutoupdateSettings() {
  try {
    var body = {
      enabled: document.getElementById('autoupdateEnabled').checked,
      branch: document.getElementById('autoupdateBranch').value.trim() || 'dev',
      interval: parseInt(document.getElementById('autoupdateInterval').value) || 300,
      diff_update: document.getElementById('autoupdateDiffUpdate').checked,
      mirrors: _getMirrorsFromUI()
    };
    var resp = await fetch('/v1/admin/autoupdate', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    var data = await resp.json();
    if (data.success) {
      document.getElementById('autoupdateStatus').textContent = data.data.enabled ? t('autoupdate.statusEnabled') : t('autoupdate.statusDisabled');
      toast(t('autoupdate.saveOk'), 'ok');
    } else {
      toast(t('autoupdate.saveFailed', { error: data.error || t('actions.unknownError') }), 'error');
    }
  } catch (error) {
    toast(t('autoupdate.saveFailed', { error: String(error) }), 'error');
  }
}

function _showCheckResults(d) {
  var panel = document.getElementById('autoupdateResults');
  var statusEl = document.getElementById('autoupdateResultStatus');
  var metaEl = document.getElementById('autoupdateResultMeta');
  var filesEl = document.getElementById('autoupdateChangedFiles');
  var actionBtns = document.getElementById('autoupdateActionBtns');
  var searchInput = document.getElementById('autoupdateSearchInput');
  var selectedCount = document.getElementById('autoupdateSelectedCount');
  var applyBtn = document.getElementById('autoupdateApplyBtn');
  if (!panel) return;
  panel.classList.remove('hidden');

  // Hide toolbar and action buttons by default
  if (actionBtns) actionBtns.style.display = 'none';
  if (searchInput) searchInput.style.display = 'none';
  if (applyBtn) applyBtn.classList.add('hidden');

  if (d.status === 'error') {
    statusEl.textContent = '[error]';
    statusEl.style.color = 'var(--err)';
    metaEl.textContent = d.message || t('autoupdate.checkFailed');
    filesEl.innerHTML = '';
    return;
  }

  if (!d.has_update) {
    statusEl.textContent = t('autoupdate.upToDate');
    statusEl.style.color = 'var(--ok)';
    metaEl.textContent = (d.local_hash || '') + ' = ' + (d.remote_hash || '') + ' (mirror: ' + (d.mirror || '') + ')';
    filesEl.innerHTML = '';
    return;
  }

  var files = d.changed_files || [];
  statusEl.textContent = t('autoupdate.filesChanged', { count: files.length });
  statusEl.style.color = 'var(--warn)';
  metaEl.textContent = (d.local_hash || '?') + ' -> ' + (d.remote_hash || '?') + ' (mirror: ' + (d.mirror || '') + ')';

  // Show search box only when >5 files
  if (searchInput) {
    searchInput.style.display = files.length > 5 ? '' : 'none';
    searchInput.value = '';
  }

  // Show action buttons
  if (actionBtns) actionBtns.style.display = '';

  function _renderFileList(filter) {
    var filtered = filter ? files.filter(function(f) { return f.toLowerCase().indexOf(filter) !== -1; }) : files;
    var html = filtered.map(function(f) {
      return '<label class="flex items-center gap-2" style="padding:2px 0;cursor:pointer;">'
        + '<input type="checkbox" class="autoupdate-file-check" value="' + escapeHtml(f) + '" checked>'
        + '<span class="text-[12px] font-mono autoupdate-file-link" data-file="' + escapeHtml(f) + '" style="color:var(--accent);cursor:pointer;text-decoration:underline;" title="' + escapeHtml(t('autoupdate.viewDiff')) + '">' + escapeHtml(f) + '</span>'
        + '</label>';
    }).join('');
    filesEl.innerHTML = html || '<div class="text-muted" style="padding:8px;">' + escapeHtml(t('autoupdate.noMatchingFiles')) + '</div>';
    _bindFileEvents();
    _updateSelectedCount();
  }

  function _updateSelectedCount() {
    var checked = filesEl.querySelectorAll('.autoupdate-file-check:checked').length;
    var total = filesEl.querySelectorAll('.autoupdate-file-check').length;
    if (selectedCount) selectedCount.textContent = t('autoupdate.selectedCount', { checked: checked, total: total });
  }

  function _bindFileEvents() {
    filesEl.querySelectorAll('.autoupdate-file-link').forEach(function(link) {
      link.addEventListener('click', function(e) {
        e.preventDefault();
        e.stopPropagation();
        _showFileDiff(link.dataset.file);
      });
    });
    filesEl.querySelectorAll('.autoupdate-file-check').forEach(function(cb) {
      cb.addEventListener('change', _updateSelectedCount);
    });
  }

  // Search input handler
  if (searchInput) {
    searchInput.oninput = function() {
      _renderFileList(searchInput.value.toLowerCase());
    };
  }

  // Select all / none buttons
  var selectAllBtn = document.getElementById('autoupdateSelectAllBtn');
  var selectNoneBtn = document.getElementById('autoupdateSelectNoneBtn');
  if (selectAllBtn) {
    selectAllBtn.onclick = function() {
      filesEl.querySelectorAll('.autoupdate-file-check').forEach(function(cb) { cb.checked = true; });
      _updateSelectedCount();
    };
  }
  if (selectNoneBtn) {
    selectNoneBtn.onclick = function() {
      filesEl.querySelectorAll('.autoupdate-file-check').forEach(function(cb) { cb.checked = false; });
      _updateSelectedCount();
    };
  }

  // Confirm button -> apply update
  var confirmBtn = document.getElementById('autoupdateConfirmBtn');
  if (confirmBtn) {
    confirmBtn.onclick = function() { applyAutoupdate(); };
  }

  // Cancel button -> hide results
  var cancelBtn = document.getElementById('autoupdateCancelBtn');
  if (cancelBtn) {
    cancelBtn.onclick = function() {
      panel.classList.add('hidden');
      if (applyBtn) applyBtn.classList.add('hidden');
    };
  }

  // Initial render
  _renderFileList('');
}

async function _showFileDiff(filepath) {
  // Create or reuse diff dialog
  var overlay = document.getElementById('autoupdateDiffOverlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'autoupdateDiffOverlay';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;padding:16px;';
    overlay.innerHTML = '<div style="background:var(--panel);border:1px solid var(--border);border-radius:16px;max-width:1200px;width:100%;max-height:85vh;display:flex;flex-direction:column;overflow:hidden;padding:16px;">'
      + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
      + '<strong id="autoupdateDiffTitle" style="font-size:14px;font-family:monospace;"></strong>'
      + '<button id="autoupdateDiffClose" type="button" style="cursor:pointer;font-size:20px;border:none;background:none;color:var(--text);">&times;</button>'
      + '</div>'
      + '<div id="autoupdateDiffContent" style="flex:1;overflow:auto;display:grid;grid-template-columns:1fr 1fr;gap:8px;">'
      + '<div id="diffLeft" style="overflow:auto;font-size:12px;line-height:1.5;padding:12px;background:var(--panel-alt);border:1px solid var(--border);border-radius:8px;white-space:pre-wrap;word-break:break-all;font-family:monospace;"><div style="font-size:11px;color:var(--muted);margin-bottom:8px;font-weight:600;">' + escapeHtml(t('autoupdate.diffOld')) + '</div><pre id="diffLeftPre" style="margin:0;white-space:pre-wrap;"></pre></div>'
      + '<div id="diffRight" style="overflow:auto;font-size:12px;line-height:1.5;padding:12px;background:var(--panel-alt);border:1px solid var(--border);border-radius:8px;white-space:pre-wrap;word-break:break-all;font-family:monospace;"><div style="font-size:11px;color:var(--muted);margin-bottom:8px;font-weight:600;">' + escapeHtml(t('autoupdate.diffNew')) + '</div><pre id="diffRightPre" style="margin:0;white-space:pre-wrap;"></pre></div>'
      + '</div>'
      + '</div>';
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.style.display = 'none'; });
    document.getElementById('autoupdateDiffClose').addEventListener('click', function() { overlay.style.display = 'none'; });
  }
  overlay.style.display = 'flex';
  document.getElementById('autoupdateDiffTitle').textContent = filepath;
  document.getElementById('diffLeftPre').textContent = t('autoupdate.diffLoading');
  document.getElementById('diffRightPre').textContent = '';

  try {
    var resp = await fetch('/v1/admin/autoupdate/diff', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: filepath }),
    });
    var data = await resp.json();
    var leftPre = document.getElementById('diffLeftPre');
    var rightPre = document.getElementById('diffRightPre');
    if (data.success) {
      var lines = (data.diff || '(no changes)').split('\n');
      var leftHtml = [];
      var rightHtml = [];
      for (var i = 0; i < lines.length; i++) {
        var line = lines[i];
        if (line.startsWith('+++') || line.startsWith('---')) {
          // File header lines — show on both sides
          leftHtml.push('<span style="color:var(--muted);">' + escapeHtml(line) + '</span>');
          rightHtml.push('<span style="color:var(--muted);">' + escapeHtml(line) + '</span>');
        } else if (line.startsWith('@@')) {
          // Hunk header — show on both sides
          leftHtml.push('<span style="color:var(--accent);">' + escapeHtml(line) + '</span>');
          rightHtml.push('<span style="color:var(--accent);">' + escapeHtml(line) + '</span>');
        } else if (line.startsWith('-')) {
          // Removed line — left side only
          leftHtml.push('<span style="color:var(--err);background:rgba(217,72,72,0.1);display:block;padding:0 4px;margin:0 -4px;">' + escapeHtml(line) + '</span>');
          rightHtml.push('<span style="display:block;min-height:1.5em;">&nbsp;</span>');
        } else if (line.startsWith('+')) {
          // Added line — right side only
          leftHtml.push('<span style="display:block;min-height:1.5em;">&nbsp;</span>');
          rightHtml.push('<span style="color:var(--ok);background:rgba(31,157,97,0.1);display:block;padding:0 4px;margin:0 -4px;">' + escapeHtml(line) + '</span>');
        } else {
          // Context line — show on both sides
          leftHtml.push(escapeHtml(line));
          rightHtml.push(escapeHtml(line));
        }
      }
      leftPre.innerHTML = leftHtml.join('\n');
      rightPre.innerHTML = rightHtml.join('\n');
      // Sync scroll between the two panels
      var diffLeft = document.getElementById('diffLeft');
      var diffRight = document.getElementById('diffRight');
      var syncing = false;
      diffLeft.onscroll = function() {
        if (syncing) return;
        syncing = true;
        diffRight.scrollTop = diffLeft.scrollTop;
        syncing = false;
      };
      diffRight.onscroll = function() {
        if (syncing) return;
        syncing = true;
        diffLeft.scrollTop = diffRight.scrollTop;
        syncing = false;
      };
    } else {
      leftPre.textContent = 'Error: ' + (data.error || 'unknown');
      rightPre.textContent = '';
    }
  } catch (e) {
    document.getElementById('diffLeftPre').textContent = 'Error: ' + e.message;
    document.getElementById('diffRightPre').textContent = '';
  }
}

async function triggerAutoupdateCheck() {
  try {
    var statusEl = document.getElementById('autoupdateResultStatus');
    var panel = document.getElementById('autoupdateResults');
    if (panel) panel.classList.remove('hidden');
    if (statusEl) { statusEl.textContent = t('autoupdate.checking'); statusEl.style.color = 'var(--muted)'; }
    var resp = await fetch('/v1/admin/autoupdate/check', { method: 'POST' });
    var data = await resp.json();
    if (data.success) {
      _showCheckResults(data.data);
      toast(t('autoupdate.checkComplete', { count: data.data.changed_count || 0 }), 'ok');
    } else {
      _showCheckResults({ status: 'error', message: data.error || t('actions.unknownError') });
      toast(t('autoupdate.checkFailedDetail', { error: data.error || t('actions.unknownError') }), 'error');
    }
  } catch (error) {
    _showCheckResults({ status: 'error', message: String(error) });
    toast(t('autoupdate.checkFailedDetail', { error: String(error) }), 'error');
  }
}

async function applyAutoupdate() {
  try {
    // Collect selected files
    var checkboxes = document.querySelectorAll('.autoupdate-file-check:checked');
    var selectedFiles = [];
    checkboxes.forEach(function(cb) { selectedFiles.push(cb.value); });

    if (selectedFiles.length === 0) {
      toast(t('autoupdate.selectAtLeastOne'), 'warn');
      return;
    }

    var confirmed = await showConfirmDialog(t('autoupdate.applyConfirm', { count: selectedFiles.length }));
    if (!confirmed) return;
    toast(t('autoupdate.applying', { count: selectedFiles.length }), 'info');
    var resp = await fetch('/v1/admin/autoupdate/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files: selectedFiles })
    });
    var data = await resp.json();
    if (data.success) {
      toast(t('autoupdate.applyOk', { count: selectedFiles.length }), 'ok');
      var applyBtn = document.getElementById('autoupdateApplyBtn');
      if (applyBtn) applyBtn.classList.add('hidden');
      // Auto hot-reload config after apply
      try {
        var reloadResp = await fetch('/v1/config/reload', { method: 'POST' });
        var reloadResult = await reloadResp.json();
        if (reloadResult.status === 'ok') {
          toast(t('autoupdate.configReloaded'), 'ok');
        }
      } catch (e) { /* ignore reload errors */ }
      await refreshAll();
    } else {
      toast(t('autoupdate.applyFailed', { error: data.error || t('actions.unknownError') }), 'error');
    }
  } catch (error) {
    toast(t('autoupdate.applyFailed', { error: String(error) }), 'error');
  }
}
