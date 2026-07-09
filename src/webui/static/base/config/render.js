// ========================= Config Component System =========================

/**
 * Render a boolean toggle component.
 */
function _renderToggle(section, key, val) {
  var id = 'cfg-' + section + '-' + key;
  return '<label class="config-toggle">'
    + '<input type="checkbox" id="' + id + '" data-section="' + section + '" data-key="' + key + '" data-type="boolean"'
    + (val ? ' checked' : '') + '>'
    + '<span class="toggle-slider"></span></label>';
}

/**
 * Render a number input component.
 */
function _renderNumber(section, key, val, field) {
  var id = 'cfg-' + section + '-' + key;
  var attrs = '';
  if (field && field.min != null) attrs += ' min="' + field.min + '"';
  if (field && field.max != null) attrs += ' max="' + field.max + '"';
  return '<input type="number" class="config-input" id="' + id
    + '" data-section="' + section + '" data-key="' + key + '" data-type="number"'
    + attrs + ' value="' + val + '">';
}

/**
 * Render a text input component.
 */
function _renderText(section, key, val) {
  var id = 'cfg-' + section + '-' + key;
  return '<input type="text" class="config-input" id="' + id
    + '" data-section="' + section + '" data-key="' + key + '" data-type="string"'
    + ' value="' + escapeHtml(String(val)) + '">';
}

/**
 * Render a readonly text display.
 */
function _renderReadonly(section, key, val) {
  return '<span class="config-readonly">' + escapeHtml(String(val)) + '</span>';
}

/**
 * Render a select dropdown component.
 */
function _renderSelect(section, key, val, options) {
  var id = 'cfg-' + section + '-' + key;
  var html = '<select class="config-input" id="' + id
    + '" data-section="' + section + '" data-key="' + key + '" data-type="string">';
  for (var i = 0; i < options.length; i++) {
    var opt = options[i];
    html += '<option value="' + escapeHtml(opt) + '"'
      + (opt === val ? ' selected' : '') + '>' + escapeHtml(opt) + '</option>';
  }
  html += '</select>';
  return html;
}

/**
 * Render a string list editor component (add/remove items).
 */
function _renderStringList(section, key, val) {
  var id = 'cfg-' + section + '-' + key;
  var items = Array.isArray(val) ? val : [];
  var html = '<div class="config-list" id="' + id + '" data-section="' + section + '" data-key="' + key + '" data-type="list">';
  for (var i = 0; i < items.length; i++) {
    html += '<div class="config-list-item">'
      + '<input type="text" class="config-input config-list-input" value="' + escapeHtml(items[i]) + '">'
      + '<button type="button" class="config-list-remove" data-index="' + i + '">&times;</button>'
      + '</div>';
  }
  html += '<button type="button" class="config-list-add" data-section="' + section + '" data-key="' + key + '">+ 添加</button>';
  html += '</div>';
  return html;
}

/**
 * Render a raw JSON textarea for unknown/complex fields.
 */
function _renderRawJson(section, key, val) {
  var id = 'cfg-' + section + '-' + key;
  var text = '';
  try { text = JSON.stringify(val, null, 2); } catch(e) { text = '{}'; }
  return '<textarea class="config-json" id="' + id
    + '" data-section="' + section + '" data-key="' + key + '" data-type="json"'
    + ' rows="' + Math.max(2, Math.min(8, text.split('\n').length)) + '">'
    + escapeHtml(text) + '</textarea>';
}

/**
 * Render a multiline text field.
 */
function _renderTextarea(section, key, val) {
  var id = 'cfg-' + section + '-' + key;
  var text = val != null ? String(val) : '';
  return '<textarea class="config-json" id="' + id
    + '" data-section="' + section + '" data-key="' + key + '" data-type="string"'
    + ' rows="' + Math.max(2, Math.min(6, text.split('\n').length + 1)) + '">'
    + escapeHtml(text) + '</textarea>';
}

/**
 * Render a key-value mapping editor component.
 * Each entry is a row: [key input] → [value input] [× remove]
 * Plus an "add" button at the bottom.
 */
function _renderMappingEditor(section, key, val) {
  var id = 'cfg-' + section + '-' + key;
  var entries = [];
  if (val && typeof val === 'object' && !Array.isArray(val)) {
    var keys = Object.keys(val);
    for (var i = 0; i < keys.length; i++) {
      entries.push({ k: keys[i], v: String(val[keys[i]]) });
    }
  }
  var html = '<div class="config-mapping" id="' + id + '" data-section="' + section + '" data-key="' + key + '" data-type="mapping">';
  for (var j = 0; j < entries.length; j++) {
    html += '<div class="config-mapping-row">'
      + '<input type="text" class="config-input config-mapping-key" value="' + escapeHtml(entries[j].k) + '" placeholder="key">'
      + '<span class="config-mapping-arrow">→</span>'
      + '<input type="text" class="config-input config-mapping-val" value="' + escapeHtml(entries[j].v) + '" placeholder="value">'
      + '<button type="button" class="config-mapping-remove" data-index="' + j + '">&times;</button>'
      + '</div>';
  }
  html += '<button type="button" class="config-list-add config-mapping-add" data-section="' + section + '" data-key="' + key + '">+ 添加映射</button>';
  html += '</div>';
  return html;
}

/**
 * Build a field row: label + control (side by side).
 */
function _field(label, control) {
  return '<div class="config-field">'
    + '<span class="config-field-label">' + escapeHtml(label) + '</span>'
    + control + '</div>';
}

/**
 * Build a full-width field block: label on top, control below (for lists/JSON).
 */
function _fieldBlock(label, control) {
  return '<div class="config-field-block">'
    + '<div class="config-field-label" style="margin-bottom:4px;">' + escapeHtml(label) + '</div>'
    + control + '</div>';
}

/**
 * Build a section card with title and fields.
 */
function _sectionCard(title, fieldsHtml) {
  return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">'
    + '<div class="text-[13px] text-muted m-0 mb-2 font-semibold">[' + escapeHtml(title) + ']</div>'
    + fieldsHtml + '</div>';
}

// ========================= Schema-driven rendering =========================

var _configPanelSchema = null;
var _webuiConfigPanelSchema = null;
var _activeConfigSchema = null;
var _lastConfigSaveTime = 0;
var _activeConfigSection = null;
var _configSourceNoticeDismissed = localStorage.getItem('provider.configSourceNoticeDismissed') === 'true';

function getConfigEditMode() {
  var mode = window._configEditMode || localStorage.getItem('provider.configEditMode') || 'visual';
  return mode === 'source' ? 'source' : 'visual';
}

function setConfigEditMode(mode) {
  window._configEditMode = mode;
  localStorage.setItem('provider.configEditMode', mode);
}

function getConfigTarget() {
  return window._configTarget || localStorage.getItem('provider.configTarget') || 'main';
}

function setConfigTarget(target) {
  window._configTarget = target;
  localStorage.setItem('provider.configTarget', target);
}

function _isFlatConfigTarget() {
  return getConfigTarget() === 'webui';
}

function _configSetValue(config, section, key, val) {
  if (_isFlatConfigTarget() || section === '_root') {
    config[key] = val;
    return;
  }
  if (!config[section]) config[section] = {};
  config[section][key] = val;
}

function _configGetValue(config, section, key) {
  if (_isFlatConfigTarget() || section === '_root') {
    return config[key];
  }
  return config[section] && config[section][key];
}

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

function _ensureConfigSchema() {
  var target = getConfigTarget();
  if (target === 'webui') {
    if (_webuiConfigPanelSchema) return Promise.resolve(_webuiConfigPanelSchema);
    return fetchJson('/v1/admin/webui/config/schema').then(function(schema) {
      _webuiConfigPanelSchema = schema || { sections: [], flat: true };
      return _webuiConfigPanelSchema;
    }).catch(function() {
      _webuiConfigPanelSchema = { sections: [], flat: true };
      return _webuiConfigPanelSchema;
    });
  }
  if (_configPanelSchema) return Promise.resolve(_configPanelSchema);
  return fetchJson('/v1/admin/config/schema').then(function(schema) {
    _configPanelSchema = schema || { sections: [] };
    return _configPanelSchema;
  }).catch(function() {
    _configPanelSchema = { sections: [] };
    return _configPanelSchema;
  });
}

function _defaultForField(field) {
  if (field.type === 'boolean') return false;
  if (field.type === 'number') return field.min != null ? field.min : 0;
  if (field.type === 'list') return [];
  if (field.type === 'mapping' || field.type === 'json') return {};
  return '';
}

function _renderFieldControl(sectionId, field, val) {
  var key = field.key;
  var type = field.type;
  if (type === 'readonly') return _renderReadonly(sectionId, key, val);
  if (type === 'boolean') return _renderToggle(sectionId, key, !!val);
  if (type === 'number') return _renderNumber(sectionId, key, val != null ? val : _defaultForField(field), field);
  if (type === 'select') return _renderSelect(sectionId, key, val || (field.options && field.options[0]) || '', field.options || []);
  if (type === 'list') return _renderStringList(sectionId, key, Array.isArray(val) ? val : []);
  if (type === 'mapping') return _renderMappingEditor(sectionId, key, val || {});
  if (type === 'json') return _renderRawJson(sectionId, key, val != null ? val : {});
  if (type === 'textarea') return _renderTextarea(sectionId, key, val != null ? val : '');
  return _renderText(sectionId, key, val != null ? val : '');
}

function _renderFieldFromSchema(sectionId, field, sectionData) {
  var val = sectionData && Object.prototype.hasOwnProperty.call(sectionData, field.key)
    ? sectionData[field.key]
    : _defaultForField(field);
  var control = _renderFieldControl(sectionId, field, val);
  var label = field.label || field.key;
  var blockTypes = { list: 1, mapping: 1, json: 1, textarea: 1 };
  if (field.wide || blockTypes[field.type]) return _fieldBlock(label, control);
  return _field(label, control);
}

function _renderSectionFromSchema(sectionDef, config, schema) {
  var sectionId = sectionDef.id;
  var sectionData = (schema && schema.flat) || sectionId === '_root'
    ? config
    : (config[sectionId] || {});
  var fieldsHtml = '';
  var fields = sectionDef.fields || [];
  var knownFieldKeys = [];
  for (var i = 0; i < fields.length; i++) {
    knownFieldKeys.push(fields[i].key);
    fieldsHtml += _renderFieldFromSchema(sectionId, fields[i], sectionData);
  }
  if (!schema.flat && sectionData && typeof sectionData === 'object') {
    Object.keys(sectionData).forEach(function(key) {
      if (knownFieldKeys.indexOf(key) !== -1) return;
      var extra = sectionData[key];
      if (extra != null && typeof extra === 'object') {
        fieldsHtml += _fieldBlock(key, _renderRawJson(sectionId, key, extra));
      } else {
        fieldsHtml += _field(key, _renderText(sectionId, key, extra != null ? extra : ''));
      }
    });
  }
  return _sectionCard(sectionDef.title || sectionId, fieldsHtml);
}

function _knownSchemaSectionIds(schema) {
  var ids = [];
  var sections = (schema && schema.sections) || [];
  for (var i = 0; i < sections.length; i++) ids.push(sections[i].id);
  return ids;
}

// ========================= Main Render =========================

function _knownSchemaFieldKeys(schema) {
  var keys = [];
  var sections = (schema && schema.sections) || [];
  for (var i = 0; i < sections.length; i++) {
    var fields = sections[i].fields || [];
    for (var j = 0; j < fields.length; j++) keys.push(fields[j].key);
  }
  return keys;
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

function _bindConfigPanel() {
  if (window._configPanelBound) return;
  window._configPanelBound = true;
  _syncConfigTargetUI(getConfigTarget());
  _syncConfigModeUI(getConfigEditMode());
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
  /* JSON preview removed in MaiBot-style panel */
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

function _findSectionDef(schema, sectionId) {
  var sections = (schema && schema.sections) || [];
  for (var i = 0; i < sections.length; i++) {
    if (sections[i].id === sectionId) return sections[i];
  }
  return null;
}

function _renderConfigData(config) {
  window._currentConfig = config;

  var schema = _activeConfigSchema || (_isFlatConfigTarget() ? _webuiConfigPanelSchema : _configPanelSchema) || { sections: [] };
  _renderSectionTabs(schema, config);

  var html = '';
  var activeId = _activeConfigSection;
  var sectionDef = activeId ? _findSectionDef(schema, activeId) : null;

  if (sectionDef) {
    html = _renderSectionFromSchema(sectionDef, config, schema);
    if (schema.flat) {
      var knownKeys = _knownSchemaFieldKeys(schema);
      var extraHtml = '';
      Object.keys(config).forEach(function(key) {
        if (knownKeys.indexOf(key) !== -1) return;
        var rawVal = config[key];
        if (rawVal != null && typeof rawVal === 'object') {
          extraHtml += _fieldBlock(key, _renderRawJson('_extra', key, rawVal));
        } else {
          extraHtml += _field(key, _renderText('_extra', key, rawVal != null ? rawVal : ''));
        }
      });
      if (extraHtml) html += _sectionCard('(extra)', extraHtml);
    }
  } else if (activeId && !schema.flat && config[activeId] && typeof config[activeId] === 'object') {
    html = _sectionCard(activeId, _fieldBlock('(raw)', _renderRawJson(activeId, '_raw', config[activeId])));
  } else if (schema.flat) {
    var knownKeys = _knownSchemaFieldKeys(schema);
    Object.keys(config).forEach(function(key) {
      if (knownKeys.indexOf(key) === -1) {
        var rawVal = config[key];
        if (rawVal != null && typeof rawVal === 'object') {
          html += _sectionCard(key, _fieldBlock('(raw)', _renderRawJson('_extra', key, rawVal)));
        } else {
          html += _sectionCard(key, _fieldBlock('(raw)', _renderText('_extra', key, rawVal != null ? rawVal : '')));
        }
      }
    });
    if (!html && (schema.sections || []).length) {
      html = _renderSectionFromSchema(schema.sections[0], config, schema);
    }
  }

  if (!html) {
    html = '<div class="text-muted text-sm p-3">' + escapeHtml(typeof t === 'function' ? t('config.noSection') : '无配置节') + '</div>';
  }

  if (!configGrid) return;
  configGrid.innerHTML = html;

  if (_isFlatConfigTarget()) {
    _enrichWebuiWidgets(config);
  }

  // Convert native <select> elements to CustomDropdown for consistent UI
  if (typeof CustomDropdown !== 'undefined') {
    var configSelects = configGrid.querySelectorAll('select.config-input');
    for (var si = 0; si < configSelects.length; si++) {
      var sel = configSelects[si];
      if (sel.getAttribute('data-dynamic') === 'true') continue;
      if (sel.classList.contains('custom-dropdown') || sel._customDropdown) continue;
      var dd = new CustomDropdown(sel, {
        onChange: function(value) {
          var wrapper = this.el || this;
          var section = wrapper.getAttribute('data-section') || wrapper._section;
          var key = wrapper.getAttribute('data-key') || wrapper._key;
          if (!section || !key) return;
          _configSetValue(window._currentConfig, section, key, value);
          _onWebuiConfigFieldChange(key, value);
          scheduleConfigSave();
        }
      });
      // Store section/key on the dropdown wrapper for the onChange handler
      if (dd && dd.el) {
        dd.el._section = sel.getAttribute('data-section');
        dd.el._key = sel.getAttribute('data-key');
        // Also copy data attributes to the wrapper for event delegation
        dd.el.setAttribute('data-section', sel.getAttribute('data-section') || '');
        dd.el.setAttribute('data-key', sel.getAttribute('data-key') || '');
        dd.el.setAttribute('data-type', sel.getAttribute('data-type') || 'string');
      }
    }
  }

  // Bind events only once (survives re-renders since delegation is on configGrid)
  if (!configGrid._eventsBound) {
    configGrid._eventsBound = true;
    configGrid.addEventListener('change', _onConfigChange);
    configGrid.addEventListener('input', function(e) {
      if (e.target.tagName === 'TEXTAREA') {
        _onConfigChange(e);
        return;
      }
      if (e.target.classList.contains('config-list-input')) {
        _syncListFromContainer(e.target.closest('.config-list'));
        _updateConfigPreview();
        scheduleConfigSave();
      }
    });
  }

  // Bind list add/remove buttons
  configGrid.querySelectorAll('.config-list-add').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var section = this.dataset.section;
      var key = this.dataset.key;
      var list = _configGetValue(window._currentConfig, section, key) || [];
      list = Array.isArray(list) ? list.slice() : [];
      list.push('');
      _configSetValue(window._currentConfig, section, key, list);
      _renderConfigData(window._currentConfig);
    });
  });
  configGrid.querySelectorAll('.config-list-remove').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var container = this.closest('.config-list');
      var section = container.dataset.section;
      var key = container.dataset.key;
      var idx = parseInt(this.dataset.index);
      // Collect current values from inputs
      var inputs = container.querySelectorAll('.config-list-input');
      var list = [];
      inputs.forEach(function(inp) { list.push(inp.value); });
      list.splice(idx, 1);
      _configSetValue(window._currentConfig, section, key, list);
      _renderConfigData(window._currentConfig);
    });
  });

  configGrid.querySelectorAll('.config-mapping-add').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var section = this.dataset.section;
      var key = this.dataset.key;
      var mapping = _collectMapping(this.closest('.config-mapping'));
      mapping[''] = '';  // add empty entry
      _configSetValue(window._currentConfig, section, key, mapping);
      _renderConfigData(window._currentConfig);
    });
  });
  configGrid.querySelectorAll('.config-mapping-remove').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var container = this.closest('.config-mapping');
      var section = container.dataset.section;
      var key = container.dataset.key;
      var idx = parseInt(this.dataset.index);
      var mapping = _collectMapping(container);
      var keys = Object.keys(mapping);
      delete mapping[keys[idx]];
      _configSetValue(window._currentConfig, section, key, mapping);
      _renderConfigData(window._currentConfig);
    });
  });
  configGrid.querySelectorAll('.config-mapping-key, .config-mapping-val').forEach(function(inp) {
    inp.addEventListener('change', function() {
      var container = this.closest('.config-mapping');
      var section = container.dataset.section;
      var key = container.dataset.key;
      var mapping = _collectMapping(container);
      _configSetValue(window._currentConfig, section, key, mapping);
      scheduleConfigSave();
    });
  });

  updateConfigSaveStatus();
  _updateConfigSaveBtn();
}

function _applyWebuiRuntime(config) {
  if (!config || typeof config !== 'object') return;
  if (config.theme) state.settings.theme = config.theme;
  if (typeof config.refreshInterval === 'number') state.settings.refreshInterval = config.refreshInterval;
  if (typeof config.timeoutMs === 'number') state.settings.timeoutMs = config.timeoutMs;
  if (typeof config.streamIdleTimeoutMs === 'number') state.settings.streamIdleTimeoutMs = config.streamIdleTimeoutMs;
  if (config.compact != null) state.settings.compact = String(config.compact);
  localStorage.setItem('provider.webui.settings', JSON.stringify(state.settings));
  if (typeof applyTheme === 'function') applyTheme();
  if (typeof applyCompact === 'function') applyCompact();
  if (typeof scheduleRefresh === 'function') scheduleRefresh();
  if (typeof window._tabLayoutConfig !== 'undefined') {
    if (config.layout) window._tabLayoutConfig.layout = config.layout;
    if (typeof config.sidebarCompressed === 'boolean') {
      window._tabLayoutConfig.sidebarCompressed = config.sidebarCompressed;
    }
    if (typeof window._applyTabLayout === 'function') {
      window._applyTabLayout(window._tabLayoutConfig.layout);
    }
  }
  if (typeof saveVoiceSettings === 'function') {
    saveVoiceSettings({
      sttModel: config.sttModel || '',
      ttsModel: config.ttsModel || '',
      ttsPrompt: config.ttsPrompt || '',
    });
  }
  if (typeof applyVoiceSettings === 'function') applyVoiceSettings();
}

function _onWebuiConfigFieldChange(key, val) {
  if (!_isFlatConfigTarget()) return;
  var patch = {};
  patch[key] = val;
  _applyWebuiRuntime(Object.assign({}, window._currentConfig || {}, patch));
}

async function _enrichWebuiWidgets(config) {
  var models = state.models || [];
  function _isSttModel(model) {
    var caps = model.capabilities || {};
    var id = String(model.id || '').toLowerCase();
    if (caps.audio_transcription || caps.audio_in) return true;
    if (caps.chat && caps.vision) return true;
    if (/whisper|transcribe|paraformer|speech-to-text/.test(id)) return true;
    return false;
  }
  function _isTtsModel(model) {
    var caps = model.capabilities || {};
    var ownedBy = String(model.owned_by || '');
    if (!caps.audio_gen && !caps.tts) return false;
    if (ownedBy === 'edgetts' || ownedBy === 'gtts' || ownedBy === 'openaifm') return true;
    return !!(caps.audio_gen && !caps.chat);
  }
  function _modelIds(filterFn) {
    var opts = [];
    for (var i = 0; i < models.length; i++) {
      if (filterFn(models[i])) opts.push(models[i].id);
    }
    return opts;
  }
  function _fillModelSelect(el, value, filterFn) {
    if (!el) return;
    el.setAttribute('data-dynamic', 'true');
    var ids = _modelIds(filterFn);
    var html = '<option value="">' + escapeHtml(typeof t === 'function' ? t('common.notUsing') : '') + '</option>';
    for (var i = 0; i < ids.length; i++) {
      html += '<option value="' + escapeHtml(ids[i]) + '"' + (ids[i] === value ? ' selected' : '') + '>' + escapeHtml(ids[i]) + '</option>';
    }
    el.innerHTML = html;
    if (typeof CustomDropdown !== 'undefined') {
      if (el._customDropdown && typeof el._customDropdown.destroy === 'function') {
        el._customDropdown.destroy();
      }
      el._customDropdown = new CustomDropdown(el, {
        onChange: function(val) {
          var section = el.getAttribute('data-section');
          var key = el.getAttribute('data-key');
          _configSetValue(window._currentConfig, section, key, val);
          _onWebuiConfigFieldChange(key, val);
          scheduleConfigSave();
        }
      });
    }
  }
  _fillModelSelect(document.getElementById('cfg-_root-sttModel'), config.sttModel || '', _isSttModel);
  _fillModelSelect(document.getElementById('cfg-_root-ttsModel'), config.ttsModel || '', _isTtsModel);
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
  try {
    var devices = await navigator.mediaDevices.enumerateDevices();
    var audioInputs = devices.filter(function(d) { return d.kind === 'audioinput'; });
    var recSel = document.getElementById('cfg-_root-recordingDeviceId');
    if (!recSel) return;
    recSel.setAttribute('data-dynamic', 'true');
    var current = config.recordingDeviceId || '';
    var html = '<option value="">' + escapeHtml(typeof t === 'function' ? t('portable.defaultDevice') : '默认设备') + '</option>';
    for (var i = 0; i < audioInputs.length; i++) {
      var dev = audioInputs[i];
      html += '<option value="' + escapeHtml(dev.deviceId) + '"' + (dev.deviceId === current ? ' selected' : '') + '>'
        + escapeHtml(dev.label || ('Mic ' + (i + 1))) + '</option>';
    }
    recSel.innerHTML = html;
    if (typeof CustomDropdown !== 'undefined') {
      if (recSel._customDropdown && typeof recSel._customDropdown.destroy === 'function') {
        recSel._customDropdown.destroy();
      }
      recSel._customDropdown = new CustomDropdown(recSel, {
        onChange: function(value) {
          _configSetValue(window._currentConfig, '_root', 'recordingDeviceId', value);
          scheduleConfigSave();
        }
      });
    }
  } catch (e) { /* ignore */ }
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

window.getConfigTarget = getConfigTarget;
window.setConfigTarget = setConfigTarget;
window.getConfigEditMode = getConfigEditMode;
window.setConfigEditMode = setConfigEditMode;
window.switchConfigTarget = switchConfigTarget;
window.switchConfigEditMode = switchConfigEditMode;
window.switchConfigSection = switchConfigSection;
window.forceRenderConfig = forceRenderConfig;
window.renderConfig = renderConfig;
window._bindConfigPanel = _bindConfigPanel;
window._applyWebuiRuntime = _applyWebuiRuntime;
window._syncConfigFromDOM = _syncConfigFromDOM;
window._renderConfigData = _renderConfigData;
window._updateConfigSubtitle = _updateConfigSubtitle;
window._updateConfigSaveBtn = _updateConfigSaveBtn;
window._loadConfigRaw = _loadConfigRaw;
