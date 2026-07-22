// ========================= Main config data rendering, runtime apply, field handlers =========================
// 拆分自 render.js。依赖 render_state.js / render_schema.js / render_main.js / render_bind.js / render_widgets.js。

function _renderConfigData(config) {
  window._currentConfig = config;

  var schema = _activeConfigSchema || (_isFlatConfigTarget() ? _webuiConfigPanelSchema : _configPanelSchema) || { sections: [] };
  _renderSectionTabs(schema, config);

  var html = _buildConfigDataHtml(schema, config);

  if (!configGrid) return;
  configGrid.innerHTML = html;
  _bindConfigGridEventsOnce();

  var finalize = function() {
    _bindConfigFieldHandlers();
    updateConfigSaveStatus();
    _updateConfigSaveBtn();
    _finalizeAutoupdateSection();
  };

  if (_isFlatConfigTarget()) {
    _enrichWebuiWidgets(config).then(function() {
      _bindConfigDropdowns();
      finalize();
    });
  } else {
    _bindConfigDropdowns();
    finalize();
  }
}

function _buildConfigDataHtml(schema, config) {
  var activeId = _activeConfigSection;
  var sectionDef = activeId ? _findSectionDef(schema, activeId) : null;
  var html = '';

  if (sectionDef && sectionDef.id === 'autoupdate' && !schema.flat) {
    html = _renderAutoupdateSection(config.autoupdate || {});
  } else if (sectionDef) {
    html = _renderSectionFromSchema(sectionDef, config, schema);
    if (schema.flat) html += _buildFlatExtraHtml(schema, config);
  } else if (activeId && !schema.flat && config[activeId] && typeof config[activeId] === 'object') {
    html = _sectionCard(activeId, _fieldBlock('(raw)', _renderRawJson(activeId, '_raw', config[activeId])));
  } else if (schema.flat) {
    html = _buildFlatRootHtml(schema, config);
  }

  if (!html) {
    html = '<div class="text-muted text-sm p-3">' + escapeHtml(typeof t === 'function' ? t('config.noSection') : '无配置节') + '</div>';
  }
  return html;
}

function _buildFlatExtraHtml(schema, config) {
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
  return extraHtml ? _sectionCard('(extra)', extraHtml) : '';
}

function _buildFlatRootHtml(schema, config) {
  var knownKeys = _knownSchemaFieldKeys(schema);
  var html = '';
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
  return html;
}

function _bindConfigGridEventsOnce() {
  if (!configGrid || configGrid._eventsBound) return;
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

function _bindConfigDropdowns() {
  if (!configGrid || typeof CustomDropdown === 'undefined') return;
  var configSelects = configGrid.querySelectorAll('select.config-input');
  for (var si = 0; si < configSelects.length; si++) {
    var sel = configSelects[si];
    if (sel.classList.contains('custom-dropdown') || sel._customDropdown) continue;
    if (!sel.options || sel.options.length === 0) continue;
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
    if (dd && dd.el) {
      dd.el._section = sel.getAttribute('data-section');
      dd.el._key = sel.getAttribute('data-key');
      dd.el.setAttribute('data-section', sel.getAttribute('data-section') || '');
      dd.el.setAttribute('data-key', sel.getAttribute('data-key') || '');
      dd.el.setAttribute('data-type', sel.getAttribute('data-type') || 'string');
    }
  }
}

function _bindConfigFieldHandlers() {
  if (!configGrid) return;
  _bindConfigListAddRemove();
  _bindConfigMappingAddRemove();
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
}

function _bindConfigListAddRemove() {
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
      var inputs = container.querySelectorAll('.config-list-input');
      var list = [];
      inputs.forEach(function(inp) { list.push(inp.value); });
      list.splice(idx, 1);
      _configSetValue(window._currentConfig, section, key, list);
      _renderConfigData(window._currentConfig);
    });
  });
}

function _bindConfigMappingAddRemove() {
  configGrid.querySelectorAll('.config-mapping-add').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var section = this.dataset.section;
      var key = this.dataset.key;
      var mapping = _collectMapping(this.closest('.config-mapping'));
      mapping[''] = '';
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
  _applyWebuiTabLayout(config);
  if (typeof saveVoiceSettings === 'function') {
    saveVoiceSettings(_voiceSettingsFromConfig(config));
  }
  if (typeof applyVoiceSettings === 'function') applyVoiceSettings();
}

function _applyWebuiTabLayout(config) {
  if (typeof window._tabLayoutConfig === 'undefined') return;
  if (config.layout) window._tabLayoutConfig.layout = config.layout;
  if (typeof config.sidebarCompressed === 'boolean') {
    window._tabLayoutConfig.sidebarCompressed = config.sidebarCompressed;
  }
  if (typeof window._applyTabLayout === 'function') {
    window._applyTabLayout(window._tabLayoutConfig.layout);
  }
}

function _voiceSettingsFromConfig(config) {
  return normalizeVoiceSettings(config);
}

function _onWebuiConfigFieldChange(key, val) {
  if (!_isFlatConfigTarget()) return;
  var patch = {};
  patch[key] = val;
  _applyWebuiRuntime(Object.assign({}, window._currentConfig || {}, patch));
}

window._renderConfigData = _renderConfigData;
window._applyWebuiRuntime = _applyWebuiRuntime;
