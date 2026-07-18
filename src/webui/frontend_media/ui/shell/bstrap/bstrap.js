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
      var text = typeof i18n !== 'undefined' && i18n.fetchPromptTemplate
        ? await i18n.fetchPromptTemplate('tts_default')
        : (await (await fetch('/prompts/zh-CN/tts_default.prompt')).text()).trim();
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
if (typeof UiDropdown !== 'undefined') {
  UiDropdown.mount(document, window._dropdowns);
} else {
  ['modelPlatformSelect', 'modelCapabilitySelect', 'chatModelSelect',
   'chatProtocolSelect', 'autoupdateBranch', 'requestStatusFilter', 'requestTimeFilter',
   'logLevelSelect', 'logModuleSelect'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) window._dropdowns[id] = new CustomDropdown(el);
  });
}

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
if (typeof WebuiShell !== 'undefined') WebuiShell.bind();
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
