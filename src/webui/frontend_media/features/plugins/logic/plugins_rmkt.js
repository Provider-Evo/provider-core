/**
 * PluginsPanel 渲染层：市场列表渲染。
 */
/**
 * Filter and sort the market item list according to the current search /
 * type / sort / show-installed controls. Split out of renderMarket to keep
 * it under the line cap.
 */
function _pluginsFilterMarketItems(P, installedIds) {
  var query = P.el('pluginsMarketSearch') ? String(P.el('pluginsMarketSearch').value || '').trim().toLowerCase() : '';
  var typeFilter = P.el('pluginsMarketType') ? P.el('pluginsMarketType').value : '';
  var sortBy = P.el('pluginsMarketSort') ? P.el('pluginsMarketSort').value : 'name';
  var showInstalled = P.el('pluginsMarketShowInstalled') ? P.el('pluginsMarketShowInstalled').checked : false;

  var items = P._market.filter(function (item) {
    var manifest = item.manifest || {};
    var id = item.id || manifest.id || '';
    if (!showInstalled && installedIds[id]) return false;
    if (typeFilter && manifest.plugin_type !== typeFilter) return false;
    if (!query) return true;
    var hay = [id, manifest.name, manifest.description, manifest.plugin_type].join(' ').toLowerCase();
    return hay.indexOf(query) !== -1;
  });

  items.sort(function (a, b) {
    var ma = a.manifest || {};
    var mb = b.manifest || {};
    if (sortBy === 'type') {
      return String(ma.plugin_type || '').localeCompare(String(mb.plugin_type || ''));
    }
    return String(ma.name || a.id || '').localeCompare(String(mb.name || b.id || ''));
  });

  return items;
}

/**
 * Build the action-buttons markup for a single market card (readme/like plus
 * install/installed/incompatible state). Split out of _renderMarketCard to
 * keep it under the line cap.
 */
function _pluginsMarketCardActions(P, id, installed, repo, compatible) {
  var html = '<button type="button" class="cursor-pointer text-xs rounded-lg px-2 py-1 border border-border bg-panel" data-market-action="detail" data-id="' + P.escapeAttr(id) + '">' + P.t('plugins.readme') + '</button>' +
    '<button type="button" class="cursor-pointer text-xs rounded-lg px-2 py-1 border border-border bg-panel" data-market-action="like" data-id="' + P.escapeAttr(id) + '">' + P.t('plugins.like') + '</button>';
  if (!installed && repo && compatible) {
    html += '<button type="button" class="cursor-pointer text-xs rounded-lg px-2 py-1 border border-accent text-accent bg-panel" data-market-action="install" data-url="' + P.escapeAttr(repo) + '" data-id="' + P.escapeAttr(id) + '">' + P.t('plugins.install') + '</button>';
  } else if (installed) {
    html += '<span class="text-xs text-ok px-2 py-1">' + P.t('plugins.installed') + '</span>';
  } else if (!compatible) {
    html += '<span class="text-xs text-warn px-2 py-1">' + P.t('plugins.incompatible') + '</span>';
  }
  return html;
}

function _attachPluginsRenderMarketMethods(P) {
  P.renderMarket = function renderMarket() {
    var grid = P.el('pluginsMarketGrid');
    if (!grid) return;
    var installedIds = {};
    P._plugins.forEach(function (p) { if (p.id) installedIds[p.id] = p; });

    var items = _pluginsFilterMarketItems(P, installedIds);

    if (!items.length) {
      grid.innerHTML = '<div class="plugins-empty col-span-full">' + P.t('plugins.empty') + '</div>';
      return;
    }

    var html = '';
    items.forEach(function (item) {
      html += P._renderMarketCard(item, installedIds);
    });
    grid.innerHTML = html;
  };

  P._renderMarketCard = function _renderMarketCard(item, installedIds) {
    var manifest = item.manifest || {};
    var id = item.id || manifest.id || '';
    var installed = installedIds[id];
    var compatible = P.isCompatible(manifest);
    var repo = manifest.urls && manifest.urls.repository ? manifest.urls.repository : (manifest.repository_url || '');
    var icon = item.assets && item.assets.icon_64 ? item.assets.icon_64 : '';
    var iconLocal = id ? '/v1/admin/plugins/icon/' + encodeURIComponent(id) : '';
    var html = '<div class="plugins-market-card">' +
      '<div class="flex items-start gap-2">' +
      '<img class="plugins-row-icon" src="' + P.escapeAttr(icon || iconLocal) + '" alt="" onerror="this.style.visibility=\'hidden\'">' +
      '<div class="flex-1 min-w-0">' +
      '<div class="font-semibold truncate">' + P.escapeHtml(manifest.name || id) + '</div>' +
      '<div class="text-xs text-muted">' + P.escapeHtml(manifest.version || '') + ' · ' + P.escapeHtml(P.typeLabel(manifest.plugin_type)) + '</div>' +
      '</div></div>' +
      '<div class="text-xs text-muted line-clamp-3">' + P.escapeHtml(manifest.description || '') + '</div>' +
      '<div class="flex flex-wrap gap-1 mt-auto">' +
      _pluginsMarketCardActions(P, id, installed, repo, compatible) +
      '</div></div>';
    return html;
  };
}
