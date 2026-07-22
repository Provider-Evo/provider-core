// ========================= Schema fetch & field rendering =========================
// 拆分自 render.js。依赖 render_state.js（_isFlatConfigTarget/schema 变量）与 render_primitives.js。

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
  if (type === 'select') return _renderSelect(sectionId, key, val != null ? val : '', field.options || [], field);
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
  if (typeof _isFlatConfigTarget === 'function' && !_isFlatConfigTarget() && ids.indexOf('autoupdate') === -1) {
    ids.push('autoupdate');
  }
  return ids;
}

function _knownSchemaFieldKeys(schema) {
  var keys = [];
  var sections = (schema && schema.sections) || [];
  for (var i = 0; i < sections.length; i++) {
    var fields = sections[i].fields || [];
    for (var j = 0; j < fields.length; j++) keys.push(fields[j].key);
  }
  return keys;
}

function _findSectionDef(schema, sectionId) {
  var sections = (schema && schema.sections) || [];
  for (var i = 0; i < sections.length; i++) {
    if (sections[i].id === sectionId) return sections[i];
  }
  if (sectionId === 'autoupdate' && typeof _autoupdateSectionDef === 'function') {
    return _autoupdateSectionDef();
  }
  return null;
}
