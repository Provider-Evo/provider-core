/**
 * PluginsPanel 渲染层：已安装列表渲染。
 */
function _attachPluginsRenderListMethodsSubSummary(P) {
  P.renderSummary = function renderSummary(summary) {
    summary = summary || {};
    var loaded = P.el('pluginsSummaryLoaded');
    var failed = P.el('pluginsSummaryFailed');
    var inactive = P.el('pluginsSummaryInactive');
    if (loaded) loaded.textContent = P.t('plugins.summaryLoaded', { count: summary.loaded || 0 });
    if (failed) failed.textContent = P.t('plugins.summaryFailed', { count: summary.failed || 0 });
    if (inactive) inactive.textContent = P.t('plugins.summaryInactive', { count: summary.inactive || 0 });
  };
}

function _attachPluginsRenderListMethodsSubTab(P) {
  P.setTab = function setTab(tab) {
    P._activeTab = tab;
    var installedBtn = P.el('pluginsTabInstalled');
    var marketBtn = P.el('pluginsTabMarket');
    var mirrorsBtn = P.el('pluginsTabMirrors');
    var installedPane = P.el('pluginsInstalledPane');
    var marketPane = P.el('pluginsMarketPane');
    var mirrorsPane = P.el('pluginsMirrorsPane');
    var activeCls = 'border-accent text-accent';
    var idleCls = 'border-border text-text hover:bg-panel-alt';
    if (installedBtn) installedBtn.className = 'tab-button cursor-pointer font-bold rounded-lg px-4 py-2 border bg-panel ' + (tab === 'installed' ? activeCls : idleCls);
    if (marketBtn) marketBtn.className = 'tab-button cursor-pointer font-bold rounded-lg px-4 py-2 border bg-panel ' + (tab === 'market' ? activeCls : idleCls);
    if (mirrorsBtn) mirrorsBtn.className = 'tab-button cursor-pointer font-bold rounded-lg px-4 py-2 border bg-panel ' + (tab === 'mirrors' ? activeCls : idleCls);
    if (installedPane) installedPane.classList.toggle('hidden', tab !== 'installed');
    if (marketPane) marketPane.classList.toggle('hidden', tab !== 'market');
    if (mirrorsPane) mirrorsPane.classList.toggle('hidden', tab !== 'mirrors');
    if (tab === 'market' && !P._market.length) P.loadMarket();
    if (tab === 'mirrors') P.loadMirrors();
  };
}

function _attachPluginsRenderListMethodsSubFilter(P) {
  P.filteredPlugins = function filteredPlugins() {
    var query = P._searchQuery.trim().toLowerCase();
    return P._plugins.filter(function (plugin) {
      if (P._showUpdatesOnly && !P.hasMarketUpdate(plugin)) return false;
      if (!query) return true;
      var hay = [plugin.id, plugin.name, plugin.description, plugin.plugin_type, plugin.version].join(' ').toLowerCase();
      return hay.indexOf(query) !== -1;
    });
  };

  P.renderList = function renderList() {
    var list = P.el('pluginsList');
    if (!list) return;
    var items = P.filteredPlugins();
    if (!items.length) {
      list.innerHTML = '<div class="plugins-empty">' + P.t('plugins.empty') + '</div>';
      return;
    }
    var html = '';
    items.forEach(function (plugin) {
      html += P._renderPluginRow(plugin);
    });
    list.innerHTML = html;
  };
}

function _attachPluginsRenderListMethodsSubRow(P) {
  P._renderPluginRow = function _renderPluginRow(plugin) {
    var meta = P.statusMeta(plugin);
    var iconUrl = plugin.id ? '/v1/admin/plugins/icon/' + encodeURIComponent(plugin.id) : '';
    var acting = P._actingPluginId === plugin.id;
    var updateAvail = P.hasMarketUpdate(plugin);
    var err = plugin.load_error
      ? '<div class="plugins-load-error">' + P.escapeHtml(plugin.load_error) + '</div>'
      : '';
    return '<div class="plugins-row' + (plugin.enabled ? '' : ' is-disabled') + '" data-plugin-id="' + P.escapeAttr(plugin.id) + '" role="button" tabindex="0">' +
      '<span class="plugins-status-dot ' + meta.dot + '" title="' + P.escapeAttr(meta.label) + '"></span>' +
      (iconUrl ? '<img class="plugins-row-icon" src="' + P.escapeAttr(iconUrl) + '" alt="" onerror="this.classList.add(\'hidden\')">' : '<div class="plugins-row-icon"></div>') +
      '<div class="plugins-row-main">' +
      '<div class="plugins-row-title">' +
      '<span>' + P.escapeHtml(plugin.name || plugin.path) + '</span>' +
      '<span class="plugins-badge">v' + P.escapeHtml(plugin.version || '-') + '</span>' +
      '<span class="plugins-badge">' + P.escapeHtml(P.typeLabel(plugin.plugin_type)) + '</span>' +
      '<span class="plugins-badge ' + meta.badge + '">' + P.escapeHtml(meta.label) + '</span>' +
      (updateAvail ? '<span class="plugins-badge status-warn">' + P.t('plugins.hasUpdate') + '</span>' : '') +
      '</div>' +
      '<div class="plugins-row-desc">' + P.escapeHtml(plugin.description || '') + '</div>' +
      err +
      '</div>' +
      '<div class="plugins-row-actions">' +
      '<button type="button" class="plugins-icon-btn" data-action="config" data-id="' + P.escapeAttr(plugin.id) + '" title="' + P.escapeAttr(P.t('plugins.config')) + '">&#9881;</button>' +
      '<button type="button" class="plugins-icon-btn' + (updateAvail ? ' has-update' : '') + '" data-action="update" data-id="' + P.escapeAttr(plugin.id) + '" title="' + P.escapeAttr(P.t('plugins.update')) + '"' + (acting ? ' disabled' : '') + '>&#8593;</button>' +
      '<label class="config-toggle" title="' + P.escapeAttr(plugin.enabled ? P.t('plugins.disable') : P.t('plugins.enable')) + '">' +
      '<input type="checkbox" data-action="toggle" data-id="' + P.escapeAttr(plugin.id) + '"' + (plugin.enabled ? ' checked' : '') + (acting ? ' disabled' : '') + '>' +
      '<span class="toggle-slider"></span></label>' +
      '<button type="button" class="plugins-icon-btn" data-action="uninstall" data-path="' + P.escapeAttr(plugin.path) + '" data-id="' + P.escapeAttr(plugin.id) + '" title="' + P.escapeAttr(P.t('plugins.uninstall')) + '"' + (acting ? ' disabled' : '') + '>&#128465;</button>' +
      '</div></div>';
  };
}

function _attachPluginsRenderListMethods(P) {
  _attachPluginsRenderListMethodsSubSummary(P);
  _attachPluginsRenderListMethodsSubTab(P);
  _attachPluginsRenderListMethodsSubFilter(P);
  _attachPluginsRenderListMethodsSubRow(P);
}
