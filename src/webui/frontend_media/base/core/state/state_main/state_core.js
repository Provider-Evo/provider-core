// ========================= State Core =========================
// 拆分自 state.js（原文件超 400 行上限）。
// 本文件必须最先加载：定义 defaultSettings / state 对象 / DOM 元素引用等全局量，
// 供其余 state_*.js 文件引用。
//
// 注意：state.settings 在此处初始化为 null 占位。真正的赋值
// （state.settings = loadSettings();）在 state_settings.js 加载时执行，
// 因为 loadSettings() 函数定义在该文件中——经典 <script> 标签之间不共享
// 函数声明提升（hoisting），必须等对应文件加载完成后才能调用。

const defaultSettings = {
  theme: 'auto',
  refreshInterval: 0,
  timeoutMs: 30000,
  streamIdleTimeoutMs: 60000,
  compact: '0',
  fontSizeBase: 14,
};
const TAB_ALIAS_MAP = { overview: 'dashboard', stats: 'dashboard', platforms: 'routing', models: 'routing', config: 'settings', autoupdate: 'settings' };
const initialTabRaw = localStorage.getItem('provider.webui.activeTab') || document.body.dataset.initialTab || 'dashboard';
const initialTab = TAB_ALIAS_MAP[initialTabRaw] || initialTabRaw;
const state = {
  timer: null,
  models: [],
  modelsLoaded: false,
  summary: null,
  settings: null, // 由 state_settings.js 加载后赋值为 loadSettings()
  activeTab: initialTab,
  configDirty: false,
  configSaveTimer: null,
  configSaveDebounceMs: 1000,
};

function resolveModelCapabilities(model) {
  if (!model || typeof model !== 'object') return {};
  var ownedBy = String(model.owned_by || '');
  var platformCaps = (((state.summary || {}).capabilities || {})[ownedBy]) || {};
  var caps = {};
  var key;
  for (key in platformCaps) {
    if (platformCaps[key]) caps[key] = true;
  }
  var modelCaps = model.capabilities || {};
  for (key in modelCaps) {
    if (modelCaps[key]) caps[key] = true;
  }
  return caps;
}

const logBox = document.getElementById('logBox');
const platformGrid = document.getElementById('platformGrid');
const modelGrid = document.getElementById('modelGrid');
const configGrid = document.getElementById('configGrid');
const configSaveStatus = document.getElementById('configSaveStatus');
const overviewGrid = document.getElementById('overviewGrid');
const overviewNotice = document.getElementById('overviewNotice');
const themeState = document.getElementById('themeState');
const refreshState = document.getElementById('refreshState');
const toastWrap = document.getElementById('toastWrap');
const socketNotice = document.getElementById('socketNotice');
let logsSocket = null;

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

function escapeHtml(text) {
  var d = document.createElement('div');
  d.textContent = String(text);
  return d.innerHTML;
}
