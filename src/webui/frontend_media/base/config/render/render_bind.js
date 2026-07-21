// ========================= Config panel binding & DOM sync =========================
// 拆分自 render.js。依赖 render_state.js / render_main.js（switch* 函数）。

function _bindConfigPanel() {
  if (window._configPanelBound) return;
  window._configPanelBound = true;
  _syncConfigTargetUI(getConfigTarget());
  _syncConfigModeUI(getConfigEditMode());
  _bindConfigPanelSwitchers();
  _bindConfigPanelActions();
}

/**
 * Bind target switcher, mode switcher, and section tabs. Split out of
 * _bindConfigPanel to keep it under the line cap.
 */
function _bindConfigPanelSwitchers() {
  var switcher = document.getElementById('configTargetSwitch');
  if (switcher) {
    switcher.addEventListener('click', function(e) {
      var btn = e.target.closest('.config-target-btn[data-target]');
      if (!btn) return;
      switchConfigTarget(btn.getAttribute('data-target'));
    });
  }
  var select = document.getElementById('configTargetSelect');
  if (select) {
    select.addEventListener('change', function() {
      switchConfigTarget(select.value);
    });
    var dd = window._dropdowns && window._dropdowns['configTargetSelect'];
    if (dd) {
      dd.onChange = function(value) {
        switchConfigTarget(value);
      };
    }
  }
  var modeSwitch = document.getElementById('configModeSwitch');
  if (modeSwitch) {
    modeSwitch.addEventListener('click', function(e) {
      var btn = e.target.closest('.config-mode-btn[data-mode]');
      if (!btn) return;
      switchConfigEditMode(btn.getAttribute('data-mode'));
    });
  }
  var sectionTabs = document.getElementById('configSectionTabs');
  if (sectionTabs) {
    sectionTabs.addEventListener('click', function(e) {
      var btn = e.target.closest('.config-section-tab[data-section]');
      if (!btn) return;
      switchConfigSection(btn.getAttribute('data-section'));
    });
  }
}

/**
 * Bind refresh/save/notice-dismiss buttons and the raw-TOML editor input
 * listener. Split out of _bindConfigPanel to keep it under the line cap.
 */
function _bindConfigPanelActions() {
  var refreshBtn = document.getElementById('configRefreshBtn');
  if (refreshBtn) {
    refreshBtn.addEventListener('click', function() {
      if (typeof reloadConfigFromFile === 'function') reloadConfigFromFile();
    });
  }
  var saveBtn = document.getElementById('configSaveBtn');
  if (saveBtn) {
    saveBtn.addEventListener('click', function() {
      if (typeof saveConfig === 'function') saveConfig();
    });
  }
  var noticeDismiss = document.getElementById('configSourceNoticeDismiss');
  if (noticeDismiss) {
    noticeDismiss.addEventListener('click', function() {
      _configSourceNoticeDismissed = true;
      localStorage.setItem('provider.configSourceNoticeDismissed', 'true');
      var notice = document.getElementById('configSourceNotice');
      if (notice) notice.classList.add('hidden');
    });
  }
  var tomlEditor = document.getElementById('configTomlEditor');
  if (tomlEditor) {
    tomlEditor.addEventListener('input', function() {
      state.configDirty = true;
      var errEl = document.getElementById('configTomlError');
      if (errEl) errEl.classList.add('hidden');
      updateConfigSaveStatus();
      _updateConfigSaveBtn();
      scheduleConfigSave();
    });
  }
}

function _updateConfigPreview() {
  /* JSON preview removed in Provider-V2-style panel */
}

function _syncListFromContainer(container) {
  if (!container || !window._currentConfig) return;
  var section = container.dataset.section;
  var key = container.dataset.key;
  if (!section || !key) return;
  var inputs = container.querySelectorAll('.config-list-input');
  var list = [];
  inputs.forEach(function(inp) { list.push(inp.value); });
  _configSetValue(window._currentConfig, section, key, list);
}

function _syncConfigFromDOM() {
  if (!configGrid || !window._currentConfig) return;
  configGrid.querySelectorAll('.config-list').forEach(_syncListFromContainer);
  configGrid.querySelectorAll('.config-mapping').forEach(function(container) {
    var section = container.dataset.section;
    var key = container.dataset.key;
    if (!section || !key) return;
    _configSetValue(window._currentConfig, section, key, _collectMapping(container));
  });
  _updateConfigPreview();
}

/**
 * Collect key-value pairs from a mapping editor container.
 */
function _collectMapping(container) {
  var mapping = {};
  var rows = container.querySelectorAll('.config-mapping-row');
  rows.forEach(function(row) {
    var k = row.querySelector('.config-mapping-key');
    var v = row.querySelector('.config-mapping-val');
    if (k && k.value) mapping[k.value] = v ? v.value : '';
  });
  return mapping;
}

function _onConfigChange(e) {
  var el = e.target;
  var section = el.dataset.section;
  var key = el.dataset.key;
  var type = el.dataset.type;
  if (!section || !key || !type) return;

  var val;
  if (type === 'boolean') {
    val = el.checked;
  } else if (type === 'number') {
    val = parseInt(el.value, 10) || 0;
  } else if (type === 'json') {
    try { val = JSON.parse(el.value); } catch(err) { return; }
  } else if (type === 'list') {
    // List items are handled by add/remove buttons
    return;
  } else {
    val = el.value;
  }

  _configSetValue(window._currentConfig, section, key, val);
  _onWebuiConfigFieldChange(key, val);
  scheduleConfigSave();
}

window._bindConfigPanel = _bindConfigPanel;
window._syncConfigFromDOM = _syncConfigFromDOM;
