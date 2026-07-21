// ========================= Embedded config panel helpers =========================
// 拆分自 render_embed.js。schema 转换 / 值读写 / DOM 事件绑定等纯逻辑函数。
// 依赖 render_primitives.js（_renderRawJson/_field/_fieldBlock 等）、render_bind.js（_collectMapping）。

// 数组类型字段 -> panel 字段（list 或 json）
function _panelFieldForArray(panel, field) {
  var items = field.items || {};
  if (items.type === 'string' || !items.type) {
    panel.type = 'list';
    return panel;
  }
  panel.type = 'json';
  panel.wide = true;
  return panel;
}

// 字符串类型字段 -> panel 字段（textarea 或普通 string）
function _panelFieldForString(panel, field, key) {
  if (field.format === 'textarea' || (field.maxLength && field.maxLength > 200)) {
    panel.type = 'textarea';
    panel.wide = true;
    return panel;
  }
  if (/content|prompt|description/i.test(key)) {
    panel.type = 'textarea';
    panel.wide = true;
    return panel;
  }
  panel.type = 'string';
  return panel;
}

function jsonSchemaFieldToPanelField(key, field) {
  field = field || {};
  var ftype = field.type;
  var panel = { key: key, label: field.title || key };
  if (Array.isArray(field.enum) && field.enum.length) {
    panel.type = 'select';
    panel.options = field.enum.map(String);
    return panel;
  }
  if (ftype === 'boolean') {
    panel.type = 'boolean';
    return panel;
  }
  if (ftype === 'integer' || ftype === 'number') {
    panel.type = 'number';
    if (field.minimum != null) panel.min = field.minimum;
    if (field.maximum != null) panel.max = field.maximum;
    return panel;
  }
  if (ftype === 'array') {
    return _panelFieldForArray(panel, field);
  }
  if (ftype === 'object') {
    panel.type = 'json';
    panel.wide = true;
    return panel;
  }
  if (ftype === 'string') {
    return _panelFieldForString(panel, field, key);
  }
  panel.type = 'string';
  return panel;
}

function _embeddedSetValue(state, section, key, val) {
  var config = state.config;
  var schema = state.schema || {};
  if (schema.flat || section === '_root') {
    config[key] = val;
    return;
  }
  if (!config[section]) config[section] = {};
  config[section][key] = val;
}

function _embeddedGetValue(state, section, key) {
  var config = state.config;
  var schema = state.schema || {};
  if (schema.flat || section === '_root') return config[key];
  return config[section] && config[section][key];
}

function _embeddedSyncFromDOM(state) {
  var container = state.container;
  if (!container || !state.config) return;
  container.querySelectorAll('.config-list').forEach(function(listEl) {
    var section = listEl.dataset.section;
    var key = listEl.dataset.key;
    if (!section || !key) return;
    var inputs = listEl.querySelectorAll('.config-list-input');
    var list = [];
    inputs.forEach(function(inp) { list.push(inp.value); });
    _embeddedSetValue(state, section, key, list);
  });
  container.querySelectorAll('.config-mapping').forEach(function(mapEl) {
    var section = mapEl.dataset.section;
    var key = mapEl.dataset.key;
    if (!section || !key) return;
    _embeddedSetValue(state, section, key, _collectMapping(mapEl));
  });
}

function _destroyEmbeddedDropdowns(container) {
  if (!container) return;
  container.querySelectorAll('select.config-input').forEach(function(sel) {
    if (sel._customDropdown && typeof sel._customDropdown.destroy === 'function') {
      sel._customDropdown.destroy();
      sel._customDropdown = null;
    }
  });
}

function _bindEmbeddedDropdowns(state) {
  var container = state.container;
  if (!container || typeof CustomDropdown === 'undefined') return;
  container.querySelectorAll('select.config-input').forEach(function(sel) {
    if (sel._customDropdown) return;
    if (!sel.options || sel.options.length === 0) return;
    var dd = new CustomDropdown(sel, {
      onChange: function(value) {
        var section = sel.getAttribute('data-section');
        var key = sel.getAttribute('data-key');
        if (!section || !key) return;
        _embeddedSetValue(state, section, key, value);
        if (typeof state.onChange === 'function') state.onChange(state.config);
      }
    });
    if (dd && dd.el) {
      dd.el.setAttribute('data-section', sel.getAttribute('data-section') || '');
      dd.el.setAttribute('data-key', sel.getAttribute('data-key') || '');
    }
  });
}

function _bindEmbeddedFieldHandlers(state) {
  var container = state.container;
  if (!container) return;
  _bindEmbeddedListHandlers(state);
  _bindEmbeddedMappingHandlers(state);
}

function _bindEmbeddedListHandlers(state) {
  var container = state.container;
  container.querySelectorAll('.config-list-add').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var section = this.dataset.section;
      var key = this.dataset.key;
      var list = _embeddedGetValue(state, section, key) || [];
      list = Array.isArray(list) ? list.slice() : [];
      list.push('');
      _embeddedSetValue(state, section, key, list);
      _renderEmbeddedPanelData(state.panelId);
      if (typeof state.onChange === 'function') state.onChange(state.config);
    });
  });
  container.querySelectorAll('.config-list-remove').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var listEl = this.closest('.config-list');
      var section = listEl.dataset.section;
      var key = listEl.dataset.key;
      var idx = parseInt(this.dataset.index, 10);
      var inputs = listEl.querySelectorAll('.config-list-input');
      var list = [];
      inputs.forEach(function(inp) { list.push(inp.value); });
      list.splice(idx, 1);
      _embeddedSetValue(state, section, key, list);
      _renderEmbeddedPanelData(state.panelId);
      if (typeof state.onChange === 'function') state.onChange(state.config);
    });
  });
}

function _bindEmbeddedMappingHandlers(state) {
  var container = state.container;
  container.querySelectorAll('.config-mapping-add').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var section = this.dataset.section;
      var key = this.dataset.key;
      var mapping = _collectMapping(this.closest('.config-mapping'));
      mapping[''] = '';
      _embeddedSetValue(state, section, key, mapping);
      _renderEmbeddedPanelData(state.panelId);
      if (typeof state.onChange === 'function') state.onChange(state.config);
    });
  });
  container.querySelectorAll('.config-mapping-remove').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var mapEl = this.closest('.config-mapping');
      var section = mapEl.dataset.section;
      var key = mapEl.dataset.key;
      var idx = parseInt(this.dataset.index, 10);
      var mapping = _collectMapping(mapEl);
      var keys = Object.keys(mapping);
      delete mapping[keys[idx]];
      _embeddedSetValue(state, section, key, mapping);
      _renderEmbeddedPanelData(state.panelId);
      if (typeof state.onChange === 'function') state.onChange(state.config);
    });
  });
  container.querySelectorAll('.config-mapping-key, .config-mapping-val').forEach(function(inp) {
    inp.addEventListener('change', function() {
      var mapEl = this.closest('.config-mapping');
      var section = mapEl.dataset.section;
      var key = mapEl.dataset.key;
      _embeddedSetValue(state, section, key, _collectMapping(mapEl));
      if (typeof state.onChange === 'function') state.onChange(state.config);
    });
  });
}

function _onEmbeddedConfigChange(state, e) {
  var el = e.target;
  var section = el.dataset.section;
  var key = el.dataset.key;
  var type = el.dataset.type;
  if (!section || !key || !type) return;
  var val;
  if (type === 'boolean') val = el.checked;
  else if (type === 'number') val = parseInt(el.value, 10) || 0;
  else if (type === 'json') {
    try { val = JSON.parse(el.value); } catch (err) { return; }
  } else if (type === 'list') return;
  else val = el.value;
  _embeddedSetValue(state, section, key, val);
  if (typeof state.onChange === 'function') state.onChange(state.config);
}

function _renderEmbeddedSectionTabs(state) {
  var tabsEl = state.tabsEl;
  if (!tabsEl) return;
  var tabs = _collectSectionTabs(state.schema, state.config);
  if (!tabs.length) {
    state.activeSection = null;
    tabsEl.classList.add('hidden');
    tabsEl.innerHTML = '';
    return;
  }
  var hasActive = false;
  for (var i = 0; i < tabs.length; i++) {
    if (tabs[i].id === state.activeSection) {
      hasActive = true;
      break;
    }
  }
  if (!hasActive) state.activeSection = tabs[0].id;
  if (tabs.length <= 1) {
    tabsEl.classList.add('hidden');
    tabsEl.innerHTML = '';
    return;
  }
  tabsEl.classList.remove('hidden');
  var html = '';
  for (var j = 0; j < tabs.length; j++) {
    var tab = tabs[j];
    html += '<button type="button" class="config-section-tab'
      + (tab.id === state.activeSection ? ' active' : '')
      + '" data-panel-id="' + escapeHtml(state.panelId) + '" data-section="' + escapeHtml(tab.id) + '" role="tab"'
      + (tab.id === state.activeSection ? ' aria-selected="true"' : ' aria-selected="false"')
      + '>[' + escapeHtml(tab.title) + ']</button>';
  }
  tabsEl.innerHTML = html;
  _bindEmbeddedSectionTabsOnce(tabsEl);
}

function _bindEmbeddedSectionTabsOnce(tabsEl) {
  if (tabsEl._embeddedBound) return;
  tabsEl._embeddedBound = true;
  tabsEl.addEventListener('click', function(ev) {
    var btn = ev.target.closest('[data-panel-id][data-section]');
    if (!btn) return;
    var panelId = btn.getAttribute('data-panel-id');
    var sectionId = btn.getAttribute('data-section');
    var panelState = _embeddedPanels[panelId];
    if (!panelState || sectionId === panelState.activeSection) return;
    _embeddedSyncFromDOM(panelState);
    panelState.activeSection = sectionId;
    _renderEmbeddedPanelData(panelId);
  });
}
