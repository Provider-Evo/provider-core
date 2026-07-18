/**
 * PluginsPanel 操作层：刷新 / 市场加载 / 安装 / 启停 / 更新 / 卸载 / 镜像源。
 */
function _actShowMarketError(P, message) {
  var grid = P.el('pluginsMarketGrid');
  if (grid && !grid.children.length) {
    grid.innerHTML = '<div class="plugins-empty col-span-full">' + P.escapeHtml(message) + '</div>';
  }
}

async function _actLoadMarket(P) {
  var statusEl = P.el('pluginsStatus');
  if (statusEl) statusEl.textContent = P.t('plugins.loading');
  try {
    if (!P._marketConfig) {
      P._marketConfig = await Api.fetchJson('/v1/admin/plugins/market-config');
    }
    var cfg = P._marketConfig || {};
    var resp = await Api.post('/v1/admin/plugins/fetch-raw', {
      owner: cfg.owner,
      repo: cfg.repo,
      branch: cfg.branch,
      file_path: cfg.details_file || 'plugin_details.json',
    });
    if (!resp.success || !resp.data) throw new Error(resp.error || 'fetch failed');
    P._market = JSON.parse(resp.data.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F]/g, ''));
    if (!Array.isArray(P._market)) throw new Error('invalid catalog format');
    P.indexMarket();
    P.renderMarket();
    if (P._activeTab === 'installed') P.renderList();
    if (statusEl) statusEl.textContent = P.t('plugins.ready');
  } catch (err) {
    var errText = P.t('plugins.loadFailed', { error: err.message || String(err) });
    _actShowMarketError(P, errText);
    if (statusEl) statusEl.textContent = errText;
  }
}

async function _actRefresh(P) {
  var statusEl = P.el('pluginsStatus');
  if (statusEl) statusEl.textContent = P.t('plugins.loading');
  try {
    await P.loadHostVersion();
    var listResp = await Api.fetchJson('/v1/admin/plugins/installed');
    P._plugins = (listResp && listResp.plugins) ? listResp.plugins : [];
    var statusResp = await Api.fetchJson('/v1/admin/plugins/status');
    P.renderSummary(statusResp && statusResp.summary);
    P.renderList();
    if (P._activeTab === 'market') P.renderMarket();
    else if (P._market.length) P.renderList();
    if (P._editorPluginId) {
      P._editorPlugin = P._plugins.find(function (p) { return p.id === P._editorPluginId; }) || P._editorPlugin;
      var sw = P.el('pluginsEditorSwitch');
      if (sw && P._editorPlugin) sw.checked = !!P._editorPlugin.enabled;
    }
    if (statusEl) statusEl.textContent = P.t('plugins.ready');
  } catch (err) {
    if (statusEl) statusEl.textContent = P.t('plugins.loadFailed', { error: err.message || String(err) });
  }
}

async function _actInstallFromGit(P, url, ref, pluginId) {
  var statusEl = P.el('pluginsStatus');
  if (statusEl) statusEl.textContent = P.t('plugins.installing');
  var body = { url: url };
  if (ref) body.ref = ref;
  if (pluginId) body.plugin_id = pluginId;
  try {
    var resp = await P.runWithProgress(Api.post('/v1/admin/plugins/install', body), P.t('plugins.installing'));
    if (statusEl) statusEl.textContent = P.t('plugins.installOk');
    if (resp && resp.summary) P.renderSummary(resp.summary);
    P.showModal('pluginsInstallModal', false);
    await P.refresh();
  } catch (err) {
    if (statusEl) statusEl.textContent = P.t('plugins.installFailed', { error: err.message || String(err) });
  }
}

async function _actTogglePlugin(P, pluginId) {
  P._actingPluginId = pluginId;
  P.renderList();
  var statusEl = P.el('pluginsStatus');
  try {
    var resp = await P.runWithProgress(Api.post('/v1/admin/plugins/toggle', { plugin_id: pluginId }), P.t('plugins.reloading'));
    if (statusEl) statusEl.textContent = P.t('plugins.toggleOk');
    if (resp && resp.summary) P.renderSummary(resp.summary);
    await P.refresh();
  } catch (err) {
    if (statusEl) statusEl.textContent = P.t('plugins.actionFailed', { error: err.message || String(err) });
  } finally {
    P._actingPluginId = '';
    P.renderList();
  }
}

async function _actUpdatePlugin(P, pluginId) {
  P._actingPluginId = pluginId;
  P.renderList();
  var statusEl = P.el('pluginsStatus');
  try {
    var resp = await P.runWithProgress(Api.post('/v1/admin/plugins/update', { plugin_id: pluginId }), P.t('plugins.updating'));
    if (statusEl) statusEl.textContent = P.t('plugins.updateOk');
    if (resp && resp.summary) P.renderSummary(resp.summary);
    await P.refresh();
  } catch (err) {
    if (statusEl) statusEl.textContent = P.t('plugins.actionFailed', { error: err.message || String(err) });
  } finally {
    P._actingPluginId = '';
    P.renderList();
  }
}

async function _actUninstallPlugin(P, pluginId, folder) {
  if (!await showConfirmDialog(P.t('plugins.uninstallConfirm', { path: folder }), { title: P.t('plugins.uninstall') || 'Uninstall' })) return;
  P._actingPluginId = pluginId;
  P.renderList();
  var statusEl = P.el('pluginsStatus');
  try {
    var resp = await P.runWithProgress(Api.post('/v1/admin/plugins/uninstall', { path: folder }), P.t('plugins.uninstalling'));
    if (statusEl) statusEl.textContent = P.t('plugins.uninstallOk');
    if (resp && resp.summary) P.renderSummary(resp.summary);
    if (P._editorPluginId === pluginId) P.closeEditor();
    await P.refresh();
  } catch (err) {
    if (statusEl) statusEl.textContent = P.t('plugins.actionFailed', { error: err.message || String(err) });
  } finally {
    P._actingPluginId = '';
    P.renderList();
  }
}

async function _actLoadMirrors(P) {
  var list = P.el('pluginsMirrorsList');
  if (!list) return;
  list.textContent = P.t('plugins.loading');
  try {
    var resp = await Api.fetchJson('/v1/admin/plugins/mirrors');
    var mirrors = (resp && resp.mirrors) ? resp.mirrors : [];
    if (!mirrors.length) {
      list.innerHTML = '<div class="plugins-empty">' + P.t('plugins.empty') + '</div>';
      return;
    }
    var html = '';
    mirrors.forEach(function (m) {
      html += '<div class="flex flex-wrap gap-2 items-center py-2 border-t border-border">' +
        '<span class="font-semibold text-sm">' + P.escapeHtml(m.name || m.id) + '</span>' +
        '<span class="text-xs text-muted flex-1">' + P.escapeHtml(m.base_url || '') + '</span>' +
        '<button type="button" class="plugins-icon-btn" data-mirror-delete="' + P.escapeAttr(m.id) + '">&#128465;</button></div>';
    });
    list.innerHTML = html;
  } catch (err) {
    list.textContent = P.t('plugins.loadFailed', { error: err.message || String(err) });
  }
}

async function _actAddMirror(P) {
  var nameInput = P.el('pluginsMirrorName');
  var urlInput = P.el('pluginsMirrorUrl');
  var name = nameInput ? nameInput.value.trim() : '';
  var base_url = urlInput ? urlInput.value.trim() : '';
  if (!name || !base_url) return;
  await Api.post('/v1/admin/plugins/mirrors', { name: name, base_url: base_url });
  if (nameInput) nameInput.value = '';
  if (urlInput) urlInput.value = '';
  await P.loadMirrors();
}

async function _actDeleteMirror(P, mirrorId) {
  await Api.fetchJson('/v1/admin/plugins/mirrors/' + encodeURIComponent(mirrorId), { method: 'DELETE' });
  await P.loadMirrors();
}

function _attachPluginsActionMethods(P) {
  P.loadMarket = function loadMarket() { return _actLoadMarket(P); };
  P.refresh = function refresh() { return _actRefresh(P); };
  P.installFromGit = function installFromGit(url, ref, pluginId) { return _actInstallFromGit(P, url, ref, pluginId); };
  P.togglePlugin = function togglePlugin(pluginId) { return _actTogglePlugin(P, pluginId); };
  P.updatePlugin = function updatePlugin(pluginId) { return _actUpdatePlugin(P, pluginId); };
  P.uninstallPlugin = function uninstallPlugin(pluginId, folder) { return _actUninstallPlugin(P, pluginId, folder); };
  P.loadMirrors = function loadMirrors() { return _actLoadMirrors(P); };
  P.addMirror = function addMirror() { return _actAddMirror(P); };
  P.deleteMirror = function deleteMirror(mirrorId) { return _actDeleteMirror(P, mirrorId); };
}
