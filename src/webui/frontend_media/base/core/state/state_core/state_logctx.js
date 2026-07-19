// ========================= Log Context Menu =========================
// Right-click menu for log entries: copy, filter, and search actions.

var _logContextMenu = null;

function _hideLogContextMenu() {
  if (_logContextMenu) {
    _logContextMenu.remove();
    _logContextMenu = null;
  }
}

function _copyLogText(text) {
  if (!text) return;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function () {
      toast(t('logs.copied'), 'ok');
    }).catch(function () {
      _copyLogTextFallback(text);
    });
    return;
  }
  _copyLogTextFallback(text);
}

function _copyLogTextFallback(text) {
  var ta = document.createElement('textarea');
  ta.value = text;
  ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;';
  document.body.appendChild(ta);
  ta.select();
  try {
    document.execCommand('copy');
    toast(t('logs.copied'), 'ok');
  } catch (e) {
    toast(t('logs.copyFailed'), 'error');
  }
  document.body.removeChild(ta);
}

function _formatLogLine(entry) {
  return _formatLogTimestamp(entry.timestamp) + ' [' + _formatLogLevel(entry.level || 'INFO') + '] [' +
    (entry.module || '') + '] ' + (entry.message || '');
}

function _setLogLevelFilter(level) {
  _logLevelFilter = level;
  localStorage.setItem('provider.logLevelFilter', _logLevelFilter);
  var dropdown = window._dropdowns && window._dropdowns['logLevelSelect'];
  if (dropdown && typeof dropdown.setValue === 'function') {
    dropdown.setValue(level);
  } else {
    var sel = document.getElementById('logLevelSelect');
    if (sel) sel.value = level;
  }
  filterLogs();
}

function _setLogModuleFilter(module) {
  _logModuleFilter = module || 'all';
  var dropdown = window._dropdowns && window._dropdowns['logModuleSelect'];
  if (dropdown && typeof dropdown.setValue === 'function') {
    dropdown.setValue(_logModuleFilter);
  } else {
    var sel = document.getElementById('logModuleSelect');
    if (sel) sel.value = _logModuleFilter;
  }
  filterLogs();
}

function _setLogSearchQuery(query) {
  _logSearchQuery = query || '';
  var input = document.getElementById('logSearchInput');
  if (input) input.value = _logSearchQuery;
  filterLogs();
}

function _appendLogContextMenuItem(menu, def) {
  if (def.separator) {
    var sep = document.createElement('div');
    sep.className = 'logs-context-menu-separator';
    menu.appendChild(sep);
    return;
  }
  var item = document.createElement('div');
  item.className = 'logs-context-menu-item';
  if (def.disabled) item.className += ' disabled';
  item.textContent = def.label;
  if (!def.disabled) {
    (function (action) {
      item.addEventListener('click', function (e) {
        e.stopPropagation();
        _hideLogContextMenu();
        action();
      });
    })(def.action);
  }
  menu.appendChild(item);
}

function _clampLogContextMenuPosition(menu) {
  var rect = menu.getBoundingClientRect();
  if (rect.right > window.innerWidth) {
    menu.style.left = (window.innerWidth - rect.width - 8) + 'px';
  }
  if (rect.bottom > window.innerHeight) {
    menu.style.top = (window.innerHeight - rect.height - 8) + 'px';
  }
}

function _showLogContextMenu(event, entry) {
  _hideLogContextMenu();
  if (!entry) return;

  _logContextMenu = document.createElement('div');
  _logContextMenu.className = 'logs-context-menu';
  _logContextMenu.style.left = event.clientX + 'px';
  _logContextMenu.style.top = event.clientY + 'px';

  var items = [
    { label: t('logs.copyMessage'), action: function () { _copyLogText(entry.message || ''); } },
    { label: t('logs.copyLine'), action: function () { _copyLogText(_formatLogLine(entry)); } },
    { separator: true },
    { label: t('logs.searchThis'), action: function () { _setLogSearchQuery(entry.message || ''); } },
    { label: t('logs.filterByLevel', { level: _formatLogLevel(entry.level || 'INFO') }), action: function () {
      _setLogLevelFilter(entry.level || 'INFO');
    } },
    { label: t('logs.filterByModule', { module: entry.module || t('logs.unknownModule') }), disabled: !entry.module, action: function () {
      _setLogModuleFilter(entry.module);
    } },
    { separator: true },
    { label: t('logs.clear'), action: function () { clearLogs(); } },
    { label: t('logs.export'), action: function () { exportLogs(); } },
  ];

  for (var i = 0; i < items.length; i++) {
    _appendLogContextMenuItem(_logContextMenu, items[i]);
  }

  document.body.appendChild(_logContextMenu);
  _clampLogContextMenuPosition(_logContextMenu);
}

function _resolveLogEntryFromTarget(target) {
  var row = target && target.closest ? target.closest('.log-entry') : null;
  if (!row) return null;
  var idx = parseInt(row.getAttribute('data-log-index'), 10);
  if (isNaN(idx) || idx < 0 || idx >= _logEntries.length) return null;
  return _logEntries[idx];
}

(function _setupLogContextMenu() {
  document.addEventListener('click', function () { _hideLogContextMenu(); });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') _hideLogContextMenu();
  });

  var box = document.getElementById('logBox');
  if (!box) return;

  box.addEventListener('contextmenu', function (e) {
    var entry = _resolveLogEntryFromTarget(e.target);
    if (!entry) return;
    e.preventDefault();
    _showLogContextMenu(e, entry);
  });
})();
