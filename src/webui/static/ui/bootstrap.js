document.getElementById('fabThemeButton').addEventListener('click', function() {
  // Portable toggle: only switches between light and dark (no auto)
  var current = state.settings.theme;
  state.settings.theme = (current === 'light') ? 'dark' : 'light';
  saveSettings();
  toast('主题已切换为 ' + state.settings.theme, 'ok');
});
function _openPortable() {
  portablePanel.style.display = '';
  _refreshRecordingDevices();
  requestAnimationFrame(function() { portablePanel.classList.add('is-visible'); });
}
function _closePortable() {
  portablePanel.classList.remove('is-visible');
  setTimeout(function() { portablePanel.style.display = 'none'; }, 200);
}
document.getElementById('portableButton').addEventListener('click', function() {
  if (!portablePanel.style.display || portablePanel.style.display === 'none') _openPortable();
  else _closePortable();
});
document.getElementById('portableBackdrop').addEventListener('click', _closePortable);
document.getElementById('themeSelect').addEventListener('change', function(event) {
  state.settings.theme = event.target.value;
  saveSettings();
});
document.getElementById('refreshIntervalInput').value = String(state.settings.refreshInterval);
document.getElementById('refreshIntervalInput').addEventListener('change', function(event) {
  state.settings.refreshInterval = Number(event.target.value || 0);
  saveSettings();
});
document.getElementById('timeoutInput').value = String(state.settings.timeoutMs);
document.getElementById('timeoutInput').addEventListener('change', function(event) {
  state.settings.timeoutMs = Number(event.target.value || defaultSettings.timeoutMs);
  saveSettings();
});
document.getElementById('compactSelect').addEventListener('change', function(event) {
  state.settings.compact = event.target.value;
  saveSettings();
});
document.getElementById('platformSearchInput').addEventListener('input', function() {
  renderPlatforms((state.summary || {}).platforms || {});
});
document.getElementById('modelSearchInput').addEventListener('input', function() {
  renderModels(state.models);
});
document.getElementById('modelPlatformSelect').addEventListener('change', function() {
  renderModels(state.models);
});
document.getElementById('modelCapabilitySelect').addEventListener('change', function() {
  renderModels(state.models);
});
document.getElementById('copySummaryButton').addEventListener('click', function() {
  copyText(JSON.stringify(state.summary || {}, null, 2), '摘要已复制');
});
document.getElementById('exportSummaryButton').addEventListener('click', exportSummary);
document.getElementById('copyConfigButton').addEventListener('click', function() {
  copyText(configJsonBox.textContent || '{}', '配置摘要已复制');
});
document.getElementById('clearLogButton').addEventListener('click', function() {
  clearLogs();
});
document.getElementById('logExportBtn').addEventListener('click', function() {
  exportLogs();
});
document.getElementById('logAutoScrollBtn').addEventListener('click', function() {
  toggleAutoScroll();
});
document.getElementById('logLevelSelect').addEventListener('change', function() {
  _logLevelFilter = this.value;
  localStorage.setItem('provider.logLevelFilter', _logLevelFilter);
  filterLogs();
});
document.getElementById('logSearchInput').addEventListener('input', function() {
  _logSearchQuery = this.value;
  filterLogs();
});
document.getElementById('logRegexBtn').addEventListener('click', function() { toggleLogRegex(); });
document.getElementById('logModuleSelect').addEventListener('change', function() {
  _logModuleFilter = this.value;
  filterLogs();
});
// Collapsible advanced filters toggle
document.getElementById('logFilterToggleBtn').addEventListener('click', function() {
  _toggleLogFilters();
});
// Date range filters
document.getElementById('logDateFrom').addEventListener('change', function() {
  _logDateFrom = this.value;
  localStorage.setItem('provider.logDateFrom', _logDateFrom);
  _updateLogClearDateBtn();
  filterLogs();
});
document.getElementById('logDateTo').addEventListener('change', function() {
  _logDateTo = this.value;
  localStorage.setItem('provider.logDateTo', _logDateTo);
  _updateLogClearDateBtn();
  filterLogs();
});
document.getElementById('logClearDateBtn').addEventListener('click', function() {
  _logDateFrom = '';
  _logDateTo = '';
  localStorage.removeItem('provider.logDateFrom');
  localStorage.removeItem('provider.logDateTo');
  document.getElementById('logDateFrom').value = '';
  document.getElementById('logDateTo').value = '';
  _updateLogClearDateBtn();
  filterLogs();
});
// Initialize auto-scroll button state and restore level filter
(function() {
  var btn = document.getElementById('logAutoScrollBtn');
  if (btn) btn.classList.toggle('active', _logAutoScroll);
  // Restore level filter select
  var levelSel = document.getElementById('logLevelSelect');
  if (levelSel) levelSel.value = _logLevelFilter;
  // Restore collapsible filter panel state
  if (_logFilterExpanded) {
    var panel = document.getElementById('logAdvancedFilters');
    var icon = document.getElementById('logFilterToggleIcon');
    var toggleBtn = document.getElementById('logFilterToggleBtn');
    if (panel) panel.style.display = '';
    if (icon) icon.innerHTML = '&#9650;';
    if (toggleBtn) toggleBtn.classList.add('active');
  }
  // Restore date range inputs
  var dateFrom = document.getElementById('logDateFrom');
  var dateTo = document.getElementById('logDateTo');
  if (dateFrom && _logDateFrom) dateFrom.value = _logDateFrom;
  if (dateTo && _logDateTo) dateTo.value = _logDateTo;
  _updateLogClearDateBtn();
  // Restore regex search state
  _updateRegexBtn();
})();
// Font size buttons
(function() {
  var savedSize = localStorage.getItem('provider.logFontSize') || 'small';
  _logFontSize = savedSize;
  _applyLogFontSize();
  document.querySelectorAll('.log-font-btn').forEach(function(btn) {
    if (btn.dataset.size === savedSize) {
      btn.classList.add('active');
    } else {
      btn.classList.remove('active');
    }
    btn.addEventListener('click', function() {
      document.querySelectorAll('.log-font-btn').forEach(function(b) { b.classList.remove('active'); });
      btn.classList.add('active');
      _logFontSize = btn.dataset.size;
      _applyLogFontSize();
      localStorage.setItem('provider.logFontSize', _logFontSize);
    });
  });
})();
document.getElementById('reloadServerButton').addEventListener('click', reloadServer);
document.getElementById('reloadConfigButton').addEventListener('click', reloadConfigFromFile);
// Restart overlay buttons
document.getElementById('restartRefreshBtn').addEventListener('click', function() { location.reload(); });
document.getElementById('restartRetryBtn').addEventListener('click', function() { retryHealthCheck(); });
document.getElementById('configEditToggle').addEventListener('click', toggleConfigEdit);
if (configEditArea) {
  configEditArea.addEventListener('input', function() {
    try {
      JSON.parse(configEditArea.value);
      scheduleConfigSave();
    } catch (e) {
      toast('JSON 格式错误', 'error');
    }
  });
}
document.querySelectorAll('.tab-button[data-tab]').forEach(function(node) {
  node.id = 'tab-' + node.dataset.tab + '-button';
  node.addEventListener('click', function() {
    switchTab(node.dataset.tab);
  });
});

// Autoupdate & chat initialization moved to lazy per-tab init functions
// (_initAutoupdateTab, _initChatTab) — called by state.js _initTab()

applyTheme();
applyCompact();
applyVoiceSettings();

// Voice settings change handlers
['voiceSttModel', 'voiceTtsModel', 'voiceTtsPrompt'].forEach(function(id) {
  var el = document.getElementById(id);
  if (el) {
    el.addEventListener('change', function() {
      saveVoiceSettings({
        sttModel: (document.getElementById('voiceSttModel') || {}).value || '',
        ttsModel: (document.getElementById('voiceTtsModel') || {}).value || '',
        ttsPrompt: (document.getElementById('voiceTtsPrompt') || {}).value || '',
      });
    });
  }
});

// ========================= Custom Dropdown Initialization =========================
window._dropdowns = {};
['modelPlatformSelect', 'modelCapabilitySelect', 'chatModelSelect',
 'chatProtocolSelect', 'themeSelect', 'compactSelect', 'tabLayoutSelect',
 'voiceSttModel', 'voiceTtsModel', 'recordingDeviceSelect',
 'autoupdateBranch', 'requestStatusFilter', 'requestTimeFilter'].forEach(function(id) {
  var el = document.getElementById(id);
  if (el) {
    window._dropdowns[id] = new CustomDropdown(el);
  }
});
// Re-apply settings after dropdown initialization (needed for themeSelect/compactSelect)
applyTheme();
applyCompact();

// Load portable settings from server-side config.toml (overrides localStorage)
initSettingsFromServer();

scheduleRefresh();
switchTab(initialTab);
connectLogsSocket();
refreshAll();

// ========================= MotionKit Integration =========================
// Initialize motion effects after DOM is ready
if (typeof initAllMotionEffects === 'function') {
  // Small delay to ensure all dynamic content is rendered
  setTimeout(initAllMotionEffects, 100);
}

// Load models list moved to _initChatTab() (lazy)

// Load voice model lists for STT/TTS dropdowns
(async function loadVoiceModels() {
  try {
    var result = await fetchJson("/v1/models");
    if (!result || !result.data) return;
    var models = result.data;
    var sttOpts = [{ value: '', text: '不使用' }];
    var ttsOpts = [{ value: '', text: '不使用' }];
    for (var i = 0; i < models.length; i++) {
      var caps = models[i].capabilities || {};
      if (caps.stt || (caps.chat && caps.vision)) sttOpts.push({ value: models[i].id, text: models[i].id });
      if (caps.tts || caps.audio_gen) ttsOpts.push({ value: models[i].id, text: models[i].id });
    }
    var sttDropdown = window._dropdowns && window._dropdowns['voiceSttModel'];
    var ttsDropdown = window._dropdowns && window._dropdowns['voiceTtsModel'];
    if (sttDropdown) {
      sttDropdown.setOptions(sttOpts, false);
      var vs = loadVoiceSettings();
      if (vs.sttModel) sttDropdown.setValue(vs.sttModel);
    }
    if (ttsDropdown) {
      ttsDropdown.setOptions(ttsOpts, false);
      var vs = loadVoiceSettings();
      if (vs.ttsModel) ttsDropdown.setValue(vs.ttsModel);
    }
  } catch (e) { /* ignore */ }
})();

// Voice dropdown change handlers
['voiceSttModel', 'voiceTtsModel'].forEach(function(id) {
  var dropdown = window._dropdowns && window._dropdowns[id];
  if (dropdown) {
    dropdown.onChange = function(value) {
      saveVoiceSettings({
        sttModel: (window._dropdowns['voiceSttModel'] || {}).value || document.getElementById('voiceSttModel').value || '',
        ttsModel: (window._dropdowns['voiceTtsModel'] || {}).value || document.getElementById('voiceTtsModel').value || '',
        ttsPrompt: (document.getElementById('voiceTtsPrompt') || {}).value || '',
      });
    };
  }
});

// TTS prompt restore default button
var ttsRestoreBtn = document.getElementById('voiceTtsPromptRestoreBtn');
if (ttsRestoreBtn) {
  ttsRestoreBtn.addEventListener('click', async function() {
    try {
      var resp = await fetch('/prompts/tts_default.prompt');
      if (resp.ok) {
        var text = await resp.text();
        var textarea = document.getElementById('voiceTtsPrompt');
        if (textarea) {
          textarea.value = text.trim();
          saveVoiceSettings({
            sttModel: (window._dropdowns['voiceSttModel'] || {}).value || document.getElementById('voiceSttModel').value || '',
            ttsModel: (window._dropdowns['voiceTtsModel'] || {}).value || document.getElementById('voiceTtsModel').value || '',
            ttsPrompt: text.trim(),
          });
          toast('已恢复默认 Prompt', 'ok');
        }
      } else {
        toast('加载默认 Prompt 失败', 'error');
      }
    } catch (e) {
      toast('加载默认 Prompt 失败: ' + e.message, 'error');
    }
  });
}

// Restore chat history moved to _initChatTab() (lazy)

// Override switchTab to scroll to top of content container
var originalSwitchTab = window.switchTab;
if (typeof switchTab === 'function') {
  window.switchTab = function(tabName) {
    originalSwitchTab(tabName);

    // Scroll to top of the right-side content container
    var contentContainer = document.querySelector('.webui-content');
    if (contentContainer) {
      contentContainer.scrollTop = 0;
    }

    // Animate the newly shown tab panel
    var activePanel = document.querySelector('.tab-panel.active');
    if (activePanel && typeof animateTabIn === 'function') {
      setTimeout(function() { animateTabIn(activePanel); }, 50);
    }
  };
}

// ========================= Persist Helpers =========================
async function persistSave(filename, data) {
  try {
    await fetch('/v1/webui/persist/' + filename, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data)
    });
  } catch (e) { /* ignore */ }
}

async function persistLoad(filename) {
  try {
    var resp = await fetch('/v1/webui/persist/' + filename);
    if (resp.ok) return await resp.json();
  } catch (e) { /* ignore */ }
  return null;
}

// ========================= Recording Device =========================
async function _refreshRecordingDevices() {
  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
    var devices = await navigator.mediaDevices.enumerateDevices();
    var audioInputs = devices.filter(function(d) { return d.kind === 'audioinput'; });
    var opts = [{ value: '', text: '默认设备' }];
    for (var i = 0; i < audioInputs.length; i++) {
      opts.push({
        value: audioInputs[i].deviceId,
        text: audioInputs[i].label || ('麦克风 ' + (i + 1))
      });
    }
    var dropdown = window._dropdowns && window._dropdowns['recordingDeviceSelect'];
    if (dropdown) {
      dropdown.setOptions(opts, false);
      var saved = await persistLoad('config.toml');
      if (saved && saved.recordingDeviceId) {
        dropdown.setValue(saved.recordingDeviceId);
      }
    }
  } catch (e) { /* ignore */ }
}

// Initial load of recording devices
_refreshRecordingDevices();

// Recording device change handler
(function() {
  async function _saveRecordingDevice(deviceId) {
    var existing = await persistLoad('config.toml') || {};
    existing.recordingDeviceId = deviceId;
    persistSave('config.toml', existing);
  }
  var dropdown = window._dropdowns && window._dropdowns['recordingDeviceSelect'];
  if (dropdown) {
    dropdown.onChange = function(value) {
      _saveRecordingDevice(value);
    };
  }
  var el = document.getElementById('recordingDeviceSelect');
  if (el) {
    el.addEventListener('change', function() {
      _saveRecordingDevice(el.value);
    });
  }
})();

// ========================= Lazy Per-Tab Init Functions =========================
// Called by state.js _initTab() the first time each tab is shown.

function _initChatTab() {
  // Chat InputBox initialization
  var chatClearBtn = document.getElementById('chatClearBtn');
  var chatRunTestsBtn = document.getElementById('chatRunTestsBtn');
  var chatBatchToggleBtn = document.getElementById('chatBatchToggleBtn');

  if (chatBatchToggleBtn) {
    chatBatchToggleBtn.addEventListener('click', function() {
      var section = document.getElementById('batchTestSection');
      if (section) {
        section.classList.toggle('hidden');
        chatBatchToggleBtn.textContent = section.classList.contains('hidden') ? '批量测试' : '收起批量测试';
      }
    });
  }

  if (typeof InputBox !== 'undefined' && document.getElementById('chatInputBox')) {
    var voiceSettings = {};
    try { voiceSettings = JSON.parse(localStorage.getItem('provider.webui.voice') || '{}'); } catch(e) {}
    window._chatInputBox = InputBox.create('#chatInputBox', {
      placeholder: '输入消息... (Shift+Enter 换行, Enter 发送)',
      buttons: { file: true, voice: true, send: true },
      voice: {
        sttModel: voiceSettings.sttModel || '',
        ttsModel: voiceSettings.ttsModel || '',
        ttsPrompt: voiceSettings.ttsPrompt || '',
      },
      onSend: function(text, files) { sendChatMessage(text, files); },
      onVoiceStart: function() { toast('录音中...', 'info'); },
      onVoiceEnd: function() {},
    });
  }

  if (chatClearBtn) {
    chatClearBtn.addEventListener('click', function() {
      clearChatMessages();
      toast('对话已清空', 'ok');
    });
  }
  if (chatRunTestsBtn) {
    chatRunTestsBtn.addEventListener('click', runChatTests);
  }
  if (typeof loadModelsList === 'function') loadModelsList();
  if (typeof loadChatState === 'function') loadChatState();
  if (typeof _loadTools === 'function') _loadTools();
}

function _initAutoupdateTab() {
  if (document.getElementById('autoupdateCheckBtn')) {
    document.getElementById('autoupdateCheckBtn').addEventListener('click', triggerAutoupdateCheck);
  }
  if (document.getElementById('autoupdateSaveBtn')) {
    document.getElementById('autoupdateSaveBtn').addEventListener('click', saveAutoupdateSettings);
  }
  if (document.getElementById('autoupdateApplyBtn')) {
    document.getElementById('autoupdateApplyBtn').addEventListener('click', applyAutoupdate);
  }
  if (document.getElementById('autoupdateAddMirrorBtn')) {
    document.getElementById('autoupdateAddMirrorBtn').addEventListener('click', function() {
      var mirrors = _getMirrorsFromUI();
      mirrors.push('');
      _renderMirrors(mirrors);
      var inputs = document.querySelectorAll('#autoupdateMirrorsList .mirror-url');
      if (inputs.length) inputs[inputs.length - 1].focus();
    });
  }
  loadAutoupdateSettings();
}

function _initStatsTab() {
  if (typeof StatsFeature !== 'undefined') StatsFeature.init();
  if (typeof RequestInspector !== 'undefined') RequestInspector.init();
  var statsRefreshBtn = document.getElementById('statsRefreshBtn');
  var statsResetBtn = document.getElementById('statsResetBtn');
  if (statsRefreshBtn) statsRefreshBtn.addEventListener('click', function() { StatsFeature.refresh(); });
  if (statsResetBtn) statsResetBtn.addEventListener('click', async function() {
    try {
      await Api.post('/v1/webui/stats/reset');
      toast('统计已重置', 'ok');
      StatsFeature.refresh();
    } catch(e) { toast('重置失败: ' + e.message, 'error'); }
  });
}

function _initTerminalTab() {
  var localBtn = document.getElementById('terminalEmptyLocalBtn');
  var sshBtn = document.getElementById('terminalEmptySSHBtn');
  if (localBtn) localBtn.addEventListener('click', function() { TerminalManager.createTab('local'); });
  if (sshBtn) sshBtn.addEventListener('click', function() { TerminalManager.showSSHDialog(); });
}

function _initConfigTab() {
  if (typeof renderConfig === 'function' && state.summary) {
    renderConfig(state.summary);
  }
}

// ========================= Tab Layout Toggle =========================
var _tabLayoutConfig = { layout: 'horizontal', sidebarCompressed: false };

/**
 * Global registry for TabBar instances.
 * Modules (terminal, files) register their TabBar instances here
 * so that layout toggle changes can be propagated.
 */
window._tabBars = {};

function _applyTabLayout(layout) {
  var isVertical = (layout === 'vertical');
  var termContainer = document.getElementById('terminalContainer');
  var filesContainer = document.getElementById('filesContainer');

  // Toggle vertical class on containers (for container-level flex-direction)
  if (termContainer) termContainer.classList.toggle('tab-layout-vertical', isVertical);
  if (filesContainer) filesContainer.classList.toggle('tab-layout-vertical', isVertical);

  // Delegate layout + collapsed state to registered TabBar instances
  var bars = window._tabBars;
  var keys = Object.keys(bars);
  for (var i = 0; i < keys.length; i++) {
    if (bars[keys[i]] && typeof bars[keys[i]].setLayout === 'function') {
      bars[keys[i]].setLayout(layout, _tabLayoutConfig.sidebarCompressed);
    }
  }

  // Update select value
  var select = document.getElementById('tabLayoutSelect');
  if (select) select.value = layout;
  var dd = window._dropdowns && window._dropdowns['tabLayoutSelect'];
  if (dd) dd.setValue(layout);
}

// Initialize tab layout from saved config
(async function _initTabLayout() {
  try {
    var saved = await persistLoad('config.toml');
    if (saved && saved.layout) {
      _tabLayoutConfig.layout = saved.layout;
    }
    if (saved && typeof saved.sidebarCompressed === 'boolean') {
      _tabLayoutConfig.sidebarCompressed = saved.sidebarCompressed;
    }
  } catch (e) { /* ignore */ }
  _applyTabLayout(_tabLayoutConfig.layout);
})();

// Tab layout change handler
document.getElementById('tabLayoutSelect').addEventListener('change', async function(event) {
  _tabLayoutConfig.layout = event.target.value;
  _applyTabLayout(_tabLayoutConfig.layout);
  var existing = await persistLoad('config.toml') || {};
  existing.layout = _tabLayoutConfig.layout;
  existing.sidebarCompressed = _tabLayoutConfig.sidebarCompressed;
  persistSave('config.toml', existing);
  toast('标签栏布局: ' + (event.target.value === 'vertical' ? '竖向侧边' : '横向顶部'), 'ok');
});

// CustomDropdown onChange for tabLayoutSelect
(function() {
  var dropdown = window._dropdowns && window._dropdowns['tabLayoutSelect'];
  if (dropdown) {
    dropdown.onChange = async function(value) {
      _tabLayoutConfig.layout = value;
      _applyTabLayout(value);
      var existing = await persistLoad('config.toml') || {};
      existing.layout = value;
      existing.sidebarCompressed = _tabLayoutConfig.sidebarCompressed;
      persistSave('config.toml', existing);
      toast('标签栏布局: ' + (value === 'vertical' ? '竖向侧边' : '横向顶部'), 'ok');
    };
  }
})();
