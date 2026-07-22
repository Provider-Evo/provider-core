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

/** Merge-patch terminals.json to avoid bg/connection fields clobbering each other. */
async function mergeTerminalsPersist(patch) {
  if (typeof persistSave !== 'function' || typeof persistLoad !== 'function') return;
  var existing = await persistLoad('terminals.json');
  if (!existing || typeof existing !== 'object') existing = {};
  var next = Object.assign({}, existing, patch || {});
  await persistSave('terminals.json', next);
  return next;
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
  if (chatRunTestsBtn && typeof runChatTests === 'function') {
    chatRunTestsBtn.addEventListener('click', runChatTests);
  }
  (async function() {
    if (typeof loadChatState === 'function') await loadChatState();
    if (typeof loadModelsList === 'function') await loadModelsList();
  })();
  if (typeof ChatAttachments !== 'undefined' && ChatAttachments.install) ChatAttachments.install();
  if (typeof _loadTools === 'function') _loadTools();
}

function _initStatsTab() {
  if (typeof StatsFeature !== 'undefined') StatsFeature.init();
  if (typeof RequestInspector !== 'undefined') RequestInspector.init();
}

function _initRequestsTab() {
  _initStatsTab();
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
  var bodyEl = document.getElementById('webuiBody');
  if (bodyEl && _tabLayoutConfig.sidebarCompressed) {
    bodyEl.classList.remove('expanded');
  }
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
