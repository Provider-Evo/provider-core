// ========================= Embedded config panel (plugins) =========================
// 拆分自 render.js。依赖 render_primitives.js（_renderRawJson/_field/_fieldBlock 等）、
// render_schema.js（_renderSectionFromSchema/_findSectionDef）、render_main.js（_collectSectionTabs）、
// render_bind.js（_collectMapping）。schema 转换 / 值读写 / DOM 事件绑定拆分到 embedhelpers.js。

var _embeddedPanels = {};

function jsonSchemaToPanelSchema(jsonSchema) {
  if (!jsonSchema || jsonSchema.type !== 'object' || !jsonSchema.properties) {
    return { sections: [], flat: false };
  }
  var props = jsonSchema.properties;
  var keys = Object.keys(props);
  var sections = [];
  var rootFields = [];
  for (var i = 0; i < keys.length; i++) {
    var key = keys[i];
    var prop = props[key] || {};
    if (prop.type === 'object' && prop.properties) {
      var fields = [];
      var subKeys = Object.keys(prop.properties);
      for (var j = 0; j < subKeys.length; j++) {
        fields.push(jsonSchemaFieldToPanelField(subKeys[j], prop.properties[subKeys[j]]));
      }
      sections.push({ id: key, title: prop.title || key, fields: fields });
    } else {
      rootFields.push(jsonSchemaFieldToPanelField(key, prop));
    }
  }
  if (sections.length) {
    if (rootFields.length) {
      sections.unshift({ id: '_root', title: 'general', fields: rootFields });
    }
    return { flat: false, sections: sections };
  }
  if (rootFields.length) {
    return { flat: true, sections: [{ id: '_root', title: 'config', fields: rootFields }] };
  }
  return { sections: [], flat: false };
}

function _renderEmbeddedPanelData(panelId) {
  var state = _embeddedPanels[panelId];
  if (!state || !state.container) return;
  var schema = state.schema || { sections: [] };
  var config = state.config || {};
  _renderEmbeddedSectionTabs(state);
  var html = '';
  var sectionDef = state.activeSection ? _findSectionDef(schema, state.activeSection) : null;
  if (sectionDef) {
    html = _renderSectionFromSchema(sectionDef, config, schema);
  } else if ((schema.sections || []).length) {
    html = _renderSectionFromSchema(schema.sections[0], config, schema);
  }
  if (!html) {
    html = '<div class="text-muted text-sm p-3">' + escapeHtml(typeof t === 'function' ? t('plugins.noSchema') : '无配置 schema') + '</div>';
  }
  _destroyEmbeddedDropdowns(state.container);
  state.container.innerHTML = html;
  _bindEmbeddedPanelEventsOnce(state, panelId);
  _bindEmbeddedFieldHandlers(state);
  _bindEmbeddedDropdowns(state);
}

function _bindEmbeddedPanelEventsOnce(state, panelId) {
  if (state.container._embeddedEventsBound) return;
  state.container._embeddedEventsBound = true;
  state.container.addEventListener('change', function(e) {
    var panelState = _embeddedPanels[panelId];
    if (panelState) _onEmbeddedConfigChange(panelState, e);
  });
  state.container.addEventListener('input', function(e) {
    if (e.target.tagName !== 'TEXTAREA') return;
    var panelState = _embeddedPanels[panelId];
    if (panelState) _onEmbeddedConfigChange(panelState, e);
  });
}

function renderEmbeddedConfigPanel(opts) {
  opts = opts || {};
  var panelId = opts.panelId || 'embedded';
  var container = opts.container;
  if (!container) return null;
  var schema = opts.panelSchema || jsonSchemaToPanelSchema(opts.jsonSchema || {});
  var state = _embeddedPanels[panelId] || {};
  state.panelId = panelId;
  state.container = container;
  state.tabsEl = opts.tabsContainer || null;
  state.schema = schema;
  state.config = opts.config || {};
  state.onChange = opts.onChange || null;
  if (!state.activeSection) {
    state.activeSection = schema.sections && schema.sections[0] ? schema.sections[0].id : null;
  }
  _embeddedPanels[panelId] = state;
  _renderEmbeddedPanelData(panelId);
  return {
    getConfig: function() {
      var panelState = _embeddedPanels[panelId];
      if (panelState) _embeddedSyncFromDOM(panelState);
      return panelState ? panelState.config : {};
    },
    setConfig: function(cfg) {
      var panelState = _embeddedPanels[panelId];
      if (!panelState) return;
      panelState.config = cfg || {};
      _renderEmbeddedPanelData(panelId);
    },
    destroy: function() {
      var panelState = _embeddedPanels[panelId];
      if (panelState && panelState.container) _destroyEmbeddedDropdowns(panelState.container);
      delete _embeddedPanels[panelId];
    }
  };
}

function destroyEmbeddedConfigPanel(panelId) {
  var state = _embeddedPanels[panelId];
  if (!state) return;
  if (state.container) _destroyEmbeddedDropdowns(state.container);
  delete _embeddedPanels[panelId];
}

window.jsonSchemaToPanelSchema = jsonSchemaToPanelSchema;
window.renderEmbeddedConfigPanel = renderEmbeddedConfigPanel;
window.destroyEmbeddedConfigPanel = destroyEmbeddedConfigPanel;
