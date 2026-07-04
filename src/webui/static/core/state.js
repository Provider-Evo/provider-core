const defaultSettings = {
  theme: 'auto',
  refreshInterval: 0,
  timeoutMs: 30000,
  compact: '0'
};
const initialTab = localStorage.getItem('provider.webui.activeTab') || document.body.dataset.initialTab || 'overview';
const state = {
  timer: null,
  models: [],
  summary: null,
  settings: loadSettings(),
  activeTab: initialTab,
  configDirty: false,
  configSaveTimer: null,
  configSaveDebounceMs: 1000,
};

const logBox = document.getElementById('logBox');
const platformGrid = document.getElementById('platformGrid');
const modelGrid = document.getElementById('modelGrid');
const configGrid = document.getElementById('configGrid');
const configJsonBox = document.getElementById('configJsonBox');
const configEditArea = document.getElementById('configEditArea');
const configSaveStatus = document.getElementById('configSaveStatus');
const overviewGrid = document.getElementById('overviewGrid');
const overviewNotice = document.getElementById('overviewNotice');
const portablePanel = document.getElementById('portablePanel');
const themeState = document.getElementById('themeState');
const refreshState = document.getElementById('refreshState');
const toastWrap = document.getElementById('toastWrap');
const socketNotice = document.getElementById('socketNotice');
let logsSocket = null;
let _logEntries = [];
const _logMaxEntries = 5000;
let _logAutoScroll = localStorage.getItem('provider.logAutoScroll') !== 'false';
let _logLevelFilter = localStorage.getItem('provider.logLevelFilter') || 'INFO';
let _logSearchQuery = '';
let _logModuleFilter = 'all';
let _logFontSize = localStorage.getItem('provider.logFontSize') || 'small';
let _logDateFrom = localStorage.getItem('provider.logDateFrom') || '';
let _logDateTo = localStorage.getItem('provider.logDateTo') || '';
let _logFilterExpanded = localStorage.getItem('provider.logFilterExpanded') === 'true';
let _uniqueModules = [];
let _logSeenIds = {};  // 去重

// Virtual scrolling state
let _logFilteredCache = null;  // cached filtered entries (invalidated on filter change)
const _VS_ROW_HEIGHT = 26;
const _VS_BUFFER = 50;
let _vsRenderedRange = { start: -1, end: -1 };

const _LOG_LEVEL_PRIORITY = { DEBUG: 10, INFO: 20, WARNING: 30, ERROR: 40, CRITICAL: 50, SUCCESS: 25 };

// ========================= Log Helpers =========================

function _escapeHtml(text) {
  var d = document.createElement('div');
  d.textContent = String(text);
  return d.innerHTML;
}

function _formatLogTimestamp(ts) {
  if (!ts) return '--:--:--';
  var match = ts.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}:\d{2}:\d{2})/);
  if (match) return match[2] + '-' + match[3] + ' ' + match[4];
  return ts;
}

function _formatLogLevel(level) {
  if (!level) return 'INFO';
  if (level === 'WARNING') return 'WARN';
  if (level === 'CRITICAL') return 'CRIT';
  return level;
}

function _logEntryMatchesFilter(entry) {
  if (_logLevelFilter !== 'all') {
    var entryPri = _LOG_LEVEL_PRIORITY[entry.level] || 0;
    var filterPri = _LOG_LEVEL_PRIORITY[_logLevelFilter] || 0;
    if (entryPri < filterPri) return false;
  }
  if (_logModuleFilter !== 'all' && entry.module !== _logModuleFilter) return false;
  if (_logSearchQuery) {
    var q = _logSearchQuery.toLowerCase();
    var msg = (entry.message || '').toLowerCase();
    var mod = (entry.module || '').toLowerCase();
    if (msg.indexOf(q) === -1 && mod.indexOf(q) === -1) return false;
  }
  // Date range filter
  if (_logDateFrom || _logDateTo) {
    var ts = entry.timestamp || '';
    if (ts) {
      var entryDate = ts.substring(0, 10); // YYYY-MM-DD
      if (_logDateFrom && entryDate < _logDateFrom) return false;
      if (_logDateTo && entryDate > _logDateTo) return false;
    }
  }
  return true;
}

// ========================= Virtual Scrolling =========================

function _invalidateLogFilterCache() {
  _logFilteredCache = null;
  _vsRenderedRange = { start: -1, end: -1 };
}

function _getFilteredLogs() {
  if (_logFilteredCache !== null) return _logFilteredCache;
  _logFilteredCache = [];
  for (var i = _logEntries.length - 1; i >= 0; i--) {
    if (_logEntryMatchesFilter(_logEntries[i])) {
      _logFilteredCache.push(_logEntries[i]);
    }
  }
  return _logFilteredCache;
}

function _renderVisibleLogs() {
  var box = document.getElementById('logBox');
  if (!box) return;
  var filtered = _getFilteredLogs();
  var totalHeight = filtered.length * _VS_ROW_HEIGHT;
  var scrollTop = box.scrollTop;
  var viewportH = box.clientHeight;

  // Ensure spacer exists for scroll height
  var spacer = box.querySelector('.log-vs-spacer');
  if (!spacer) {
    spacer = document.createElement('div');
    spacer.className = 'log-vs-spacer';
    spacer.style.cssText = 'width:1px;pointer-events:none;';
    box.appendChild(spacer);
  }
  spacer.style.height = totalHeight + 'px';

  // Calculate visible range
  var startIdx = Math.max(0, Math.floor(scrollTop / _VS_ROW_HEIGHT) - _VS_BUFFER);
  var endIdx = Math.min(filtered.length, Math.ceil((scrollTop + viewportH) / _VS_ROW_HEIGHT) + _VS_BUFFER);

  // Skip if range unchanged
  if (startIdx === _vsRenderedRange.start && endIdx === _vsRenderedRange.end) return;
  _vsRenderedRange = { start: startIdx, end: endIdx };

  // Remove old log entries (keep spacer)
  var children = box.children;
  for (var i = children.length - 1; i >= 0; i--) {
    if (!children[i].classList.contains('log-vs-spacer')) {
      box.removeChild(children[i]);
    }
  }

  // Insert new entries before spacer
  for (var j = startIdx; j < endIdx; j++) {
    var dom = _createLogEntryDOM(filtered[j]);
    dom.style.position = 'absolute';
    dom.style.top = (j * _VS_ROW_HEIGHT) + 'px';
    dom.style.left = '0';
    dom.style.right = '0';
    box.insertBefore(dom, spacer);
  }
}

function _setupLogVirtualScroll() {
  var box = document.getElementById('logBox');
  if (!box || box._vsSetup) return;
  box._vsSetup = true;
  box.style.position = 'relative';
  box.addEventListener('scroll', function() {
    requestAnimationFrame(_renderVisibleLogs);
  });
}

function _createLogEntryDOM(entry) {
  var div = document.createElement('div');
  div.className = 'log-entry';
  var levelText = _formatLogLevel(entry.level || 'INFO');
  var moduleStyle = entry.moduleColor ? ' style="color:' + _escapeHtml(entry.moduleColor) + '"' : '';
  div.innerHTML =
    '<span class="log-time">' + _escapeHtml(_formatLogTimestamp(entry.timestamp)) + '</span>' +
    '<span class="log-level log-level-' + _escapeHtml(entry.level || 'INFO') + '">' + levelText + '</span>' +
    '<span class="log-module"' + moduleStyle + '>' + _escapeHtml(entry.module || '') + '</span>' +
    '<span class="log-msg">' + _escapeHtml(entry.message || '') + '</span>';
  return div;
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
  sel.innerHTML = '<option value="all">全部模块</option>';
  for (var i = 0; i < _uniqueModules.length; i++) {
    var opt = document.createElement('option');
    opt.value = _uniqueModules[i];
    opt.textContent = _uniqueModules[i];
    sel.appendChild(opt);
  }
  sel.value = prev || 'all';
}

function _updateLogCount() {
  var el = document.getElementById('logCount');
  if (!el) return;
  var total = _logEntries.length;
  var visible = logBox ? logBox.children.length : 0;
  el.textContent = visible + ' / ' + total + ' 条';
}

function _applyLogFontSize() {
  var viewer = document.getElementById('logBox');
  if (!viewer) return;
  viewer.classList.remove('log-font-small', 'log-font-medium', 'log-font-large');
  viewer.classList.add('log-font-' + _logFontSize);
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

  _logEntries.unshift(entry);
  while (_logEntries.length > _logMaxEntries) {
    var removed = _logEntries.pop();
    if (removed.id) delete _logSeenIds[removed.id];
  }

  // 更新模块列表
  if (entry.module && _uniqueModules.indexOf(entry.module) === -1) {
    _uniqueModules.push(entry.module);
    _uniqueModules.sort();
    _rebuildModuleSelect();
  }

  // Invalidate filter cache and re-render visible logs
  _invalidateLogFilterCache();
  if (_logEntryMatchesFilter(entry)) {
    _renderVisibleLogs();
    _logAutoScrollToBottom();
  }
  _updateLogCount();
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
  _setupLogVirtualScroll();
  _renderVisibleLogs();
  _logAutoScrollToBottom();
  _updateLogCount();
}

function clearLogs() {
  _logEntries = [];
  _logSeenIds = {};
  _uniqueModules = [];
  _logFilteredCache = null;
  _vsRenderedRange = { start: -1, end: -1 };
  var box = document.getElementById('logBox');
  if (box) box.innerHTML = '';
  _rebuildModuleSelect();
  _updateLogCount();
  toast('日志已清空', 'ok');
}

function exportLogs() {
  var lines = [];
  for (var i = _logEntries.length - 1; i >= 0; i--) {
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
  toast('日志已导出', 'ok');
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
  _renderVisibleLogs();
}

function _updateRegexBtn() {
  var btn = document.getElementById('logRegexBtn');
  if (btn) {
    btn.classList.toggle('active', _logSearchRegex);
    btn.title = _logSearchRegex ? '正则表达式搜索已开启' : '正则表达式搜索已关闭';
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

function toast(message, type) {
  const node = document.createElement('div');
  node.className = 'min-w-[220px] max-w-[340px] rounded-xl border border-border bg-panel shadow-panel px-3 py-2.5 text-[13px] leading-relaxed toast-enter';
  node.textContent = '[' + (type || 'info') + '] ' + message;
  toastWrap.appendChild(node);
  // Animate toast entrance if MotionKit is available
  if (typeof animateToastIn === 'function') {
    animateToastIn(node);
  }
  setTimeout(function() {
    // Animate toast exit
    if (typeof MotionKit !== 'undefined') {
      MotionKit.opacityTo(node, 0, 5);
      setTimeout(function() { node.remove(); }, 200);
    } else {
      node.remove();
    }
  }, 3200);
}

function showConfirmDialog(message, options) {
  options = options || {};
  var title = options.title || '确认操作';
  var confirmText = options.confirmText || '确定';
  var cancelText = options.cancelText || '取消';

  return new Promise(function(resolve) {
    var overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    overlay.innerHTML =
      '<div class="confirm-dialog">' +
      '<div class="confirm-dialog-title">' + title + '</div>' +
      '<div class="confirm-dialog-message">' + message + '</div>' +
      '<div class="confirm-dialog-actions">' +
      '<button class="confirm-dialog-btn confirm-dialog-cancel" type="button">' + cancelText + '</button>' +
      '<button class="confirm-dialog-btn confirm-dialog-ok" type="button">' + confirmText + '</button>' +
      '</div></div>';

    document.body.appendChild(overlay);
    requestAnimationFrame(function() { overlay.classList.add('is-visible'); });

    function close(result) {
      overlay.classList.remove('is-visible');
      setTimeout(function() { overlay.remove(); resolve(result); }, 180);
    }

    overlay.querySelector('.confirm-dialog-ok').addEventListener('click', function() { close(true); });
    overlay.querySelector('.confirm-dialog-cancel').addEventListener('click', function() { close(false); });
    overlay.addEventListener('click', function(e) { if (e.target === overlay) close(false); });
  });
}

function showInputDialog(message, options) {
  options = options || {};
  var title = options.title || '输入';
  var defaultValue = options.defaultValue || '';
  var confirmText = options.confirmText || '确定';
  var cancelText = options.cancelText || '取消';
  var placeholder = options.placeholder || '';

  return new Promise(function(resolve) {
    var overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    overlay.innerHTML =
      '<div class="confirm-dialog">' +
      '<div class="confirm-dialog-title">' + title + '</div>' +
      '<div class="confirm-dialog-message">' + message + '</div>' +
      '<input type="text" class="input-dialog-input" value="' + _escapeAttr(defaultValue) + '" placeholder="' + _escapeAttr(placeholder) + '">' +
      '<div class="confirm-dialog-actions">' +
      '<button class="confirm-dialog-btn confirm-dialog-cancel" type="button">' + cancelText + '</button>' +
      '<button class="confirm-dialog-btn confirm-dialog-ok" type="button">' + confirmText + '</button>' +
      '</div></div>';

    document.body.appendChild(overlay);
    requestAnimationFrame(function() { overlay.classList.add('is-visible'); });

    var input = overlay.querySelector('.input-dialog-input');
    input.focus();
    input.select();

    function close(result) {
      overlay.classList.remove('is-visible');
      setTimeout(function() { overlay.remove(); resolve(result); }, 180);
    }

    function confirm() {
      var value = input.value.trim();
      close(value || null);
    }

    overlay.querySelector('.confirm-dialog-ok').addEventListener('click', confirm);
    overlay.querySelector('.confirm-dialog-cancel').addEventListener('click', function() { close(null); });
    overlay.addEventListener('click', function(e) { if (e.target === overlay) close(null); });
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); confirm(); }
      if (e.key === 'Escape') close(null);
    });
  });
}

function _escapeAttr(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}

function loadSettings() {
  try {
    return Object.assign({}, defaultSettings, JSON.parse(localStorage.getItem('provider.webui.settings') || '{}'));
  } catch (error) {
    return Object.assign({}, defaultSettings);
  }
}

function saveSettings() {
  localStorage.setItem('provider.webui.settings', JSON.stringify(state.settings));
  applyTheme();
  applyCompact();
  scheduleRefresh();
  persistWebUISettings();
}

async function persistWebUISettings() {
  try {
    var existing = await persistLoad('config.toml') || {};
    existing.theme = state.settings.theme;
    existing.refreshInterval = state.settings.refreshInterval;
    existing.timeoutMs = state.settings.timeoutMs;
    existing.compact = state.settings.compact;
    persistSave('config.toml', existing);
  } catch (e) { /* ignore */ }
}

async function loadWebUISettings() {
  try {
    var saved = await persistLoad('config.toml');
    if (!saved) return false;
    var changed = false;
    if (saved.theme) { state.settings.theme = saved.theme; changed = true; }
    if (typeof saved.refreshInterval === 'number') { state.settings.refreshInterval = saved.refreshInterval; changed = true; }
    if (typeof saved.timeoutMs === 'number') { state.settings.timeoutMs = saved.timeoutMs; changed = true; }
    if (saved.compact) { state.settings.compact = saved.compact; changed = true; }
    return changed;
  } catch (e) { return false; }
}

async function initSettingsFromServer() {
  var loaded = await loadWebUISettings();
  if (loaded) {
    applyTheme();
    applyCompact();
    scheduleRefresh();
    var themeSelect = document.getElementById('themeSelect');
    var themeDd = window._dropdowns && window._dropdowns['themeSelect'];
    if (themeSelect) themeSelect.value = state.settings.theme;
    if (themeDd) themeDd.setValue(state.settings.theme);
    var compactSelect = document.getElementById('compactSelect');
    var compactDd = window._dropdowns && window._dropdowns['compactSelect'];
    if (compactSelect) compactSelect.value = state.settings.compact;
    if (compactDd) compactDd.setValue(state.settings.compact);
    var refreshInput = document.getElementById('refreshIntervalInput');
    if (refreshInput) refreshInput.value = String(state.settings.refreshInterval);
    var timeoutInput = document.getElementById('timeoutInput');
    if (timeoutInput) timeoutInput.value = String(state.settings.timeoutMs);
  }
}

function loadVoiceSettings() {
  try { return JSON.parse(localStorage.getItem('provider.webui.voice') || '{}'); } catch(e) { return {}; }
}

function saveVoiceSettings(vs) {
  localStorage.setItem('provider.webui.voice', JSON.stringify(vs));
  // Update InputBox if initialized
  if (window._chatInputBox) {
    window._chatInputBox._opts.voice = {
      sttModel: vs.sttModel || '',
      ttsModel: vs.ttsModel || '',
      ttsPrompt: vs.ttsPrompt || '',
    };
  }
}

function applyVoiceSettings() {
  var vs = loadVoiceSettings();
  var stt = document.getElementById('voiceSttModel');
  var tts = document.getElementById('voiceTtsModel');
  var prompt = document.getElementById('voiceTtsPrompt');
  if (stt) {
    stt.value = vs.sttModel || '';
    var sttDd = window._dropdowns && window._dropdowns['voiceSttModel'];
    if (sttDd && vs.sttModel) sttDd.setValue(vs.sttModel);
  }
  if (tts) {
    tts.value = vs.ttsModel || '';
    var ttsDd = window._dropdowns && window._dropdowns['voiceTtsModel'];
    if (ttsDd && vs.ttsModel) ttsDd.setValue(vs.ttsModel);
  }
  if (prompt) prompt.value = vs.ttsPrompt || '';
}

function applyTheme() {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = state.settings.theme === 'auto' ? (prefersDark ? 'dark' : 'light') : state.settings.theme;
  document.documentElement.setAttribute('data-theme', theme);
  themeState.textContent = 'theme: ' + state.settings.theme;
  document.getElementById('themeSelect').value = state.settings.theme;
  updateThemeIcon();
  // Notify terminal module to refresh theme when in 'theme' mode
  if (typeof TerminalManager !== 'undefined' && TerminalManager.refreshTheme) {
    TerminalManager.refreshTheme();
  }
}

function updateThemeIcon() {
  const theme = state.settings.theme;
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const effective = theme === 'auto' ? (prefersDark ? 'dark' : 'light') : theme;
  const fabIcon = document.getElementById('fabThemeIcon');
  if (fabIcon) {
    fabIcon.innerHTML = effective === 'dark' ? '&#9788;' : '&#9790;';
  }
}

function applyCompact() {
  document.body.dataset.compact = state.settings.compact;
  document.getElementById('compactSelect').value = state.settings.compact;
}

function scheduleRefresh() {
  if (state.timer) {
    clearInterval(state.timer);
  }
  const interval = Number(state.settings.refreshInterval || 0);
  if (interval > 0) {
    state.timer = setInterval(refreshAll, interval * 1000);
    refreshState.textContent = 'refresh: ' + interval + 's';
  } else {
    refreshState.textContent = 'refresh: manual';
  }
}

function updateConfigSaveStatus() {
  if (configSaveStatus) {
    if (state.configDirty) {
      configSaveStatus.textContent = '未保存';
      configSaveStatus.className = 'status-dirty flex items-center';
    } else {
      configSaveStatus.textContent = '已保存';
      configSaveStatus.className = 'status-saved flex items-center';
    }
  }
}

function scheduleConfigSave() {
  if (state.configSaveTimer) clearTimeout(state.configSaveTimer);
  state.configDirty = true;
  updateConfigSaveStatus();
  state.configSaveTimer = setTimeout(function() {
    saveConfig();
  }, state.configSaveDebounceMs);
}

var _initializedTabs = new Set();

async function switchTab(nextTab) {
  state.activeTab = nextTab;
  localStorage.setItem('provider.webui.activeTab', nextTab);
  document.querySelectorAll('.tab-button[data-tab]').forEach(function(node) {
    node.classList.toggle('active', node.dataset.tab === nextTab);
    node.setAttribute('aria-selected', node.dataset.tab === nextTab ? 'true' : 'false');
  });
  document.querySelectorAll('.tab-panel').forEach(function(node) {
    var isActive = node.id === 'tab-' + nextTab;
    node.classList.toggle('active', isActive);
    node.classList.toggle('hidden', !isActive);
  });

  // Lazy-load tab resources if needed (non-blocking for UI — panel is already visible)
  if (typeof LazyLoader !== 'undefined' && !LazyLoader.isTabLoaded(nextTab)) {
    var panel = document.getElementById('tab-' + nextTab);
    var loaderEl = null;
    if (panel) {
      loaderEl = document.createElement('div');
      loaderEl.className = 'tab-loading-indicator';
      loaderEl.textContent = '加载中...';
      panel.appendChild(loaderEl);
    }
    try {
      await LazyLoader.loadTabResources(nextTab);
    } finally {
      if (loaderEl) loaderEl.remove();
    }
  }

  _initTab(nextTab);
}

function _initTab(tabName) {
  if (_initializedTabs.has(tabName)) return;
  _initializedTabs.add(tabName);

  switch (tabName) {
    case 'chat':
      typeof _initChatTab === 'function' && _initChatTab();
      break;
    case 'stats':
      typeof _initStatsTab === 'function' && _initStatsTab();
      break;
    case 'autoupdate':
      typeof _initAutoupdateTab === 'function' && _initAutoupdateTab();
      break;
    case 'config':
      typeof _initConfigTab === 'function' && _initConfigTab();
      break;
    case 'terminal':
      typeof _initTerminalTab === 'function' && _initTerminalTab();
      break;
    // files — no special init needed (uses Router.register activate)
    default:
      break;
  }
}

async function fetchJson(url, options) {
  const controller = new AbortController();
  const timeout = Number(state.settings.timeoutMs || defaultSettings.timeoutMs);
  const timer = setTimeout(function() { controller.abort(); }, timeout);
  try {
    const response = await fetch(url, Object.assign({ signal: controller.signal }, options || {}));
    if (!response.ok) {
      throw new Error(response.status + ' ' + response.statusText);
    }
    return await response.json();
  } finally {
    clearTimeout(timer);
  }
}

// ========================= Candidate ID Mapping =========================
/**
 * 统一的候选项 ID 映射表。
 * 将后端返回的原始模型 ID 映射为简短、易读的显示 ID。
 */
const candidateIdMap = {};
let candidateIdCounter = 0;

/**
 * 获取或创建候选项的映射 ID。
 * @param {string} originalId - 原始模型 ID
 * @returns {string} 映射后的简短 ID
 */
function mapCandidateId(originalId) {
  if (!originalId) return 'unknown';
  if (candidateIdMap[originalId]) {
    return candidateIdMap[originalId];
  }
  candidateIdCounter++;
  // 提取原始 ID 的关键部分
  var shortId = originalId;
  // 如果包含斜杠或冒号，取最后一部分
  var parts = originalId.split(/[/::]/);
  if (parts.length > 1) {
    shortId = parts[parts.length - 1];
  }
  // 如果仍然太长，截取前 20 字符
  if (shortId.length > 20) {
    shortId = shortId.slice(0, 20);
  }
  candidateIdMap[originalId] = shortId;
  return shortId;
}

/**
 * 重置 ID 映射（刷新模型列表时调用）。
 */
function resetCandidateIdMap() {
  Object.keys(candidateIdMap).forEach(function(key) {
    delete candidateIdMap[key];
  });
  candidateIdCounter = 0;
}

function escapeHtml(text) {
  var d = document.createElement('div');
  d.textContent = String(text);
  return d.innerHTML;
}
