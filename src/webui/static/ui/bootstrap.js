document.getElementById('refreshButton').addEventListener('click', refreshAll);
document.getElementById('refreshModelsButton').addEventListener('click', refreshModels);
document.getElementById('fabThemeButton').addEventListener('click', function() {
  // Portable toggle: only switches between light and dark (no auto)
  var current = state.settings.theme;
  state.settings.theme = (current === 'light') ? 'dark' : 'light';
  saveSettings();
  toast('主题已切换为 ' + state.settings.theme, 'ok');
  log('主题已切换为 ' + state.settings.theme + '。');
});
function _openPortable() {
  portablePanel.style.display = 'block';
  var backdrop = document.getElementById('portableBackdrop');
  var inner = portablePanel.querySelector('section');
  if (typeof MotionKit !== 'undefined') {
    MotionKit.setState(backdrop, { opacity: 0 });
    MotionKit.opacityTo(backdrop, 1, 6);
    if (inner) {
      MotionKit.setState(inner, { opacity: 0, size: 92 });
      MotionKit.opacityTo(inner, 1, 6);
      MotionKit.sizeTo(inner, 100, 6);
    }
    // floatScale on dialog buttons
    var btns = portablePanel.querySelectorAll('button, select');
    btns.forEach(function(btn) {
      if (!btn._motionAttached && typeof MotionKit.floatScale === 'function') {
        MotionKit.floatScale(btn, 105, 97, 100, 0.15);
        btn._motionAttached = true;
      }
    });
  }
  // Re-enumerate recording devices when panel opens (ensures fresh labels after permission grant)
  _refreshRecordingDevices();
}
function _closePortable() {
  var backdrop = document.getElementById('portableBackdrop');
  var inner = portablePanel.querySelector('section');
  if (typeof MotionKit !== 'undefined' && inner) {
    MotionKit.opacityTo(inner, 0, 8);
    MotionKit.sizeTo(inner, 92, 8);
    MotionKit.opacityTo(backdrop, 0, 8);
    setTimeout(function() { portablePanel.style.display = 'none'; }, 200);
  } else {
    portablePanel.style.display = 'none';
  }
}
document.getElementById('portableButton').addEventListener('click', function() {
  if (portablePanel.style.display === 'none') _openPortable();
  else _closePortable();
});
document.getElementById('portableCloseBtn').addEventListener('click', _closePortable);
document.getElementById('portableBackdrop').addEventListener('click', _closePortable);
document.getElementById('themeSelect').addEventListener('change', function(event) {
  state.settings.theme = event.target.value;
  saveSettings();
});
document.getElementById('refreshIntervalInput').value = String(state.settings.refreshInterval);
document.getElementById('refreshIntervalInput').addEventListener('change', function(event) {
  state.settings.refreshInterval = Number(event.target.value || 0);
  saveSettings();
  log('自动刷新间隔已更新。');
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
  _logEntries = [];
  _logLineCount = 0;
  logBox.innerHTML = '';
  toast('日志已清空', 'ok');
});
document.getElementById('reloadServerButton').addEventListener('click', reloadServer);
document.getElementById('reloadConfigButton').addEventListener('click', reloadConfigFromFile);
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

// Autoupdate tab event listeners
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

// Chat InputBox initialization
var chatClearBtn = document.getElementById('chatClearBtn');
var chatRunTestsBtn = document.getElementById('chatRunTestsBtn');
var chatBatchToggleBtn = document.getElementById('chatBatchToggleBtn');

// Batch test section toggle
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
    onSend: function(text, files) {
      sendChatMessage(text, files);
    },
    onVoiceStart: function() { toast('录音中...', 'info'); },
    onVoiceEnd: function() {},
  });
}

if (chatClearBtn) {
  chatClearBtn.addEventListener('click', function() {
    clearChatMessages();
    chatConversationHistory = [];
    toast('对话已清空', 'ok');
  });
}
if (chatRunTestsBtn) {
  chatRunTestsBtn.addEventListener('click', runChatTests);
}

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

scheduleRefresh();
switchTab(initialTab);
connectLogsSocket();
refreshAll();
loadAutoupdateSettings();

// ========================= MotionKit Integration =========================
// Initialize motion effects after DOM is ready
if (typeof initAllMotionEffects === 'function') {
  // Small delay to ensure all dynamic content is rendered
  setTimeout(initAllMotionEffects, 100);
}

// Load models list for chat test
if (typeof loadModelsList === 'function') {
  loadModelsList();
}

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

// Restore chat history from localStorage
if (typeof loadChatState === 'function') {
  loadChatState();
}

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
      var saved = await persistLoad('config.json');
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
    var existing = await persistLoad('config.json') || {};
    existing.recordingDeviceId = deviceId;
    persistSave('config.json', existing);
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

// ========================= Tab Layout Toggle =========================
var _tabLayoutConfig = { layout: 'horizontal', sidebarCompressed: false };

function _applyTabLayout(layout) {
  var isVertical = (layout === 'vertical');
  var termContainer = document.getElementById('terminalContainer');
  var filesContainer = document.getElementById('filesContainer');
  var termTabBar = document.getElementById('terminalTabBar');
  var filesTabBar = document.getElementById('filesTabBar');

  // Toggle vertical class on containers
  if (termContainer) termContainer.classList.toggle('tab-layout-vertical', isVertical);
  if (filesContainer) filesContainer.classList.toggle('tab-layout-vertical', isVertical);

  // Ensure sidebar toggle buttons exist in tab bars
  if (isVertical) {
    _ensureSidebarToggle(termTabBar, 'terminal');
    _ensureSidebarToggle(filesTabBar, 'files');
    _applySidebarCompressed(_tabLayoutConfig.sidebarCompressed);
  } else {
    // Remove sidebar toggles and compressed state
    _removeSidebarToggle(termTabBar);
    _removeSidebarToggle(filesTabBar);
    if (termTabBar) termTabBar.classList.remove('tab-bar-compressed');
    if (filesTabBar) filesTabBar.classList.remove('tab-bar-compressed');
  }

  // Update select value
  var select = document.getElementById('tabLayoutSelect');
  if (select) select.value = layout;
  var dd = window._dropdowns && window._dropdowns['tabLayoutSelect'];
  if (dd) dd.setValue(layout);
}

function _ensureSidebarToggle(tabBar, type) {
  if (!tabBar) return;
  var existing = tabBar.querySelector('.tab-sidebar-toggle');
  if (existing) return;
  var btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'tab-sidebar-toggle';
  btn.textContent = _tabLayoutConfig.sidebarCompressed ? '\u25B6' : '\u25C0';
  btn.title = _tabLayoutConfig.sidebarCompressed ? '展开侧边栏' : '压缩侧边栏';
  btn.addEventListener('click', async function() {
    _tabLayoutConfig.sidebarCompressed = !_tabLayoutConfig.sidebarCompressed;
    _applySidebarCompressed(_tabLayoutConfig.sidebarCompressed);
    var existing = await persistLoad('config.json') || {};
    existing.layout = _tabLayoutConfig.layout;
    existing.sidebarCompressed = _tabLayoutConfig.sidebarCompressed;
    persistSave('config.json', existing);
  });
  tabBar.insertBefore(btn, tabBar.firstChild);
}

function _removeSidebarToggle(tabBar) {
  if (!tabBar) return;
  var existing = tabBar.querySelector('.tab-sidebar-toggle');
  if (existing) existing.remove();
}

function _applySidebarCompressed(compressed) {
  var termTabBar = document.getElementById('terminalTabBar');
  var filesTabBar = document.getElementById('filesTabBar');
  if (termTabBar) termTabBar.classList.toggle('tab-bar-compressed', compressed);
  if (filesTabBar) filesTabBar.classList.toggle('tab-bar-compressed', compressed);
  // Update toggle button text/title
  [termTabBar, filesTabBar].forEach(function(bar) {
    if (!bar) return;
    var btn = bar.querySelector('.tab-sidebar-toggle');
    if (!btn) return;
    btn.textContent = compressed ? '\u25B6' : '\u25C0';
    btn.title = compressed ? '展开侧边栏' : '压缩侧边栏';
  });
}

// Initialize tab layout from saved config
(async function _initTabLayout() {
  try {
    var saved = await persistLoad('config.json');
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
  var existing = await persistLoad('config.json') || {};
  existing.layout = _tabLayoutConfig.layout;
  existing.sidebarCompressed = _tabLayoutConfig.sidebarCompressed;
  persistSave('config.json', existing);
  toast('标签栏布局: ' + (event.target.value === 'vertical' ? '竖向侧边' : '横向顶部'), 'ok');
});

// CustomDropdown onChange for tabLayoutSelect
(function() {
  var dropdown = window._dropdowns && window._dropdowns['tabLayoutSelect'];
  if (dropdown) {
    dropdown.onChange = async function(value) {
      _tabLayoutConfig.layout = value;
      _applyTabLayout(value);
      var existing = await persistLoad('config.json') || {};
      existing.layout = value;
      existing.sidebarCompressed = _tabLayoutConfig.sidebarCompressed;
      persistSave('config.json', existing);
      toast('标签栏布局: ' + (value === 'vertical' ? '竖向侧边' : '横向顶部'), 'ok');
    };
  }
})();
