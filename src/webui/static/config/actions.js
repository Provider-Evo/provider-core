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
  };
  logsSocket.onmessage = function(event) {
    try {
      var payload = JSON.parse(event.data);
      if (payload.type === 'hello') {
        // hello 不显示，历史日志会紧随其后
      }
      if (payload.type === 'history') {
        // History count notification — no log needed
      }
      if (payload.type === 'log' && payload.message) {
        var levelColors = {
          'D': '90', 'DEBUG': '90',
          'I': '34', 'INFO': '34',
          'W': '33', 'WARNING': '33',
          'E': '31', 'ERROR': '31',
          'C': '91', 'CRITICAL': '91',
          'S': '32', 'SUCCESS': '32'
        };
        var level = (payload.level || 'I').toUpperCase();
        var colorCode = levelColors[level] || '37';
        var ts = payload.timestamp || '--:--:--';
        var mod = payload.module || '';
        var now = new Date();
        var dateStr = String(now.getMonth() + 1).padStart(2, '0') + '-' + String(now.getDate()).padStart(2, '0');
        var timeStr = String(now.getHours()).padStart(2, '0') + ':' + String(now.getMinutes()).padStart(2, '0') + ':' + String(now.getSeconds()).padStart(2, '0');
        var line = '\x1b[34m' + dateStr + ' ' + ts + '\x1b[0m | \x1b[' + colorCode + 'm[ ' + level + ' ]\x1b[0m | \x1b[36m' + mod + '\x1b[0m | ' + payload.message;
        log(line);
      }
      if (payload.type === 'pong') {
        // 心跳响应不显示
      }
    } catch (error) {
      // Ignore parse errors
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
      if (typeof renderConfig === 'function') renderConfig(summaryResult.value);
      renderModels(summaryResult.value.models || []);
      renderPlatforms(summaryResult.value.platforms || {});
    } else {
      // API failed, show error state
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
  }
}

async function refreshModels() {
  try {
    const result = await fetchJson('/v1/admin/refresh_models', { method: 'POST' });
    toast('模型刷新完成', 'ok');
    await refreshAll();
  } catch (error) {
    toast('模型刷新失败：' + String(error), 'error');
  }
}

async function saveConfig() {
  try {
    let configData;
    if (configEditArea && !configEditArea.classList.contains('hidden')) {
      configData = JSON.parse(configEditArea.value);
    } else if (window._currentConfig) {
      configData = window._currentConfig;
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
      // Prevent renderConfig from re-fetching and overwriting the form for 5 seconds
      if (typeof _lastConfigSaveTime !== 'undefined') _lastConfigSaveTime = Date.now();
      await refreshAll();
    } else {
      toast('保存失败：' + (result.error || '未知错误'), 'error');
    }
  } catch (error) {
    toast('保存失败：' + String(error), 'error');
  }
}

async function reloadServer() {
  try {
    const response = await fetch('/v1/admin/reload', { method: 'POST' });
    if (!response.ok) {
      const errorText = await response.text();
      throw new Error(`HTTP ${response.status}: ${errorText.slice(0, 200)}`);
    }
    const result = await response.json();
    if (result.status === 'ok') {
      toast('服务正在重启，页面将自动刷新', 'ok');
      setTimeout(function() { location.reload(); }, 3000);
    } else {
      toast('重启失败：' + (result.error || '未知错误'), 'error');
    }
  } catch (error) {
    toast('重启失败：' + String(error), 'error');
  }
}

async function reloadConfigFromFile() {
  try {
    const response = await fetch('/v1/config/reload', { method: 'POST' });
    const result = await response.json();
    if (result.status === 'ok') {
      state.configDirty = false;
      updateConfigSaveStatus();
      toast('配置已从文件重新加载', 'ok');
      await refreshAll();
    } else {
      toast('重载失败：' + (result.error || '未知错误'), 'error');
    }
  } catch (error) {
    toast('重载失败：' + String(error), 'error');
  }
}

function onConfigFieldChange(e) {
  // Config field changes are now handled by _onConfigChange in render.js
  // This function is kept for backward compatibility but is a no-op
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
      placeholder: 'No mirrors configured',
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
    metaEl.textContent = d.message || 'Check failed';
    filesEl.innerHTML = '';
    return;
  }

  if (!d.has_update) {
    statusEl.textContent = '[up to date]';
    statusEl.style.color = 'var(--ok)';
    metaEl.textContent = (d.local_hash || '') + ' = ' + (d.remote_hash || '') + ' (mirror: ' + (d.mirror || '') + ')';
    filesEl.innerHTML = '';
    return;
  }

  var files = d.changed_files || [];
  statusEl.textContent = files.length + ' file(s) changed';
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
        + '<span class="text-[12px] font-mono autoupdate-file-link" data-file="' + escapeHtml(f) + '" style="color:var(--accent);cursor:pointer;text-decoration:underline;" title="点击查看变更">' + escapeHtml(f) + '</span>'
        + '</label>';
    }).join('');
    filesEl.innerHTML = html || '<div class="text-muted" style="padding:8px;">No matching files</div>';
    _bindFileEvents();
    _updateSelectedCount();
  }

  function _updateSelectedCount() {
    var checked = filesEl.querySelectorAll('.autoupdate-file-check:checked').length;
    var total = filesEl.querySelectorAll('.autoupdate-file-check').length;
    if (selectedCount) selectedCount.textContent = '已选 ' + checked + '/' + total + ' 个文件';
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
      + '<div id="diffLeft" style="overflow:auto;font-size:12px;line-height:1.5;padding:12px;background:var(--panel-alt);border:1px solid var(--border);border-radius:8px;white-space:pre-wrap;word-break:break-all;font-family:monospace;"><div style="font-size:11px;color:var(--muted);margin-bottom:8px;font-weight:600;">OLD (local)</div><pre id="diffLeftPre" style="margin:0;white-space:pre-wrap;"></pre></div>'
      + '<div id="diffRight" style="overflow:auto;font-size:12px;line-height:1.5;padding:12px;background:var(--panel-alt);border:1px solid var(--border);border-radius:8px;white-space:pre-wrap;word-break:break-all;font-family:monospace;"><div style="font-size:11px;color:var(--muted);margin-bottom:8px;font-weight:600;">NEW (remote)</div><pre id="diffRightPre" style="margin:0;white-space:pre-wrap;"></pre></div>'
      + '</div>'
      + '</div>';
    document.body.appendChild(overlay);
    overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.style.display = 'none'; });
    document.getElementById('autoupdateDiffClose').addEventListener('click', function() { overlay.style.display = 'none'; });
  }
  overlay.style.display = 'flex';
  document.getElementById('autoupdateDiffTitle').textContent = filepath;
  document.getElementById('diffLeftPre').textContent = 'Loading diff...';
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
    // Collect selected files
    var checkboxes = document.querySelectorAll('.autoupdate-file-check:checked');
    var selectedFiles = [];
    checkboxes.forEach(function(cb) { selectedFiles.push(cb.value); });

    if (selectedFiles.length === 0) {
      toast('请至少选择一个要更新的文件', 'warn');
      return;
    }

    var confirmed = await showConfirmDialog('确定要应用 ' + selectedFiles.length + ' 个文件的更新吗？更新后需要重启服务才能生效。');
    if (!confirmed) return;
    toast('正在应用 ' + selectedFiles.length + ' 个文件的更新...', 'info');
    var resp = await fetch('/v1/admin/autoupdate/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files: selectedFiles })
    });
    var data = await resp.json();
    if (data.success) {
      toast('更新已应用 ' + selectedFiles.length + ' 个文件，正在热重载配置...', 'ok');
      var applyBtn = document.getElementById('autoupdateApplyBtn');
      if (applyBtn) applyBtn.classList.add('hidden');
      // Auto hot-reload config after apply
      try {
        var reloadResp = await fetch('/v1/config/reload', { method: 'POST' });
        var reloadResult = await reloadResp.json();
        if (reloadResult.status === 'ok') {
          toast('配置已热重载', 'ok');
        }
      } catch (e) { /* ignore reload errors */ }
      await refreshAll();
    } else {
      toast('应用失败：' + (data.error || 'unknown'), 'error');
    }
  } catch (error) {
    toast('应用失败：' + String(error), 'error');
  }
}
