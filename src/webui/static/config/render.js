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
function _renderNumber(section, key, val) {
  var id = 'cfg-' + section + '-' + key;
  return '<input type="number" class="config-input" id="' + id
    + '" data-section="' + section + '" data-key="' + key + '" data-type="number"'
    + ' value="' + val + '">';
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
 * Render a JSON object/map editor component.
 */
function _renderJsonEditor(section, key, val) {
  var id = 'cfg-' + section + '-' + key;
  var text = '';
  try { text = JSON.stringify(val, null, 2); } catch(e) { text = '{}'; }
  return '<textarea class="config-json" id="' + id
    + '" data-section="' + section + '" data-key="' + key + '" data-type="json"'
    + ' rows="' + Math.max(2, Math.min(8, text.split('\n').length)) + '">'
    + escapeHtml(text) + '</textarea>';
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

// ========================= Section Renderers =========================

function _renderServerSection(cfg) {
  var s = cfg.server || {};
  return _sectionCard('server',
    _field('version', _renderReadonly('server', 'version', s.version || ''))
    + _field('host', _renderText('server', 'host', s.host || '0.0.0.0'))
    + _field('port', _renderNumber('server', 'port', s.port || 1337))
    + _field('debug', _renderToggle('server', 'debug', !!s.debug))
    + _field('startup_force_kill_port', _renderToggle('server', 'startup_force_kill_port', !!s.startup_force_kill_port))
  );
}

function _renderAuthSection(cfg) {
  var s = cfg.auth || {};
  return _sectionCard('auth',
    _field('enabled', _renderToggle('auth', 'enabled', !!s.enabled))
    + _fieldBlock('keys', _renderStringList('auth', 'keys', s.keys || []))
    + _field('group_list_type', _renderSelect('auth', 'group_list_type', s.group_list_type || 'blacklist', ['blacklist', 'whitelist']))
    + _fieldBlock('group_list', _renderStringList('auth', 'group_list', s.group_list || []))
  );
}

function _renderGatewaySection(cfg) {
  var s = cfg.gateway || {};
  return _sectionCard('gateway',
    _field('concurrent_enabled', _renderToggle('gateway', 'concurrent_enabled', !!s.concurrent_enabled))
    + _field('concurrent_count', _renderNumber('gateway', 'concurrent_count', s.concurrent_count || 3))
    + _field('min_tokens', _renderNumber('gateway', 'min_tokens', s.min_tokens || 10))
    + _field('group_list_type', _renderSelect('gateway', 'group_list_type', s.group_list_type || 'whitelist', ['blacklist', 'whitelist']))
    + _fieldBlock('group_list', _renderStringList('gateway', 'group_list', s.group_list || []))
  );
}

function _renderProxySection(cfg) {
  var s = cfg.proxy || {};
  return _sectionCard('proxy',
    _field('proxy_enabled', _renderToggle('proxy', 'proxy_enabled', !!s.proxy_enabled))
    + _field('proxy_server', _renderText('proxy', 'proxy_server', s.proxy_server || ''))
    + _fieldBlock('proxy_urls', _renderStringList('proxy', 'proxy_urls', s.proxy_urls || []))
  );
}

function _renderPlatformsProxySection(cfg) {
  var s = cfg.platforms_proxy || {};
  return _sectionCard('platforms_proxy',
    _fieldBlock('enabled_platforms', _renderStringList('platforms_proxy', 'enabled_platforms', s.enabled_platforms || []))
    + _field('group_list_type', _renderSelect('platforms_proxy', 'group_list_type', s.group_list_type || 'whitelist', ['blacklist', 'whitelist']))
  );
}

function _renderPlatformsSection(cfg) {
  var s = cfg.platforms || {};
  return _sectionCard('platforms',
    _field('platform_list_type', _renderSelect('platforms', 'platform_list_type', s.platform_list_type || 'blacklist', ['blacklist', 'whitelist']))
    + _fieldBlock('platform_list', _renderStringList('platforms', 'platform_list', s.platform_list || []))
  );
}

function _renderFncallSection(cfg) {
  var s = cfg.fncall || {};
  return _sectionCard('fncall',
    _field('protocol', _renderSelect('fncall', 'protocol', s.protocol || 'antml',
      ['xml', 'antml', 'nous', 'bracket', 'original', 'custom']))
    + _field('record_prompt', _renderToggle('fncall', 'record_prompt', !!s.record_prompt))
    + _field('print_prompt', _renderToggle('fncall', 'print_prompt', !!s.print_prompt))
    + _fieldBlock('fncall_mapping', _renderJsonEditor('fncall', 'fncall_mapping', s.fncall_mapping || {}))
  );
}

function _renderDebugSection(cfg) {
  var s = cfg.debug || {};
  return _sectionCard('debug',
    _field('level', _renderSelect('debug', 'level', s.level || 'DEBUG',
      ['DEBUG', 'INFO', 'WARNING', 'ERROR']))
    + _field('color', _renderToggle('debug', 'color', !!s.color))
    + _field('access_log', _renderToggle('debug', 'access_log', !!s.access_log))
    + (s.log_name ? _field('log_name', _renderText('debug', 'log_name', s.log_name)) : '')
  );
}

function _renderAutoupdateSection(cfg) {
  var s = cfg.autoupdate || {};
  return _sectionCard('autoupdate',
    _field('enabled', _renderToggle('autoupdate', 'enabled', !!s.enabled))
    + _field('branch', _renderText('autoupdate', 'branch', s.branch || 'dev'))
    + _field('interval', _renderNumber('autoupdate', 'interval', s.interval || 300))
    + _field('diff_update', _renderToggle('autoupdate', 'diff_update', !!s.diff_update))
    + _fieldBlock('mirrors', _renderStringList('autoupdate', 'mirrors', s.mirrors || []))
  );
}

function _renderAnthropicSection(cfg) {
  var s = cfg.anthropic || {};
  return _sectionCard('anthropic',
    _field('api_version', _renderText('anthropic', 'api_version', s.api_version || ''))
    + _fieldBlock('model_mapping', _renderJsonEditor('anthropic', 'model_mapping', s.model_mapping || {}))
  );
}

// ========================= Main Render =========================

function renderConfig(summary) {
  fetchJson('/v1/config').then(function(config) {
    _renderConfigData(config);
  }).catch(function() {
    _renderConfigData(summary.config || {});
  });
}

function _renderConfigData(config) {
  // Store config globally for save operations
  window._currentConfig = config;

  var configText = JSON.stringify(config, null, 2);
  configJsonBox.textContent = configText;
  if (configEditArea && !configEditArea.classList.contains('hidden')) {
    configEditArea.value = configText;
  }

  // Render section cards in order
  var html = '';
  html += _renderServerSection(config);
  html += _renderAuthSection(config);
  html += _renderGatewaySection(config);
  html += _renderProxySection(config);
  html += _renderPlatformsProxySection(config);
  html += _renderPlatformsSection(config);
  html += _renderFncallSection(config);
  html += _renderDebugSection(config);
  html += _renderAutoupdateSection(config);
  if (config.anthropic) html += _renderAnthropicSection(config);

  // Render any unknown sections as generic JSON
  var knownSections = ['server','auth','gateway','proxy','platforms_proxy','platforms','fncall','debug','autoupdate','anthropic'];
  Object.keys(config).forEach(function(section) {
    if (knownSections.indexOf(section) === -1 && typeof config[section] === 'object' && config[section] !== null) {
      html += _sectionCard(section, _field('(raw)', _renderJsonEditor(section, '_raw', config[section])));
    }
  });

  configGrid.innerHTML = html;

  // Bind events only once (survives re-renders since delegation is on configGrid)
  if (!configGrid._eventsBound) {
    configGrid._eventsBound = true;
    configGrid.addEventListener('change', _onConfigChange);
    configGrid.addEventListener('input', function(e) {
      if (e.target.tagName === 'TEXTAREA') return;
      _onConfigChange(e);
    });
  }

  // Bind list add/remove buttons
  configGrid.querySelectorAll('.config-list-add').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var section = this.dataset.section;
      var key = this.dataset.key;
      var list = window._currentConfig[section] && window._currentConfig[section][key] || [];
      list.push('');
      if (!window._currentConfig[section]) window._currentConfig[section] = {};
      window._currentConfig[section][key] = list;
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
      window._currentConfig[section][key] = list;
      _renderConfigData(window._currentConfig);
    });
  });

  updateConfigSaveStatus();
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

  if (!window._currentConfig[section]) window._currentConfig[section] = {};
  window._currentConfig[section][key] = val;

  // Update JSON preview
  configJsonBox.textContent = JSON.stringify(window._currentConfig, null, 2);
  if (configEditArea && !configEditArea.classList.contains('hidden')) {
    configEditArea.value = configJsonBox.textContent;
  }
  scheduleConfigSave();
}
