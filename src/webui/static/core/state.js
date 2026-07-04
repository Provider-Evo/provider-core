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
let _logLineCount = 0;
let _logEntries = [];
const _logMaxEntries = 2000;

function ansiToHtml(text) {
  var escaped = text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  var colors = {
    '30': '#555', '31': '#e74c3c', '32': '#2ecc71', '33': '#f1c40f',
    '34': '#3498db', '35': '#9b59b6', '36': '#1abc9c', '37': '#ccc',
    '90': '#777', '91': '#ff6b6b', '92': '#51cf66', '93': '#ffd43b',
    '94': '#74c0fc', '95': '#da77f2', '96': '#63e6be', '97': '#fff'
  };
  var result = '';
  var openSpans = 0;
  var regex = /\x1b\[([\d;]*)m/g;
  var lastIndex = 0;
  var match;
  while ((match = regex.exec(escaped)) !== null) {
    result += escaped.substring(lastIndex, match.index);
    var codes = match[1].split(';');
    for (var i = 0; i < codes.length; i++) {
      var code = codes[i];
      if (code === '0' || code === '') {
        while (openSpans > 0) { result += '</span>'; openSpans--; }
      } else if (code === '1') {
        result += '<span style="font-weight:bold">'; openSpans++;
      } else if (code === '2') {
        result += '<span style="opacity:0.7">'; openSpans++;
      } else if (code === '3') {
        result += '<span style="font-style:italic">'; openSpans++;
      } else if (code === '4') {
        result += '<span style="text-decoration:underline">'; openSpans++;
      } else if (colors[code]) {
        result += '<span style="color:' + colors[code] + '">'; openSpans++;
      } else {
        var codeNum = parseInt(code, 10);
        if (codeNum >= 40 && codeNum <= 47) {
          // Background colors — skip silently
        } else if (codeNum >= 100 && codeNum <= 107) {
          // Bright background colors — skip silently
        }
      }
    }
    lastIndex = regex.lastIndex;
  }
  result += escaped.substring(lastIndex);
  while (openSpans > 0) { result += '</span>'; openSpans--; }
  return result;
}

function log(message) {
  // Skip timestamp prefix if message already starts with a date pattern (MM-DD from WebSocket)
  var hasDate = /^\d{2}-\d{2}\s/.test(message);
  var line = hasDate ? message : ('[' + new Date().toLocaleTimeString() + '] ' + message);
  _logEntries.unshift({ html: ansiToHtml(line) });

  // Prepend new entry to DOM
  var div = document.createElement('div');
  div.className = 'log-line';
  div.innerHTML = '<span class="log-ln">1</span>' + ansiToHtml(line);
  if (logBox.firstChild) {
    logBox.insertBefore(div, logBox.firstChild);
  } else {
    logBox.appendChild(div);
  }

  // Remove excess entries from both array and DOM
  while (_logEntries.length > _logMaxEntries) {
    _logEntries.pop();
    if (logBox.lastChild) logBox.removeChild(logBox.lastChild);
  }

  // Renumber all visible entries: #1 at top (newest), increasing downward
  var lines = logBox.children;
  for (var i = 0; i < lines.length; i++) {
    var ln = lines[i].querySelector('.log-ln');
    if (ln) ln.textContent = i + 1;
  }
}

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
