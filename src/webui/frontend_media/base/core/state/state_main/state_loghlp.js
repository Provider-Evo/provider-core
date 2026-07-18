// ========================= Log Helpers =========================
// 拆分自 state.js。依赖 state_core.js 已加载（无直接依赖，但保持加载顺序）。

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
  if (entry.moduleColor) {
    var c = String(entry.moduleColor).replace(/[^a-zA-Z0-9#(),.\s]/g, '');
    if (c) parts.push('color:' + c);
  }
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
