// ========================= Main Render: tabs / mode / target switching =========================
// 拆分自 render.js。依赖 render_state.js（target/mode 存取）与 render_schema.js（schema 结构函数）。

function _updateConfigSubtitle() {
  var subtitle = document.getElementById('configSubtitle');
  var restoreBtn = document.getElementById('configTtsRestoreBtn');
  var isWebui = _isFlatConfigTarget();
  if (subtitle) {
    subtitle.textContent = isWebui
      ? (typeof t === 'function' ? t('config.subtitleWebui') : '编辑 config/webui_config.toml，仅影响 WebUI 界面与客户端行为。')
      : (typeof t === 'function' ? t('config.subtitleMain') : '编辑 config/main_config.toml，修改后自动保存并热重载。');
  }
  if (restoreBtn) restoreBtn.classList.toggle('hidden', !isWebui);
}

function _collectSectionTabs(schema, config) {
  var tabs = [];
  var sections = (schema && schema.sections) || [];
  for (var i = 0; i < sections.length; i++) {
    tabs.push({ id: sections[i].id, title: sections[i].title || sections[i].id });
  }
  if (!schema || !schema.flat) {
    var known = _knownSchemaSectionIds(schema || { sections: [] });
    Object.keys(config || {}).forEach(function(key) {
      if (known.indexOf(key) !== -1) return;
      if (config[key] != null && typeof config[key] === 'object' && !Array.isArray(config[key])) {
        tabs.push({ id: key, title: key });
      }
    });
  }
  return tabs;
}

function _ensureActiveSection(schema, config) {
  var tabs = _collectSectionTabs(schema, config);
  if (!tabs.length) {
    _activeConfigSection = null;
    return tabs;
  }
  var hasActive = false;
  for (var i = 0; i < tabs.length; i++) {
    if (tabs[i].id === _activeConfigSection) {
      hasActive = true;
      break;
    }
  }
  if (!hasActive) _activeConfigSection = tabs[0].id;
  return tabs;
}

function _renderSectionTabs(schema, config) {
  var tabsEl = document.getElementById('configSectionTabs');
  if (!tabsEl) return;
  var tabs = _ensureActiveSection(schema, config);
  if (tabs.length <= 1) {
    tabsEl.classList.add('hidden');
    tabsEl.innerHTML = '';
    return;
  }
  tabsEl.classList.remove('hidden');
  var html = '';
  for (var i = 0; i < tabs.length; i++) {
    var tab = tabs[i];
    html += '<button type="button" class="config-section-tab'
      + (tab.id === _activeConfigSection ? ' active' : '')
      + '" data-section="' + escapeHtml(tab.id) + '" role="tab"'
      + (tab.id === _activeConfigSection ? ' aria-selected="true"' : ' aria-selected="false"')
      + '>[' + escapeHtml(tab.title) + ']</button>';
  }
  tabsEl.innerHTML = html;
}

function switchConfigSection(sectionId) {
  if (!sectionId || sectionId === _activeConfigSection) return;
  if (typeof _syncConfigFromDOM === 'function') _syncConfigFromDOM();
  _activeConfigSection = sectionId;
  if (window._currentConfig) _renderConfigData(window._currentConfig);
}

function _syncConfigModeUI(mode) {
  var switcher = document.getElementById('configModeSwitch');
  if (switcher) {
    switcher.querySelectorAll('.config-mode-btn').forEach(function(btn) {
      btn.classList.toggle('active', btn.getAttribute('data-mode') === mode);
    });
  }
  var visualPane = document.getElementById('configVisualPane');
  var sourcePane = document.getElementById('configSourcePane');
  if (visualPane) visualPane.classList.toggle('hidden', mode === 'source');
  if (sourcePane) sourcePane.classList.toggle('hidden', mode !== 'source');
  var notice = document.getElementById('configSourceNotice');
  if (notice) notice.classList.toggle('hidden', _configSourceNoticeDismissed || mode !== 'source');
}

function _loadConfigRaw() {
  var url = _isFlatConfigTarget() ? '/v1/webui/config/raw' : '/v1/config/raw';
  var editor = document.getElementById('configTomlEditor');
  if (editor) {
    editor.value = typeof t === 'function' ? t('common.loading') : '加载中...';
  }
  return fetchJson(url).then(function(result) {
    if (editor) editor.value = (result && result.content) || '';
    var errEl = document.getElementById('configTomlError');
    if (errEl) errEl.classList.add('hidden');
    state.configDirty = false;
    if (typeof updateConfigSaveStatus === 'function') updateConfigSaveStatus();
    _updateConfigSaveBtn();
  }).catch(function(err) {
    if (editor) editor.value = '';
    var errEl = document.getElementById('configTomlError');
    if (errEl) {
      errEl.textContent = String(err && err.message ? err.message : err);
      errEl.classList.remove('hidden');
    }
    if (typeof toast === 'function') {
      toast(typeof t === 'function' ? t('config.rawLoadFailed', { error: String(err) }) : String(err), 'error');
    }
  });
}

function switchConfigEditMode(mode) {
  if (mode !== 'visual' && mode !== 'source') return;
  if (mode === getConfigEditMode()) return;
  if (mode === 'visual' && typeof _syncConfigFromDOM === 'function') {
    _syncConfigFromDOM();
  }
  setConfigEditMode(mode);
  _syncConfigModeUI(mode);
  if (mode === 'source') {
    _loadConfigRaw();
    return;
  }
  forceRenderConfig(state.summary);
}

function _updateConfigSaveBtn() {
  var btn = document.getElementById('configSaveBtn');
  if (!btn) return;
  btn.disabled = !state.configDirty;
  btn.title = state.configDirty
    ? (typeof t === 'function' ? t('config.save') : '保存')
    : (typeof t === 'function' ? t('common.saved') : '已保存');
}

function renderConfig(summary) {
  if (getConfigEditMode() === 'source') return;
  if (state.configDirty) return;
  if (Date.now() - _lastConfigSaveTime < 5000) return;

  _updateConfigSubtitle();
  var configUrl = _isFlatConfigTarget() ? '/v1/webui/config' : '/v1/config';
  Promise.all([
    fetchJson(configUrl),
    _ensureConfigSchema(),
  ]).then(function(results) {
    _activeConfigSchema = results[1];
    _renderConfigData(results[0]);
    if (_isFlatConfigTarget()) _applyWebuiRuntime(results[0]);
  }).catch(function() {
    _renderConfigData((summary && summary.config) || {});
  });
}

function _syncConfigTargetUI(target) {
  var switcher = document.getElementById('configTargetSwitch');
  if (switcher) {
    switcher.querySelectorAll('.config-target-btn').forEach(function(btn) {
      btn.classList.toggle('active', btn.getAttribute('data-target') === target);
    });
  }
  var select = document.getElementById('configTargetSelect');
  if (select) select.value = target;
  var dd = window._dropdowns && window._dropdowns['configTargetSelect'];
  if (dd && typeof dd.setValue === 'function') dd.setValue(target);
  _updateConfigSubtitle();
}

function switchConfigTarget(target) {
  if (target !== 'main' && target !== 'webui') return;
  setConfigTarget(target);
  state.configDirty = false;
  _lastConfigSaveTime = 0;
  _activeConfigSchema = null;
  _activeConfigSection = null;
  _syncConfigTargetUI(target);
  if (getConfigEditMode() === 'source') {
    _loadConfigRaw();
    return;
  }
  forceRenderConfig(state.summary);
}

function forceRenderConfig(summary) {
  _updateConfigSubtitle();
  _syncConfigModeUI(getConfigEditMode());
  if (getConfigEditMode() === 'source') {
    _loadConfigRaw();
    return;
  }
  var configUrl = _isFlatConfigTarget() ? '/v1/webui/config' : '/v1/config';
  var schemaUrl = _isFlatConfigTarget() ? '/v1/admin/webui/config/schema' : '/v1/admin/config/schema';
  if (configGrid) {
    configGrid.innerHTML = '<div class="text-muted text-sm p-3">' + escapeHtml(typeof t === 'function' ? t('common.loading') : '加载中...') + '</div>';
  }
  Promise.all([
    fetchJson(configUrl).catch(function() { return (summary && summary.config) || {}; }),
    fetchJson(schemaUrl).catch(function() { return { sections: [] }; }),
  ]).then(function(results) {
    if (_isFlatConfigTarget()) {
      _webuiConfigPanelSchema = results[1];
    } else {
      _configPanelSchema = results[1];
    }
    _activeConfigSchema = results[1];
    state.configDirty = false;
    _renderConfigData(results[0] || {});
    if (_isFlatConfigTarget()) _applyWebuiRuntime(results[0] || {});
    updateConfigSaveStatus();
    _updateConfigSaveBtn();
  });
}

window.getConfigTarget = getConfigTarget;
window.setConfigTarget = setConfigTarget;
window.getConfigEditMode = getConfigEditMode;
window.setConfigEditMode = setConfigEditMode;
window.switchConfigTarget = switchConfigTarget;
window.switchConfigEditMode = switchConfigEditMode;
window.switchConfigSection = switchConfigSection;
window.forceRenderConfig = forceRenderConfig;
window.renderConfig = renderConfig;
window._updateConfigSubtitle = _updateConfigSubtitle;
window._updateConfigSaveBtn = _updateConfigSaveBtn;
window._loadConfigRaw = _loadConfigRaw;
