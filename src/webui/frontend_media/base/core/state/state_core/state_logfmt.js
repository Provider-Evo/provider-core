// ========================= Log Rendering =========================
// 拆分自 state.js。依赖 state_core.js（DOM 引用）与 state_loghelpers.js（_logEntries 等）已加载。

function _invalidateLogFilterCache() {
  _logFilteredCache = null;
}

function _getFilteredLogs() {
  if (_logFilteredCache !== null) return _logFilteredCache;
  _logFilteredCache = [];
  for (var i = 0; i < _logEntries.length; i++) {
    if (_logEntryMatchesFilter(_logEntries[i])) {
      _logFilteredCache.push(_logEntries[i]);
    }
  }
  return _logFilteredCache;
}

function _renderLogs() {
  var box = document.getElementById('logBox');
  if (!box) return;
  var filtered = _getFilteredLogs();
  if (!filtered.length) {
    box.innerHTML = '<div class="log-empty">' + t('logs.empty') + '</div>';
    return;
  }
  var parts = ['<div class="log-list">'];
  for (var i = 0; i < filtered.length; i++) {
    parts.push(_createLogEntryHTML(filtered[i]));
  }
  parts.push('</div>');
  box.innerHTML = parts.join('');
}

function _syncLogLayoutVars() {
  var viewer = document.getElementById('logBox');
  if (!viewer) return;
  var cfg = _getLogFontConfig();
  viewer.style.setProperty('--log-time-w', cfg.timeW + 'px');
  viewer.style.setProperty('--log-level-w', cfg.levelW + 'px');
  viewer.style.setProperty('--log-module-w', cfg.moduleW + 'px');
  viewer.style.setProperty('--log-col-gap', cfg.colGap + 'px');
  viewer.style.setProperty('--log-line-pad', cfg.linePad + 'px');
}

function _scheduleLogRender() {
  if (_logRenderTimer) return;
  _logRenderTimer = requestAnimationFrame(function() {
    _logRenderTimer = null;
    _renderLogs();
    _logAutoScrollToBottom();
    _updateLogCount();
  });
}

function _updateUniqueModules() {
  var seen = {};
  for (var i = 0; i < _logEntries.length; i++) {
    var mod = _logEntries[i].module;
    if (mod && !seen[mod]) {
      seen[mod] = true;
      _uniqueModules.push(mod);
    }
  }
  _uniqueModules.sort();
  _rebuildModuleSelect();
}

function _rebuildModuleSelect() {
  var sel = document.getElementById('logModuleSelect');
  if (!sel) return;
  var prev = sel.value;

  // Build options array
  var opts = [{ value: 'all', text: t('logs.allModules') }];
  for (var i = 0; i < _uniqueModules.length; i++) {
    opts.push({ value: _uniqueModules[i], text: _uniqueModules[i] });
  }

  // Update CustomDropdown if available, otherwise fallback to native select
  var dropdown = window._dropdowns && window._dropdowns['logModuleSelect'];
  if (dropdown && typeof dropdown.setOptions === 'function') {
    dropdown.setOptions(opts, false);
    dropdown.setValue(prev || 'all');
  } else {
    // Fallback to native select manipulation
    sel.innerHTML = '<option value="all">' + t('logs.allModules') + '</option>';
    for (var i = 0; i < _uniqueModules.length; i++) {
      var opt = document.createElement('option');
      opt.value = _uniqueModules[i];
      opt.textContent = _uniqueModules[i];
      sel.appendChild(opt);
    }
    sel.value = prev || 'all';
  }
}

function _updateLogCount() {
  var el = document.getElementById('logCount');
  if (!el) return;
  var filtered = _getFilteredLogs();
  el.textContent = t('logs.count', { filtered: filtered.length, total: _logEntries.length });
}

function _applyLogFontSize() {
  var viewer = document.getElementById('logBox');
  if (!viewer) return;
  viewer.classList.remove('log-font-small', 'log-font-medium', 'log-font-large');
  viewer.classList.add('log-font-' + _logFontSize);
  _syncLogLayoutVars();
  _renderLogs();
}

function _toggleLogFilters() {
  _logFilterExpanded = !_logFilterExpanded;
  var panel = document.getElementById('logAdvancedFilters');
  var icon = document.getElementById('logFilterToggleIcon');
  var btn = document.getElementById('logFilterToggleBtn');
  if (panel) panel.style.display = _logFilterExpanded ? '' : 'none';
  if (icon) icon.innerHTML = _logFilterExpanded ? '&#9650;' : '&#9660;';
  if (btn) btn.classList.toggle('active', _logFilterExpanded);
  localStorage.setItem('provider.logFilterExpanded', String(_logFilterExpanded));
}

function _updateLogClearDateBtn() {
  var btn = document.getElementById('logClearDateBtn');
  if (btn) btn.style.display = (_logDateFrom || _logDateTo) ? '' : 'none';
}

// Legacy log() for backwards compatibility
function log(message) {
  addLogEntry({
    id: '',
    timestamp: new Date().toISOString(),
    level: 'INFO',
    module: '',
    message: message,
  });
}

// ========================= Log Entry =========================

function addLogEntry(entry) {
  // 去重
  if (entry.id && _logSeenIds[entry.id]) return;
  if (entry.id) {
    _logSeenIds[entry.id] = true;
    // 裁剪去重缓存
    var keys = Object.keys(_logSeenIds);
    if (keys.length > _logMaxEntries + 500) {
      for (var k = 0; k < 500; k++) delete _logSeenIds[keys[k]];
    }
  }

  _logEntries.push(entry);
  while (_logEntries.length > _logMaxEntries) {
    var removed = _logEntries.shift();
    if (removed.id) delete _logSeenIds[removed.id];
  }

  // 更新模块列表
  if (entry.module && _uniqueModules.indexOf(entry.module) === -1) {
    _uniqueModules.push(entry.module);
    _uniqueModules.sort();
    _rebuildModuleSelect();
  }

  _invalidateLogFilterCache();
  _scheduleLogRender();
}

// ========================= Log Filtering =========================

function _logAutoScrollToBottom() {
  if (!_logAutoScroll) return;
  var box = document.getElementById('logBox');
  if (box) {
    requestAnimationFrame(function() {
      box.scrollTop = box.scrollHeight;
    });
  }
}

function filterLogs() {
  _invalidateLogFilterCache();
  _renderLogs();
  _logAutoScrollToBottom();
  _updateLogCount();
}

function clearLogs() {
  _logEntries = [];
  _logSeenIds = {};
  _uniqueModules = [];
  _logFilteredCache = null;
  if (_logRenderTimer) {
    cancelAnimationFrame(_logRenderTimer);
    _logRenderTimer = null;
  }
  var box = document.getElementById('logBox');
  if (box) box.innerHTML = '';
  _rebuildModuleSelect();
  _updateLogCount();
  toast(t('logs.cleared'), 'ok');
}

function exportLogs() {
  var lines = [];
  for (var i = 0; i < _logEntries.length; i++) {
    var e = _logEntries[i];
    lines.push(_formatLogTimestamp(e.timestamp) + ' [' + (e.level || '') + '] [' + (e.module || '') + '] ' + (e.message || ''));
  }
  var blob = new Blob([lines.join('\n')], { type: 'text/plain;charset=utf-8' });
  var url = URL.createObjectURL(blob);
  var a = document.createElement('a');
  a.href = url;
  var now = new Date();
  a.download = 'provider-logs-' + now.getFullYear() + '-' +
    String(now.getMonth() + 1).padStart(2, '0') + '-' +
    String(now.getDate()).padStart(2, '0') + '_' +
    String(now.getHours()).padStart(2, '0') +
    String(now.getMinutes()).padStart(2, '0') + '.txt';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  toast(t('logs.exported'), 'ok');
}

function toggleAutoScroll() {
  _logAutoScroll = !_logAutoScroll;
  _updateAutoScrollBtn();
  if (_logAutoScroll) _logAutoScrollToBottom();
}

function _updateAutoScrollBtn() {
  var btn = document.getElementById('logAutoScrollBtn');
  var icon = document.getElementById('logAutoScrollIcon');
  if (btn) btn.classList.toggle('active', _logAutoScroll);
  if (icon) icon.innerHTML = _logAutoScroll ? '&#9654;' : '&#9646;&#9646;';
  localStorage.setItem('provider.logAutoScroll', String(_logAutoScroll));
}

function toggleLogRegex() {
  _logSearchRegex = !_logSearchRegex;
  _updateRegexBtn();
  _invalidateLogFilterCache();
  _renderLogs();
}

function _updateRegexBtn() {
  var btn = document.getElementById('logRegexBtn');
  if (btn) {
    btn.classList.toggle('active', _logSearchRegex);
    btn.title = _logSearchRegex ? t('logs.regexOn') : t('logs.regexOff');
  }
  localStorage.setItem('provider.logSearchRegex', String(_logSearchRegex));
}

// ========================= Log Auto-Scroll Detection =========================

(function _setupLogScrollDetection() {
  var box = document.getElementById('logBox');
  if (!box) return;
  box.addEventListener('scroll', function() {
    var distFromBottom = box.scrollHeight - box.scrollTop - box.clientHeight;
    if (distFromBottom > 100 && _logAutoScroll) {
      _logAutoScroll = false;
      _updateAutoScrollBtn();
    }
    if (distFromBottom < 30 && !_logAutoScroll) {
      _logAutoScroll = true;
      _updateAutoScrollBtn();
    }
  });
})();

_applyLogFontSize();
