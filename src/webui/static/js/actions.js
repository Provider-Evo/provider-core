function copyText(text, successMessage) {
  navigator.clipboard.writeText(text).then(function() {
    toast(successMessage, 'ok');
  }).catch(function(error) {
    toast('复制失败：' + String(error), 'error');
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
  toast('摘要已导出', 'ok');
}

function connectLogsSocket() {
  if (!window.WebSocket) {
    socketNotice.textContent = '日志 WebSocket: 当前浏览器不支持';
    return;
  }
  if (logsSocket && (logsSocket.readyState === WebSocket.CONNECTING || logsSocket.readyState === WebSocket.OPEN)) {
    return; // 已有活跃连接
  }

  var protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  var url = protocol + '//' + window.location.host + '/v1/webui/ws/logs';
  logsSocket = new WebSocket(url);

  var reconnectAttempts = 0;
  var maxReconnectDelay = 30000; // 30秒最大重连延迟
  var baseReconnectDelay = 1000; // 1秒基础重连延迟

  function scheduleReconnect() {
    if (reconnectAttempts >= 10) {
      socketNotice.textContent = '日志 WebSocket: 重连次数过多，请刷新页面';
      return;
    }
    var delay = Math.min(baseReconnectDelay * Math.pow(2, reconnectAttempts), maxReconnectDelay);
    reconnectAttempts++;
    socketNotice.textContent = '日志 WebSocket: 将在 ' + (delay / 1000).toFixed(1) + ' 秒后重连 (' + reconnectAttempts + '/10)';
    setTimeout(function() {
      connectLogsSocket();
    }, delay);
  }

  logsSocket.onopen = function() {
    reconnectAttempts = 0; // 重置重连计数
    socketNotice.textContent = '日志 WebSocket: 已连接';
    log('日志 WebSocket 已连接，正在加载历史日志...');
  };
  logsSocket.onmessage = function(event) {
    try {
      var payload = JSON.parse(event.data);
      if (payload.type === 'hello') {
        // hello 不显示，历史日志会紧随其后
      }
      if (payload.type === 'history') {
        log('已加载 ' + payload.count + ' 条历史日志。');
      }
      if (payload.type === 'log' && payload.message) {
        var line = '[' + (payload.timestamp || '--:--:--') + '] [' + (payload.level || 'INFO') + '] ' + payload.message;
        logBox.textContent = line + '\n' + logBox.textContent;
      }
      if (payload.type === 'pong') {
        // 心跳响应不显示
      }
    } catch (error) {
      logBox.textContent = '[error] 消息解析失败：' + String(error) + '\n' + logBox.textContent;
    }
  };
  logsSocket.onerror = function() {
    socketNotice.textContent = '日志 WebSocket: 连接异常';
  };
  logsSocket.onclose = function() {
    socketNotice.textContent = '日志 WebSocket: 已关闭';
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
      renderOverview(summaryResult.value);
      renderConfig(summaryResult.value);
      renderModels(summaryResult.value.models || []);
      renderPlatforms(summaryResult.value.platforms || {});
    } else {
      // API failed, show error state
      log('刷新状态失败: ' + (summaryResult.reason ? summaryResult.reason.message : '未知错误'));
      if (document.getElementById('versionValue')) {
        document.getElementById('versionValue').textContent = '加载失败';
      }
      if (document.getElementById('modelsValue')) {
        document.getElementById('modelsValue').textContent = '加载失败';
      }
    }
    if (healthResult.status === 'fulfilled') {
      document.getElementById('healthValue').textContent = healthResult.value && healthResult.value.status ? healthResult.value.status : 'degraded';
    } else {
      if (document.getElementById('healthValue')) {
        document.getElementById('healthValue').textContent = '未知';
      }
    }
    document.getElementById('lastRefresh').textContent = new Date().toLocaleTimeString();
  } catch (error) {
    toast('状态刷新失败：' + String(error), 'error');
    log('状态刷新失败：' + String(error));
  }
}

async function refreshModels() {
  try {
    log('开始刷新模型缓存。');
    const result = await fetchJson('/v1/admin/refresh_models', { method: 'POST' });
    toast('模型刷新完成', 'ok');
    await refreshAll();
  } catch (error) {
    toast('模型刷新失败：' + String(error), 'error');
    log('模型刷新失败：' + String(error));
  }
}

async function saveConfig() {
  try {
    log('正在保存配置...');
    let configData;
    if (configEditArea && !configEditArea.classList.contains('hidden')) {
      configData = JSON.parse(configEditArea.value);
    } else {
      configData = JSON.parse(configJsonBox.textContent || '{}');
    }
    const response = await fetch('/v1/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(configData)
    });
    const result = await response.json();
    if (result.status === 'ok') {
      state.configDirty = false;
      updateConfigSaveStatus();
      toast('配置已保存并重新加载', 'ok');
      log('配置已保存并重新加载。');
      await refreshAll();
    } else {
      toast('保存失败：' + (result.error || '未知错误'), 'error');
      log('配置保存失败：' + JSON.stringify(result));
    }
  } catch (error) {
    toast('保存失败：' + String(error), 'error');
    log('配置保存失败：' + String(error));
  }
}

async function reloadServer() {
  try {
    log('正在请求服务重启...');
    const response = await fetch('/v1/admin/reload', { method: 'POST' });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText.slice(0, 200)}`);
    }
    const result = await response.json();
    if (result.status === 'ok') {
      toast('服务正在重启，页面将自动刷新', 'ok');
      log('服务重启已触发，页面将在3秒后刷新。');
      setTimeout(function() { location.reload(); }, 3000);
    } else {
      toast('重启失败：' + (result.error || '未知错误'), 'error');
      log('服务重启失败：' + JSON.stringify(result));
    }
  } catch (error) {
    toast('重启失败：' + String(error), 'error');
    log('服务重启失败：' + String(error));
  }
}

async function reloadConfigFromFile() {
  try {
    log('正在从文件重新加载配置...');
    const response = await fetch('/v1/config/reload', { method: 'POST' });
    const result = await response.json();
    if (result.status === 'ok') {
      state.configDirty = false;
      updateConfigSaveStatus();
      toast('配置已从文件重新加载', 'ok');
      log('配置已从文件重新加载。');
      await refreshAll();
    } else {
      toast('重载失败：' + (result.error || '未知错误'), 'error');
    }
  } catch (error) {
    toast('重载失败：' + String(error), 'error');
    log('配置重载失败：' + String(error));
  }
}

function onConfigFieldChange(e) {
  var el = e.target;
  var section = el.getAttribute('data-section');
  var key = el.getAttribute('data-key');
  if (!section || !key || !state.summary || !state.summary.config) return;

  var val;
  if (el.type === 'checkbox') {
    val = el.checked;
  } else if (el.type === 'number') {
    val = parseInt(el.value, 10) || 0;
  } else if (el.tagName === 'TEXTAREA') {
    try {
      val = JSON.parse(el.value);
    } catch (err) {
      return; // invalid JSON, skip update
    }
  } else {
    val = el.value;
  }

  if (!state.summary.config[section]) state.summary.config[section] = {};
  state.summary.config[section][key] = val;

  // Update JSON preview
  configJsonBox.textContent = JSON.stringify(state.summary.config, null, 2);
  scheduleConfigSave();
}

function toggleConfigEdit() {
  if (!configEditArea) return;
  const isHidden = configEditArea.classList.contains('hidden');
  if (isHidden) {
    configEditArea.value = configJsonBox.textContent || '';
    configEditArea.classList.remove('hidden');
    document.getElementById('configEditToggle').textContent = '收起编辑';
  } else {
    try {
      const parsed = JSON.parse(configEditArea.value);
      configJsonBox.textContent = JSON.stringify(parsed, null, 2);
    } catch (e) {
      toast('JSON 格式错误，未保存更改', 'error');
    }
    configEditArea.classList.add('hidden');
    document.getElementById('configEditToggle').textContent = '编辑配置';
  }
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
      document.getElementById('autoupdateStatus').textContent = d.enabled ? '已启用' : '未启用';
      // Render mirrors
      _renderMirrors(d.mirrors || []);
      // Show last check if available
      if (d.last_check && d.last_check.status) {
        _showCheckResults(d.last_check);
      }
    }
  } catch (error) {
    toast('加载自动更新设置失败：' + String(error), 'error');
  }
}

function _renderMirrors(mirrors) {
  var list = document.getElementById('autoupdateMirrorsList');
  if (!list) return;
  if (!mirrors.length) {
    list.innerHTML = '<div class="text-[12px] text-muted">No mirrors configured</div>';
    return;
  }
  list.innerHTML = mirrors.map(function(m, i) {
    return '<div class="mirror-item" style="display:flex;align-items:center;gap:6px;margin-bottom:4px;">'
      + '<span style="color:var(--muted);font-size:11px;width:16px;">' + (i+1) + '</span>'
      + '<input type="text" class="config-input mirror-url" value="' + escapeHtml(m) + '" style="flex:1;">'
      + '<button type="button" class="text-[12px] text-err hover:underline mirror-remove" data-index="' + i + '">remove</button>'
      + '</div>';
  }).join('');
  // Bind remove buttons
  list.querySelectorAll('.mirror-remove').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var inputs = list.querySelectorAll('.mirror-url');
      var arr = [];
      inputs.forEach(function(inp, idx) { if (idx !== parseInt(btn.dataset.index)) arr.push(inp.value); });
      _renderMirrors(arr);
    });
  });
}

function _getMirrorsFromUI() {
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
      document.getElementById('autoupdateStatus').textContent = data.data.enabled ? '已启用' : '未启用';
      toast('自动更新设置已保存', 'ok');
    } else {
      toast('保存失败：' + (data.error || 'unknown'), 'error');
    }
  } catch (error) {
    toast('保存失败：' + String(error), 'error');
  }
}

function _showCheckResults(d) {
  var panel = document.getElementById('autoupdateResults');
  var statusEl = document.getElementById('autoupdateResultStatus');
  var metaEl = document.getElementById('autoupdateResultMeta');
  var filesEl = document.getElementById('autoupdateChangedFiles');
  var applyBtn = document.getElementById('autoupdateApplyBtn');
  if (!panel) return;
  panel.classList.remove('hidden');

  if (d.status === 'error') {
    statusEl.textContent = '[error]';
    statusEl.style.color = 'var(--err)';
    metaEl.textContent = d.message || 'Check failed';
    filesEl.innerHTML = '';
    if (applyBtn) applyBtn.classList.add('hidden');
    return;
  }

  if (!d.has_update) {
    statusEl.textContent = '[up to date]';
    statusEl.style.color = 'var(--ok)';
    metaEl.textContent = (d.local_hash || '') + ' = ' + (d.remote_hash || '') + ' (mirror: ' + (d.mirror || '') + ')';
    filesEl.innerHTML = '';
    if (applyBtn) applyBtn.classList.add('hidden');
    return;
  }

  statusEl.textContent = d.changed_count + ' file(s) changed';
  statusEl.style.color = 'var(--warn)';
  metaEl.textContent = (d.local_hash || '?') + ' -> ' + (d.remote_hash || '?') + ' (mirror: ' + (d.mirror || '') + ')';
  filesEl.innerHTML = (d.changed_files || []).map(function(f) {
    return '<div style="padding:1px 0;">' + escapeHtml(f) + '</div>';
  }).join('');
  if (applyBtn) applyBtn.classList.remove('hidden');
}

async function triggerAutoupdateCheck() {
  try {
    var statusEl = document.getElementById('autoupdateResultStatus');
    var panel = document.getElementById('autoupdateResults');
    if (panel) panel.classList.remove('hidden');
    if (statusEl) { statusEl.textContent = 'checking...'; statusEl.style.color = 'var(--muted)'; }
    var resp = await fetch('/v1/admin/autoupdate/check', { method: 'POST' });
    var data = await resp.json();
    if (data.success) {
      _showCheckResults(data.data);
      toast('检查完成：' + (data.data.changed_count || 0) + ' file(s) changed', 'ok');
    } else {
      _showCheckResults({ status: 'error', message: data.error || 'unknown' });
      toast('检查失败：' + (data.error || 'unknown'), 'error');
    }
  } catch (error) {
    _showCheckResults({ status: 'error', message: String(error) });
    toast('检查失败：' + String(error), 'error');
  }
}

async function applyAutoupdate() {
  try {
    var confirmed = await showConfirmDialog('确定要应用更新吗？更新后需要重启服务才能生效。');
    if (!confirmed) return;
    toast('正在应用更新...', 'info');
    var resp = await fetch('/v1/admin/autoupdate/apply', { method: 'POST' });
    var data = await resp.json();
    if (data.success) {
      toast('更新已应用，请重启服务', 'ok');
      var applyBtn = document.getElementById('autoupdateApplyBtn');
      if (applyBtn) applyBtn.classList.add('hidden');
    } else {
      toast('应用失败：' + (data.error || 'unknown'), 'error');
    }
  } catch (error) {
    toast('应用失败：' + String(error), 'error');
  }
}
