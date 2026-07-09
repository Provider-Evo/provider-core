(function loadWebuiEnhance() {
  fetch('/v1/webui/enhance/info').then(function(r) { return r.ok ? r.json() : null; }).then(function(info) {
    if (!info || !info.enabled || !info.css) return;
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = info.css;
    document.head.appendChild(link);
    document.body.classList.add('webui-enhanced');
  }).catch(function() {});
})();
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
  copyText(JSON.stringify(state.summary || {}, null, 2), t('overview.summaryCopied'));
});
document.getElementById('exportSummaryButton').addEventListener('click', exportSummary);
document.getElementById('copyConfigButton').addEventListener('click', function() {
  var isSource = typeof getConfigEditMode === 'function' && getConfigEditMode() === 'source';
  if (isSource) {
    var editor = document.getElementById('configTomlEditor');
    copyText(editor ? editor.value : '', t('overview.configCopied'));
    return;
  }
  copyText(JSON.stringify(window._currentConfig || {}, null, 2), t('overview.configCopied'));
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
document.getElementById('logSearchInput').addEventListener('input', function() {
  _logSearchQuery = this.value;
  filterLogs();
});
document.getElementById('logRegexBtn').addEventListener('click', function() { toggleLogRegex(); });
// Collapsible advanced filters toggle
document.getElementById('logFilterToggleBtn').addEventListener('click', function() {
  _toggleLogFilters();
});
// Date range filters — CustomDatePicker
window._datePickers = {};
['logDateFrom', 'logDateTo'].forEach(function(id) {
  var el = document.getElementById(id);
  if (el && typeof CustomDatePicker !== 'undefined') {
    window._datePickers[id] = new CustomDatePicker(el, {
      onChange: function(value) {
        if (id === 'logDateFrom') {
          _logDateFrom = value;
          localStorage.setItem('provider.logDateFrom', value);
        } else {
          _logDateTo = value;
          localStorage.setItem('provider.logDateTo', value);
        }
        _updateLogClearDateBtn();
        filterLogs();
      }
    });
  }
});
document.getElementById('logClearDateBtn').addEventListener('click', function() {
  _logDateFrom = '';
  _logDateTo = '';
  localStorage.removeItem('provider.logDateFrom');
  localStorage.removeItem('provider.logDateTo');
  if (window._datePickers.logDateFrom) window._datePickers.logDateFrom.setValue('');
  if (window._datePickers.logDateTo) window._datePickers.logDateTo.setValue('');
  _updateLogClearDateBtn();
  filterLogs();
});
// Initialize auto-scroll button state and restore level filter
(function() {
  var btn = document.getElementById('logAutoScrollBtn');
  if (btn) btn.classList.toggle('active', _logAutoScroll);
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
  if (window._datePickers && window._datePickers.logDateFrom && _logDateFrom) window._datePickers.logDateFrom.setValue(_logDateFrom);
  if (window._datePickers && window._datePickers.logDateTo && _logDateTo) window._datePickers.logDateTo.setValue(_logDateTo);
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
document.querySelectorAll('.tab-button[data-tab]').forEach(function(node) {
  node.id = 'tab-' + node.dataset.tab + '-button';
  node.addEventListener('click', function() {
    switchTab(node.dataset.tab);
  });
});

// Autoupdate & chat initialization moved to lazy per-tab init functions
// (_initAutoupdateTab, _initChatTab) — called by state.js _initTab()

applyTheme();
applyVoiceSettings();

var configTtsRestoreBtn = document.getElementById('configTtsRestoreBtn');
if (configTtsRestoreBtn) {
  configTtsRestoreBtn.addEventListener('click', async function() {
    try {
      var resp = await fetch('/prompts/tts_default.prompt');
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      var text = (await resp.text()).trim();
      if (!window._currentConfig) window._currentConfig = {};
      window._currentConfig.ttsPrompt = text;
      if (typeof _renderConfigData === 'function') _renderConfigData(window._currentConfig);
      if (typeof scheduleConfigSave === 'function') scheduleConfigSave();
      toast(t('actions.promptRestored'), 'ok');
    } catch (e) {
      toast(t('actions.promptRestoreFailedDetail', { error: e.message }), 'error');
    }
  });
}

// ========================= Custom Dropdown Initialization =========================
window._dropdowns = {};
['modelPlatformSelect', 'modelCapabilitySelect', 'chatModelSelect',
 'chatProtocolSelect', 'autoupdateBranch', 'requestStatusFilter', 'requestTimeFilter',
 'logLevelSelect', 'logModuleSelect'].forEach(function(id) {
  var el = document.getElementById(id);
  if (el) {
    window._dropdowns[id] = new CustomDropdown(el);
  }
});

// Log dropdown change handlers
['logLevelSelect', 'logModuleSelect'].forEach(function(id) {
  var dropdown = window._dropdowns && window._dropdowns[id];
  if (dropdown) {
    dropdown.onChange = function(value) {
      if (id === 'logLevelSelect') {
        _logLevelFilter = value;
        localStorage.setItem('provider.logLevelFilter', _logLevelFilter);
      } else if (id === 'logModuleSelect') {
        _logModuleFilter = value;
      }
      filterLogs();
    };
  }
});

// Restore log level and module filters
(function() {
  var levelDropdown = window._dropdowns && window._dropdowns['logLevelSelect'];
  if (levelDropdown) {
    levelDropdown.setValue(_logLevelFilter);
  }
  var moduleDropdown = window._dropdowns && window._dropdowns['logModuleSelect'];
  if (moduleDropdown) {
    moduleDropdown.setValue(_logModuleFilter);
  }
})();

// Re-apply settings after dropdown initialization
applyTheme();
applyCompact();

// Load portable settings from server-side webui_config.toml
initSettingsFromServer();

scheduleRefresh();
if (typeof renderModels === 'function') renderModels([]);
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

// Load voice model lists for STT/TTS dropdowns (populateModelDropdowns in refreshAll)
(async function bootstrapModelDropdowns() {
  if (typeof populateModelDropdowns !== 'function') return;
  if (state.modelsLoaded && state.models.length) {
    populateModelDropdowns(state.models);
    return;
  }
  try {
    var result = await fetchJson('/v1/webui/summary');
    if (result && result.models) populateModelDropdowns(result.models);
    else populateModelDropdowns(null, { error: true });
  } catch (e) {
    populateModelDropdowns(null, { error: true });
  }
})();

// Voice dropdown change handlers removed — voice settings live in config panel (webui_config)

// Tab layout config (persisted via webui_config / config panel)
window._tabLayoutConfig = window._tabLayoutConfig || { layout: 'horizontal', sidebarCompressed: false };
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

// ========================= Lazy Per-Tab Init Functions =========================
// Called by state.js _initTab() the first time each tab is shown.

function _initChatTab() {
  var chatClearBtn = document.getElementById('chatClearBtn');
  var chatRunTestsBtn = document.getElementById('chatRunTestsBtn');
  var chatBatchToggleBtn = document.getElementById('chatBatchToggleBtn');

  if (chatBatchToggleBtn) {
    chatBatchToggleBtn.addEventListener('click', function() {
      var section = document.getElementById('batchTestSection');
      if (section) {
        section.classList.toggle('hidden');
        chatBatchToggleBtn.textContent = section.classList.contains('hidden') ? t('chat.batchTest') : t('chat.collapseBatchTest');
      }
    });
  }

  var initInputBox = function() {
    if (typeof InputBox === 'undefined' || !document.getElementById('chatInputBox')) return;
    if (window._chatInputBox) return;
    var voiceSettings = typeof loadVoiceSettings === 'function' ? loadVoiceSettings() : {};
    window._chatInputBox = InputBox.create('#chatInputBox', {
      placeholder: t('chat.inputPlaceholder'),
      buttons: { file: true, voice: true, send: true },
      voice: voiceSettings,
      onSend: function(text, files) { sendChatMessage(text, files); },
      onVoiceStart: function() { toast(t('chat.recording'), 'info'); },
      onVoiceEnd: function() {},
    });
  };

  if (typeof loadWebUISettings === 'function') {
    loadWebUISettings().then(initInputBox).catch(function() { initInputBox(); });
  } else {
    initInputBox();
  }

  if (chatClearBtn) {
    chatClearBtn.addEventListener('click', function() {
      clearChatMessages();
      toast(t('chat.cleared'), 'ok');
    });
  }
  if (chatRunTestsBtn) {
    chatRunTestsBtn.addEventListener('click', runChatTests);
  }
  if (typeof loadModelsList === 'function') loadModelsList();
  if (typeof ChatAttachments !== 'undefined' && ChatAttachments.install) ChatAttachments.install();
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
      toast(t('stats.resetOk'), 'ok');
      StatsFeature.refresh();
    } catch(e) { toast(t('stats.resetFailed', { error: e.message }), 'error'); }
  });
}

function _initTerminalTab() {
  var localBtn = document.getElementById('terminalEmptyLocalBtn');
  var sshBtn = document.getElementById('terminalEmptySSHBtn');
  if (localBtn) localBtn.addEventListener('click', function() { TerminalManager.createTab('local'); });
  if (sshBtn) sshBtn.addEventListener('click', function() { TerminalManager.showSSHDialog(); });
}

function _initConfigTab() {
  if (typeof activateConfigPanel === 'function') {
    activateConfigPanel(state.summary);
  }
}

function activateConfigPanel(summary) {
  if (typeof _bindConfigPanel === 'function') _bindConfigPanel();
  if (typeof forceRenderConfig === 'function') {
    forceRenderConfig(summary);
  }
}
window.activateConfigPanel = activateConfigPanel;

// ========================= Tab Layout Toggle =========================
var _tabLayoutConfig = window._tabLayoutConfig;

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
window._applyTabLayout = _applyTabLayout;

async function _persistTabLayoutPatch(patch) {
  try {
    var existing = await fetchJson('/v1/webui/config').catch(function() { return {}; });
    Object.assign(existing, patch);
    await fetch('/v1/webui/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(existing),
    });
  } catch (e) { /* ignore */ }
}

// Initialize tab layout from saved config
(async function _initTabLayout() {
  try {
    var saved = await fetchJson('/v1/webui/config');
    if (saved && saved.layout) {
      _tabLayoutConfig.layout = saved.layout;
    }
    if (saved && typeof saved.sidebarCompressed === 'boolean') {
      _tabLayoutConfig.sidebarCompressed = saved.sidebarCompressed;
    }
  } catch (e) { /* ignore */ }
  _applyTabLayout(_tabLayoutConfig.layout);
})();

if (window.i18n) {
  i18n.onLanguageChanged(function() {
    if (typeof applyTheme === 'function') applyTheme();
    if (typeof scheduleRefresh === 'function') scheduleRefresh();
    if (typeof updateConfigSaveStatus === 'function') updateConfigSaveStatus();
    if (typeof _restartSetState === 'function' && typeof _restartState !== 'undefined' && _restartState !== 'idle') {
      _restartSetState(_restartState);
    }
    if (typeof _updateLogCount === 'function') _updateLogCount();
  });
}

