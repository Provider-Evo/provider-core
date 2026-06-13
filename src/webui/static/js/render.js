function renderOverview(summary) {
  const config = summary.config || {};
  const cards = [];
  overviewNotice.textContent = [
    'auth=' + String((config.auth || {}).enabled ?? '-'),
    'proxy=' + String((config.proxy || {}).proxy_enabled ?? '-'),
    'startup_force_kill_port=' + String((config.server || {}).startup_force_kill_port ?? '-'),
    'available_platforms=' + String((summary.counts || {}).available_platforms ?? '-')
  ].join(' | ');

  // Update header badges
  var versionBadge = document.getElementById('versionBadge');
  if (versionBadge) {
    versionBadge.textContent = '版本: ' + ((config.server || {}).version || '-');
    versionBadge.classList.remove('badge-loading');
  }
  var hostBadge = document.getElementById('hostBadge');
  if (hostBadge) {
    var server = config.server || {};
    hostBadge.textContent = (server.host || '-') + ':' + (server.port || '-');
    hostBadge.classList.remove('badge-loading');
  }

  cards.push(makeCard('服务信息', [
    'service: ' + (summary.service || '-'),
    'version: ' + ((config.server || {}).version || '-'),
    'timestamp: ' + String(summary.timestamp || '-')
  ]));
  cards.push(makeCard('服务监听', [
    'host: ' + ((config.server || {}).host || '-'),
    'port: ' + String((config.server || {}).port ?? '-'),
    'debug: ' + String((config.server || {}).debug ?? '-')
  ]));
  cards.push(makeCard('网关策略', [
    'concurrent: ' + String((config.gateway || {}).concurrent_enabled ?? '-'),
    'count: ' + String((config.gateway || {}).concurrent_count ?? '-'),
    'min_tokens: ' + String((config.gateway || {}).min_tokens ?? '-')
  ]));
  cards.push(makeCard('代理与启动', [
    'proxy_enabled: ' + String((config.proxy || {}).proxy_enabled ?? '-'),
    'proxy_server: ' + String((config.proxy || {}).proxy_server || '-'),
    'startup_force_kill_port: ' + String((config.server || {}).startup_force_kill_port ?? '-')
  ]));
  cards.push(makeCard('鉴权摘要', [
    'auth_enabled: ' + String((config.auth || {}).enabled ?? '-'),
    'keys_count: ' + String((config.auth || {}).keys_count ?? '-'),
    'group_count: ' + String((config.auth || {}).group_count ?? '-')
  ]));
  cards.push(makeCard('平台筛选', [
    'list_type: ' + String((config.platforms || {}).list_type || '-'),
    'listed_platforms: ' + String((config.platforms || {}).count ?? '-'),
    'proxy_whitelist: ' + String(((config.platforms_proxy || {}).enabled_platforms || []).join(', ') || '-')
  ]));
  overviewGrid.innerHTML = cards.join('');
}

function renderConfig(summary) {
  const config = summary.config || {};
  const entries = [
    ['server', config.server || {}],
    ['auth', config.auth || {}],
    ['gateway', config.gateway || {}],
    ['proxy', config.proxy || {}],
    ['platforms_proxy', config.platforms_proxy || {}],
    ['platforms', config.platforms || {}],
    ['debug', config.debug || {}]
  ];
  const configText = JSON.stringify(config, null, 2);
  configJsonBox.textContent = configText;
  if (configEditArea && !configEditArea.classList.contains('hidden')) {
    configEditArea.value = configText;
  }
  configGrid.innerHTML = entries.map(function(entry) {
    const title = entry[0];
    const payload = entry[1];
    const rows = Object.keys(payload).map(function(key) {
      return '<div class="text-[14px] leading-[1.7]"><strong>' + key + '</strong>: ' + String(payload[key]) + '</div>';
    }).join('');
    return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift"><div class="text-[13px] text-muted m-0 mb-2">' + title + '</div>' + rows + '</div>';
  }).join('');
  updateConfigSaveStatus();
}

function syncModelFilterOptions(models) {
  const platformDropdown = window._dropdowns && window._dropdowns['modelPlatformSelect'];
  const capabilityDropdown = window._dropdowns && window._dropdowns['modelCapabilitySelect'];
  const platforms = Array.from(new Set((models || []).map(function(model) {
    return String(model.owned_by || '');
  }).filter(Boolean))).sort();
  const capabilities = Array.from(new Set((models || []).flatMap(function(model) {
    return Object.keys(model.capabilities || {}).filter(function(key) {
      return model.capabilities[key];
    });
  }))).sort();
  const platformOpts = [{ value: '', text: '全部平台' }].concat(platforms.map(function(name) {
    return { value: name, text: name };
  }));
  const capabilityOpts = [{ value: '', text: '全部能力' }].concat(capabilities.map(function(name) {
    return { value: name, text: name };
  }));
  if (platformDropdown) platformDropdown.setOptions(platformOpts, true);
  if (capabilityDropdown) capabilityDropdown.setOptions(capabilityOpts, true);
}

function renderModels(models) {
  state.models = models || [];
  const searchValue = (document.getElementById('modelSearchInput') || {}).value || '';
  const platformValue = (document.getElementById('modelPlatformSelect') || {}).value || '';
  const capabilityValue = (document.getElementById('modelCapabilitySelect') || {}).value || '';
  document.getElementById('modelCount').textContent = String(state.models.length);
  syncModelFilterOptions(state.models);
  const filtered = state.models.filter(function(model) {
    const modelId = String(model.id || '');
    const ownedBy = String(model.owned_by || '');
    const capabilities = model.capabilities || {};
    const searchMatch = !searchValue || modelId.toLowerCase().includes(searchValue.toLowerCase());
    const platformMatch = !platformValue || ownedBy === platformValue;
    const capabilityMatch = !capabilityValue || Boolean(capabilities[capabilityValue]);
    return searchMatch && platformMatch && capabilityMatch;
  });
  if (!filtered.length) {
    modelGrid.innerHTML = '<div class="text-muted p-[18px] border border-dashed border-border rounded-xl text-center">没有匹配的模型。</div>';
    return;
  }
  modelGrid.innerHTML = filtered.slice(0, 200).map(function(model) {
    const capabilities = Object.keys(model.capabilities || {}).filter(function(key) {
      return model.capabilities[key];
    }).join(', ') || '-';
    return [
      '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">',
      '<div class="text-[14px] font-semibold mb-2">' + model.id + '</div>',
      '<div class="text-[14px] leading-[1.7]"><strong>owned_by</strong>: ' + String(model.owned_by || '-') + '</div>',
      '<div class="text-[14px] leading-[1.7]"><strong>context_length</strong>: ' + String(model.context_length ?? '-') + '</div>',
      '<div class="text-[14px] leading-[1.7]"><strong>capabilities</strong>: ' + capabilities + '</div>',
      '</div>'
    ].join('');
  }).join('');
}

function renderPlatforms(platforms) {
  const keyword = (document.getElementById('platformSearchInput') || {}).value || '';
  const entries = Object.entries(platforms || {}).filter(function(entry) {
    return !keyword || entry[0].toLowerCase().includes(keyword.toLowerCase());
  });
  document.getElementById('platformCount').textContent = String(Object.keys(platforms || {}).length);
  document.getElementById('availablePlatformCount').textContent = String(entries.filter(function(entry) {
    return Number((entry[1] || {}).available || 0) > 0;
  }).length);
  if (!entries.length) {
    platformGrid.innerHTML = '<div class="text-muted p-[18px] border border-dashed border-border rounded-xl text-center">没有匹配的平台。</div>';
    return;
  }
  platformGrid.innerHTML = entries.map(function(entry) {
    const name = entry[0];
    const info = entry[1] || {};
    const statusClass = info.error ? 'err' : (Number(info.available || 0) > 0 ? 'ok' : 'warn');
    const statusText = info.error ? 'error' : (Number(info.available || 0) > 0 ? 'available' : 'idle');
    return [
      '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">',
      '<div class="text-[14px] font-semibold mb-2">' + name + ' <span class="inline-flex items-center rounded-full px-2 py-1 text-xs bg-panel text-' + statusClass + '">' + statusText + '</span></div>',
      '<div class="text-[14px] leading-[1.7]"><strong>candidates</strong>: ' + String(info.candidates ?? '-') + '</div>',
      '<div class="text-[14px] leading-[1.7]"><strong>available</strong>: ' + String(info.available ?? '-') + '</div>',
      '<div class="text-[14px] leading-[1.7]"><strong>models</strong>: ' + String(info.models ?? '-') + '</div>',
      '<div class="text-[14px] leading-[1.7]"><strong>context_length</strong>: ' + String(info.context_length ?? '-') + '</div>',
      (info.error ? '<div class="text-[14px] leading-[1.7]"><strong>error</strong>: ' + String(info.error) + '</div>' : ''),
      '</div>'
    ].join('');
  }).join('');
}

function makeCard(title, rows) {
  return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift"><div class="text-[13px] text-muted m-0 mb-2">' + title + '</div>' + rows.map(function(row) {
    return '<div class="text-[14px] leading-[1.7]">' + row + '</div>';
  }).join('') + '</div>';
}
