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
let _logSearchRegex = localStorage.getItem('provider.logSearchRegex') === 'true';
let _logModuleFilter = 'all';
let _logFontSize = localStorage.getItem('provider.logFontSize') || 'small';
let _logDateFrom = localStorage.getItem('provider.logDateFrom') || '';
let _logDateTo = localStorage.getItem('provider.logDateTo') || '';
let _logFilterExpanded = localStorage.getItem('provider.logFilterExpanded') === 'true';
let _uniqueModules = [];
let _logSeenIds = {};  // 去重

let _logFilteredCache = null;
let _logRenderTimer = null;

const _LOG_FONT_CONFIG = {
  small:  { timeW: 76, levelW: 38, moduleW: 112, colGap: 8, linePad: 2 },
  medium: { timeW: 88, levelW: 44, moduleW: 128, colGap: 8, linePad: 3 },
  large:  { timeW: 100, levelW: 50, moduleW: 144, colGap: 10, linePad: 4 },
};

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

function _getLogFontConfig() {
  return _LOG_FONT_CONFIG[_logFontSize] || _LOG_FONT_CONFIG.small;
}

function _formatLogLevelTag(level) {
  return '[' + _formatLogLevel(level) + ']';
}

function _logModuleStyleAttr(entry) {
  var parts = [];
  if (entry.moduleColor) parts.push('color:' + entry.moduleColor);
  if (entry.moduleBold) parts.push('font-weight:700');
  return parts.length ? ' style="' + parts.join(';') + '"' : '';
}

function _createLogEntryHTML(entry) {
  var level = entry.level || 'INFO';
  var levelTag = _escapeHtml(_formatLogLevelTag(level));
  var levelClass = 'log-col-level log-level-' + _escapeHtml(level);
  var ts = _escapeHtml(_formatLogTimestamp(entry.timestamp));
  var mod = _escapeHtml(entry.module || '');
  var msg = _escapeHtml(entry.message || '');
  var modStyle = _logModuleStyleAttr(entry);

  return '<div class="log-entry">' +
    '<div class="log-entry-mobile">' +
      '<div class="log-mobile-meta">' +
        '<span class="log-col-time">' + ts + '</span>' +
        '<span class="' + levelClass + '">' + levelTag + '</span>' +
      '</div>' +
      '<div class="log-col-module"' + modStyle + '>' + mod + '</div>' +
      '<div class="log-col-msg"' + modStyle + '>' + msg + '</div>' +
    '</div>' +
    '<div class="log-entry-desktop">' +
      '<span class="log-col-time">' + ts + '</span>' +
      '<span class="' + levelClass + '">' + levelTag + '</span>' +
      '<span class="log-col-module"' + modStyle + '>' + mod + '</span>' +
      '<span class="log-col-msg">' + msg + '</span>' +
    '</div>' +
  '</div>';
}

function _logEntryMatchesFilter(entry) {
  if (_logLevelFilter !== 'all') {
    var entryPri = _LOG_LEVEL_PRIORITY[entry.level] || 0;
    var filterPri = _LOG_LEVEL_PRIORITY[_logLevelFilter] || 0;
    if (entryPri < filterPri) return false;
  }
  if (_logModuleFilter !== 'all' && entry.module !== _logModuleFilter) return false;
  if (_logSearchQuery) {
    var msg = entry.message || '';
    var mod = entry.module || '';
    if (_logSearchRegex) {
      try {
        var re = new RegExp(_logSearchQuery, 'i');
        if (!re.test(msg) && !re.test(mod)) return false;
      } catch (e) {
        var q = _logSearchQuery.toLowerCase();
        if (msg.toLowerCase().indexOf(q) === -1 && mod.toLowerCase().indexOf(q) === -1) return false;
      }
    } else {
      var q = _logSearchQuery.toLowerCase();
      if (msg.toLowerCase().indexOf(q) === -1 && mod.toLowerCase().indexOf(q) === -1) return false;
    }
  }
  if (_logDateFrom || _logDateTo) {
    var ts = entry.timestamp || '';
    if (ts) {
      var entryDate = ts.substring(0, 10);
      if (_logDateFrom && entryDate < _logDateFrom) return false;
      if (_logDateTo && entryDate > _logDateTo) return false;
    }
  }
  return true;
}

// ========================= Log Rendering =========================

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
  var title = options.title || t('dialog.titleDefault');
  var confirmText = options.confirmText || t('dialog.ok');
  var cancelText = options.cancelText || t('dialog.cancel');

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
  var title = options.title || t('dialog.inputTitle');
  var defaultValue = options.defaultValue || '';
  var confirmText = options.confirmText || t('dialog.ok');
  var cancelText = options.cancelText || t('dialog.cancel');
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
  themeState.textContent = t('header.theme', { value: state.settings.theme });
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
    refreshState.textContent = t('header.refreshInterval', { value: interval });
  } else {
    refreshState.textContent = t('header.refreshManual');
  }
}

function updateConfigSaveStatus() {
  if (configSaveStatus) {
    if (state.configDirty) {
      configSaveStatus.textContent = t('common.unsaved');
      configSaveStatus.className = 'status-dirty flex items-center';
    } else {
      configSaveStatus.textContent = t('common.saved');
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
      loaderEl.textContent = t('common.loading');
      panel.appendChild(loaderEl);
    }
    try {
      await LazyLoader.loadTabResources(nextTab);
    } finally {
      if (loaderEl) loaderEl.remove();
    }
  }

  _initTab(nextTab);
  if (nextTab === 'logs') {
    requestAnimationFrame(function() {
      _renderLogs();
      _logAutoScrollToBottom();
    });
  }
}

function _initTab(tabName) {
  if (_initializedTabs.has(tabName)) return;
  _initializedTabs.add(tabName);

  switch (tabName) {
    case 'logs':
      _applyLogFontSize();
      _renderLogs();
      break;
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

_applyLogFontSize();

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
