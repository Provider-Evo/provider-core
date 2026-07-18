/**
 * PluginsPanel 事件绑定层：列表 / 市场 / 安装弹窗 / 编辑器 / 镜像源事件。
 */
async function _evtHandleListClick(P, event) {
  var toggle = event.target.closest('[data-action="toggle"]');
  if (!toggle) {
    var label = event.target.closest('.config-toggle');
    if (label) toggle = label.querySelector('[data-action="toggle"]');
  }
  if (toggle) {
    event.stopPropagation();
    await P.togglePlugin(toggle.getAttribute('data-id'));
    return;
  }
  var btn = event.target.closest('[data-action]');
  if (btn) {
    event.stopPropagation();
    var action = btn.getAttribute('data-action');
    var pluginId = btn.getAttribute('data-id');
    if (action === 'config') await P.openEditor(pluginId);
    else if (action === 'update') await P.updatePlugin(pluginId);
    else if (action === 'uninstall') await P.uninstallPlugin(pluginId, btn.getAttribute('data-path'));
    return;
  }
  var row = event.target.closest('[data-plugin-id]');
  if (row) await P.openEditor(row.getAttribute('data-plugin-id'));
}

async function _evtHandleMarketAction(P, event) {
  var btn = event.target.closest('[data-market-action]');
  if (!btn) return;
  var action = btn.getAttribute('data-market-action');
  if (action === 'install') {
    P.openInstallDialog(btn.getAttribute('data-url'), btn.getAttribute('data-id'));
    return;
  }
  if (action === 'detail') {
    var pluginId = btn.getAttribute('data-id');
    var marketItem = P._marketById[pluginId];
    var installed = P._plugins.find(function (p) { return p.id === pluginId; });
    if (installed) {
      await P.openEditor(pluginId);
      P.setEditorTab('detail');
    } else if (marketItem) {
      var desc = marketItem.manifest ? marketItem.manifest.description : '';
      var changelog = marketItem.changelog || '';
      showInfoDialog(desc + '<br><br>' + changelog, { title: P.t('plugins.detail') || 'Plugin Detail' });
    }
    return;
  }
  if (action === 'like') {
    var likeId = btn.getAttribute('data-id');
    try {
      await Api.post('/v1/admin/plugins/stats/' + encodeURIComponent(likeId) + '/like', {});
      btn.textContent = P.t('plugins.liked');
    } catch (e) {
      if (typeof toast === 'function') toast(P.t('plugins.likeError') || '点赞失败', 'error');
    }
  }
}

function _evtBindInstallDialog(P) {
  var installFromGitBtn = P.el('pluginsInstallFromGitBtn');
  var installBtn = P.el('pluginsInstallBtn');
  var installClose = P.el('pluginsInstallClose');
  var installCancel = P.el('pluginsInstallCancel');
  if (installFromGitBtn) installFromGitBtn.addEventListener('click', function () { P.openInstallDialog('', ''); });
  if (installBtn) installBtn.addEventListener('click', function () {
    var urlInput = P.el('pluginsInstallUrl');
    var refInput = P.el('pluginsInstallRef');
    var url = urlInput ? String(urlInput.value || '').trim() : P._installTarget.url;
    if (!url) {
      var statusEl = P.el('pluginsStatus');
      if (statusEl) statusEl.textContent = P.t('plugins.urlRequired');
      return;
    }
    var ref = refInput && refInput.value.trim() ? refInput.value.trim() : '';
    P.installFromGit(url, ref, P._installTarget.pluginId);
  });
  if (installClose) installClose.addEventListener('click', function () { P.showModal('pluginsInstallModal', false); });
  if (installCancel) installCancel.addEventListener('click', function () { P.showModal('pluginsInstallModal', false); });
}

function _evtBindEditor(P) {
  var editorBack = P.el('pluginsEditorBack');
  var editorSwitch = P.el('pluginsEditorSwitch');
  var editorUpdate = P.el('pluginsEditorUpdate');
  var editorUninstall = P.el('pluginsEditorUninstall');
  var configSave = P.el('pluginsConfigSave');
  var configReset = P.el('pluginsConfigReset');
  if (editorBack) editorBack.addEventListener('click', P.closeEditor);
  if (editorSwitch) editorSwitch.addEventListener('change', function () {
    if (P._editorPluginId) P.togglePlugin(P._editorPluginId);
  });
  if (editorUpdate) editorUpdate.addEventListener('click', function () {
    if (P._editorPluginId) P.updatePlugin(P._editorPluginId);
  });
  if (editorUninstall) editorUninstall.addEventListener('click', function () {
    if (P._editorPlugin && P._editorPluginId) P.uninstallPlugin(P._editorPluginId, P._editorPlugin.path);
  });
  if (configSave) configSave.addEventListener('click', P.saveConfig);
  if (configReset) configReset.addEventListener('click', P.resetConfig);
  document.querySelectorAll('.plugins-editor-tab').forEach(function (node) {
    node.addEventListener('click', function () {
      P.setEditorTab(node.getAttribute('data-editor-tab'));
    });
  });
}

function _evtBindList(P) {
  var list = P.el('pluginsList');
  if (!list) return;
  list.addEventListener('click', function (event) { _evtHandleListClick(P, event); });
  list.addEventListener('keydown', function (e) {
    if (e.key === 'Enter' || e.key === ' ') {
      var row = e.target.closest('[data-plugin-id]');
      if (row) { e.preventDefault(); P.openEditor(row.getAttribute('data-plugin-id')); }
    }
  });
}

function _evtBindTabsAndMirrors(P) {
  var tabInstalled = P.el('pluginsTabInstalled');
  var tabMarket = P.el('pluginsTabMarket');
  var tabMirrors = P.el('pluginsTabMirrors');
  var mirrorAdd = P.el('pluginsMirrorAdd');
  var mirrorsList = P.el('pluginsMirrorsList');
  if (tabInstalled) tabInstalled.addEventListener('click', function () { P.setTab('installed'); });
  if (tabMarket) tabMarket.addEventListener('click', function () { P.setTab('market'); });
  if (tabMirrors) tabMirrors.addEventListener('click', function () { P.setTab('mirrors'); });
  if (mirrorAdd) mirrorAdd.addEventListener('click', P.addMirror);
  if (mirrorsList) mirrorsList.addEventListener('click', function (e) {
    var del = e.target.closest('[data-mirror-delete]');
    if (del) P.deleteMirror(del.getAttribute('data-mirror-delete'));
  });
}

function _evtBindSearchAndMarketToolbar(P) {
  var refreshBtn = P.el('pluginsRefreshBtn');
  var search = P.el('pluginsSearch');
  var showUpdates = P.el('pluginsShowUpdatesOnly');
  var marketRefresh = P.el('pluginsMarketRefreshBtn');
  var marketSearch = P.el('pluginsMarketSearch');
  var marketType = P.el('pluginsMarketType');
  var marketSort = P.el('pluginsMarketSort');
  var marketShowInstalled = P.el('pluginsMarketShowInstalled');
  var marketGrid = P.el('pluginsMarketGrid');
  if (refreshBtn) refreshBtn.addEventListener('click', P.refresh);
  if (search) search.addEventListener('input', function () { P._searchQuery = search.value; P.renderList(); });
  if (showUpdates) showUpdates.addEventListener('change', function () { P._showUpdatesOnly = showUpdates.checked; P.renderList(); });
  if (marketRefresh) marketRefresh.addEventListener('click', P.loadMarket);
  if (marketSearch) marketSearch.addEventListener('input', P.renderMarket);
  if (marketType) marketType.addEventListener('change', P.renderMarket);
  if (marketSort) marketSort.addEventListener('change', P.renderMarket);
  if (marketShowInstalled) marketShowInstalled.addEventListener('change', P.renderMarket);
  if (marketGrid) marketGrid.addEventListener('click', function (event) { _evtHandleMarketAction(P, event); });
}

function _attachPluginsEventMethods(P) {
  P.bindEvents = function bindEvents() {
    _evtBindSearchAndMarketToolbar(P);
    _evtBindList(P);
    _evtBindTabsAndMirrors(P);
    _evtBindInstallDialog(P);
    _evtBindEditor(P);
  };
}
