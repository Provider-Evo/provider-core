// ========================= Settings =========================
// 拆分自 state.js。依赖 state_core.js（state / defaultSettings / fetchJson）已加载。

function loadSettings() {
  try {
    return Object.assign({}, defaultSettings, JSON.parse(localStorage.getItem('provider.webui.settings') || '{}'));
  } catch (error) {
    return Object.assign({}, defaultSettings);
  }
}

// state_core.js 中 state.settings 初始化为 null 占位，此处补上真正的值。
state.settings = loadSettings();

function getStreamIdleTimeoutMs() {
  const value = Number(state.settings.streamIdleTimeoutMs);
  if (Number.isFinite(value) && value >= 5000) {
    return value;
  }
  return defaultSettings.streamIdleTimeoutMs;
}

function saveSettings() {
  localStorage.setItem('provider.webui.settings', JSON.stringify(state.settings));
  applyTheme();
  applyCompact();
  applyFontSize();
  scheduleRefresh();
  persistWebUISettings();
}

async function persistWebUISettings() {
  try {
    var body = Object.assign({}, await fetchJson('/v1/webui/config').catch(function() { return {}; }));
    body.theme = state.settings.theme;
    body.refreshInterval = state.settings.refreshInterval;
    body.timeoutMs = state.settings.timeoutMs;
    body.streamIdleTimeoutMs = state.settings.streamIdleTimeoutMs;
    body.compact = state.settings.compact;
    body.fontSizeBase = state.settings.fontSizeBase;
    await fetch('/v1/webui/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  } catch (e) { /* ignore */ }
}

async function loadWebUISettings() {
  try {
    var saved = await fetchJson('/v1/webui/config');
    if (!saved || typeof saved !== 'object') saved = {};
    var voice = loadVoiceSettings();
    if (!saved.sttModel && voice.sttModel) saved.sttModel = voice.sttModel;
    if (!saved.ttsModel && voice.ttsModel) saved.ttsModel = voice.ttsModel;
    if (!saved.ttsPrompt && voice.ttsPrompt) saved.ttsPrompt = voice.ttsPrompt;
    var changed = false;
    if (saved.theme) { state.settings.theme = saved.theme; changed = true; }
    if (typeof saved.refreshInterval === 'number') { state.settings.refreshInterval = saved.refreshInterval; changed = true; }
    if (typeof saved.timeoutMs === 'number') { state.settings.timeoutMs = saved.timeoutMs; changed = true; }
    if (typeof saved.streamIdleTimeoutMs === 'number') { state.settings.streamIdleTimeoutMs = saved.streamIdleTimeoutMs; changed = true; }
    if (saved.compact) { state.settings.compact = saved.compact; changed = true; }
    if (typeof saved.fontSizeBase === 'number') { state.settings.fontSizeBase = saved.fontSizeBase; changed = true; }
    if (typeof _applyWebuiRuntime === 'function') _applyWebuiRuntime(saved);
    return changed || Object.keys(saved).length > 0;
  } catch (e) { return false; }
}

async function initSettingsFromServer() {
  await loadWebUISettings();
  applyTheme();
  applyCompact();
  applyFontSize();
  scheduleRefresh();
}

function normalizeVoiceSettings(source) {
  source = source || {};
  var nested = source.voice && typeof source.voice === 'object' ? source.voice : {};
  return {
    sttModel: source.sttModel || nested.sttModel || '',
    ttsModel: source.ttsModel || nested.ttsModel || '',
    ttsPrompt: source.ttsPrompt || nested.ttsPrompt || '',
    recordingDeviceId: source.recordingDeviceId || nested.recordingDeviceId || '',
  };
}

function loadVoiceSettings() {
  try {
    var stored = JSON.parse(localStorage.getItem('provider.webui.voice') || '{}');
    return normalizeVoiceSettings(stored);
  } catch (e) {
    return normalizeVoiceSettings({});
  }
}

function saveVoiceSettings(vs) {
  var normalized = normalizeVoiceSettings(vs);
  localStorage.setItem('provider.webui.voice', JSON.stringify(normalized));
  if (window._chatInputBox && typeof window._chatInputBox.updateVoice === 'function') {
    window._chatInputBox.updateVoice(normalized);
  } else if (window._chatInputBox) {
    window._chatInputBox._opts.voice = normalized;
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
  if (themeState) themeState.textContent = t('header.theme', { value: state.settings.theme });
  var settingsTheme = document.getElementById('settingsThemeDisplay');
  if (settingsTheme) settingsTheme.textContent = state.settings.theme || 'auto';
  var themeSelect = document.getElementById('themeSelect');
  if (themeSelect) themeSelect.value = state.settings.theme;
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
  var compactSelect = document.getElementById('compactSelect');
  if (compactSelect) compactSelect.value = state.settings.compact;
}

function applyFontSize() {
  var size = parseInt(state.settings.fontSizeBase) || 14;
  document.documentElement.style.setProperty('--font-size-base', size + 'px');
  var slider = document.getElementById('globalFontSizeRange');
  if (slider) slider.value = size;
  var display = document.getElementById('globalFontSizeDisplay');
  if (display) display.textContent = size + 'px';
}

(function () {
  var slider = document.getElementById('globalFontSizeRange');
  if (slider) {
    slider.addEventListener('input', function (e) {
      state.settings.fontSizeBase = parseInt(e.target.value) || 14;
      localStorage.setItem('provider.webui.settings', JSON.stringify(state.settings));
      applyFontSize();
      persistWebUISettings();
    });
  }
})();

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
  var settingsRefresh = document.getElementById('settingsRefreshDisplay');
  if (settingsRefresh) {
    settingsRefresh.textContent = interval > 0 ? (interval + 's') : t('settings.refreshManual');
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
  if (typeof _updateConfigSaveBtn === 'function') _updateConfigSaveBtn();
  state.configSaveTimer = setTimeout(function() {
    saveConfig();
  }, state.configSaveDebounceMs);
}
