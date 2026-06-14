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

function log(message) {
  const line = '[' + new Date().toLocaleTimeString() + '] ' + message;
  logBox.textContent = line + '\n' + logBox.textContent;
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
  if (stt) stt.value = vs.sttModel || '';
  if (tts) tts.value = vs.ttsModel || '';
  if (prompt) prompt.value = vs.ttsPrompt || '';
}

function applyTheme() {
  const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  const theme = state.settings.theme === 'auto' ? (prefersDark ? 'dark' : 'light') : state.settings.theme;
  document.documentElement.setAttribute('data-theme', theme);
  themeState.textContent = 'theme: ' + state.settings.theme;
  document.getElementById('themeSelect').value = state.settings.theme;
  updateThemeIcon();
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

function switchTab(nextTab) {
  state.activeTab = nextTab;
  localStorage.setItem('provider.webui.activeTab', nextTab);
  document.querySelectorAll('.tab-button[data-tab]').forEach(function(node) {
    node.classList.toggle('active', node.dataset.tab === nextTab);
    node.setAttribute('aria-selected', node.dataset.tab === nextTab ? 'true' : 'false');
  });
  document.querySelectorAll('.tab-panel').forEach(function(node) {
    node.classList.toggle('active', node.id === 'tab-' + nextTab);
  });
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
