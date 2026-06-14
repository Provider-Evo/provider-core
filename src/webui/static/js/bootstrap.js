document.getElementById('refreshButton').addEventListener('click', refreshAll);
document.getElementById('refreshModelsButton').addEventListener('click', refreshModels);
document.getElementById('fabThemeButton').addEventListener('click', function() {
  const order = ['auto', 'light', 'dark'];
  const index = order.indexOf(state.settings.theme);
  state.settings.theme = order[(index + 1) % order.length];
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
  logBox.textContent = '';
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
 'chatProtocolSelect', 'themeSelect', 'compactSelect'].forEach(function(id) {
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

// Restore chat history from localStorage
if (typeof loadChatState === 'function') {
  loadChatState();
}

// Override switchTab to add animation when switching tabs
var originalSwitchTab = window.switchTab;
if (typeof switchTab === 'function') {
  window.switchTab = function(tabName) {
    originalSwitchTab(tabName);
    // Smooth scroll to top to avoid scrollbar jump when switching between tabs of different heights
    var scrollTarget = document.scrollingElement || document.documentElement;
    var startY = scrollTarget.scrollTop;
    if (startY > 10) {
      var startTime = null;
      var duration = 300;
      function step(ts) {
        if (!startTime) startTime = ts;
        var progress = Math.min((ts - startTime) / duration, 1);
        var ease = 1 - Math.pow(1 - progress, 3); // easeOutCubic
        scrollTarget.scrollTop = startY * (1 - ease);
        if (progress < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }
    // Animate the newly shown tab panel
    var activePanel = document.querySelector('.tab-panel.active');
    if (activePanel && typeof animateTabIn === 'function') {
      setTimeout(function() { animateTabIn(activePanel); }, 50);
    }
  };
}
