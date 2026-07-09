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
    versionBadge.textContent = t('overview.versionBadge', { version: (config.server || {}).version || '-' });
    versionBadge.classList.remove('badge-loading');
  }
  var hostBadge = document.getElementById('hostBadge');
  if (hostBadge) {
    var server = config.server || {};
    hostBadge.textContent = (server.host || '-') + ':' + (server.port || '-');
    hostBadge.classList.remove('badge-loading');
  }

  cards.push(makeCard(t('render.serviceInfo'), [
    t('render.service') + ': ' + (summary.service || '-'),
    t('render.version') + ': ' + ((config.server || {}).version || '-'),
    t('render.timestamp') + ': ' + String(summary.timestamp || '-')
  ]));
  cards.push(makeCard(t('render.serviceListen'), [
    t('render.host') + ': ' + ((config.server || {}).host || '-'),
    t('render.port') + ': ' + String((config.server || {}).port ?? '-'),
    t('render.debug') + ': ' + String((config.server || {}).debug ?? '-')
  ]));
  cards.push(makeCard(t('render.gatewayPolicy'), [
    t('render.concurrent') + ': ' + String((config.gateway || {}).concurrent_enabled ?? '-'),
    t('render.count') + ': ' + String((config.gateway || {}).concurrent_count ?? '-'),
    t('render.minTokens') + ': ' + String((config.gateway || {}).min_tokens ?? '-')
  ]));
  cards.push(makeCard(t('render.proxyStartup'), [
    t('render.proxyEnabled') + ': ' + String((config.proxy || {}).proxy_enabled ?? '-'),
    t('render.proxyServer') + ': ' + String((config.proxy || {}).proxy_server || '-'),
    t('render.startupForceKillPort') + ': ' + String((config.server || {}).startup_force_kill_port ?? '-')
  ]));
  cards.push(makeCard(t('render.authSummary'), [
    t('render.authEnabled') + ': ' + String((config.auth || {}).enabled ?? '-'),
    t('render.keysCount') + ': ' + String((config.auth || {}).keys_count ?? '-'),
    t('render.groupCount') + ': ' + String((config.auth || {}).group_count ?? '-')
  ]));
  cards.push(makeCard(t('render.platformFilter'), [
    t('render.listType') + ': ' + String((config.platforms || {}).list_type || '-'),
    t('render.listedPlatforms') + ': ' + String((config.platforms || {}).count ?? '-'),
    t('render.proxyWhitelist') + ': ' + String(((config.platforms_proxy || {}).enabled_platforms || []).join(', ') || '-')
  ]));
  overviewGrid.innerHTML = cards.join('');
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
  const platformOpts = [{ value: '', text: t('models.allPlatforms') }].concat(platforms.map(function(name) {
    return { value: name, text: name };
  }));
  const capabilityOpts = [{ value: '', text: t('models.allCapabilities') }].concat(capabilities.map(function(name) {
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
  if (!state.modelsLoaded) {
    modelGrid.innerHTML = '<div class="text-muted p-[18px] border border-dashed border-border rounded-xl text-center">' + t('common.loading') + '</div>';
    return;
  }
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
    modelGrid.innerHTML = '<div class="text-muted p-[18px] border border-dashed border-border rounded-xl text-center">' + t('models.noMatch') + '</div>';
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
    platformGrid.innerHTML = '<div class="text-muted p-[18px] border border-dashed border-border rounded-xl text-center">' + t('platforms.noMatch') + '</div>';
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
