// ========================= Config Component System =========================
// 拆分自 render.js。基础控件渲染函数（无状态，纯字符串拼装）。

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
function _renderSelect(section, key, val, options, field) {
  field = field || {};
  var id = 'cfg-' + section + '-' + key;
  var opts = options || [];
  var dynamicAttr = field.dynamic ? ' data-dynamic="true"' : '';
  var html = '<select class="config-input" id="' + id
    + '" data-section="' + section + '" data-key="' + key + '" data-type="string"' + dynamicAttr + '>';
  if (!opts.length) {
    var placeholder = field.dynamic
      ? (typeof t === 'function' ? t('common.loading') : '加载中...')
      : (typeof t === 'function' ? t('common.notUsing') : '');
    html += '<option value="">' + escapeHtml(placeholder) + '</option>';
  } else {
    var labels = field.optionLabels || {};
    for (var i = 0; i < opts.length; i++) {
      var opt = opts[i];
      var text = labels[opt] != null ? labels[opt] : opt;
      html += '<option value="' + escapeHtml(opt) + '"'
        + (String(opt) === String(val) ? ' selected' : '') + '>' + escapeHtml(text) + '</option>';
    }
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
  html += '<button type="button" class="config-list-add" data-section="' + section + '" data-key="' + key + '">' + (typeof t === 'function' ? t('config.addItem') : '+ Add') + '</button>';
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
  html += '<button type="button" class="config-list-add config-mapping-add" data-section="' + section + '" data-key="' + key + '">' + (typeof t === 'function' ? t('config.addMapping') : '+ Add mapping') + '</button>';
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
