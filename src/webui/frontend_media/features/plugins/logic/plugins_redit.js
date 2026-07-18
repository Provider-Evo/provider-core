/**
 * PluginsPanel 渲染层：编辑器视图渲染与配置读写。
 */
function _preShowModal(P, modalId, show) {
  var modal = P.el(modalId);
  if (!modal) return;
  modal.classList.toggle('hidden', !show);
  modal.classList.toggle('flex', show);
}

function _preShowMainView(P, showEditor) {
  var main = P.el('pluginsMainView');
  var editor = P.el('pluginsEditorView');
  if (main) main.classList.toggle('hidden', showEditor);
  if (editor) editor.classList.toggle('hidden', !showEditor);
}

function _preSetEditorTab(P, tab) {
  P._editorTab = tab;
  document.querySelectorAll('.plugins-editor-tab').forEach(function (node) {
    node.classList.toggle('active', node.getAttribute('data-editor-tab') === tab);
  });
  var panes = { visual: 'pluginsEditorVisual', source: 'pluginsEditorSource', detail: 'pluginsEditorDetail' };
  Object.keys(panes).forEach(function (key) {
    var pane = P.el(panes[key]);
    if (pane) pane.classList.toggle('hidden', key !== tab);
  });
}

function _preRenderPluginConfigVisual(P, schema, config) {
  var grid = P.el('pluginsConfigGrid');
  var tabs = P.el('pluginsConfigSectionTabs');
  if (!grid) return;
  if (typeof window.renderEmbeddedConfigPanel === 'function') {
    if (P._editorPanelHandle && typeof P._editorPanelHandle.destroy === 'function') {
      P._editorPanelHandle.destroy();
    }
    P._editorPanelId = 'plugin-' + P._editorPluginId;
    P._editorPanelHandle = window.renderEmbeddedConfigPanel({
      panelId: P._editorPanelId,
      container: grid,
      tabsContainer: tabs,
      jsonSchema: schema || {},
      config: config,
      onChange: function (cfg) { P._editorDraft = cfg; }
    });
    return;
  }
  grid.innerHTML = '<div class="plugins-empty">' + P.t('plugins.noSchema') + '</div>';
}

function _preFillEditorHeader(P, pluginId) {
  var title = P.el('pluginsEditorTitle');
  var meta = P.el('pluginsEditorMeta');
  var icon = P.el('pluginsEditorIcon');
  var sw = P.el('pluginsEditorSwitch');
  if (title) title.textContent = P._editorPlugin.name || pluginId;
  if (meta) meta.textContent = pluginId + ' · v' + (P._editorPlugin.version || '-') + ' · ' + P.typeLabel(P._editorPlugin.plugin_type);
  if (icon) {
    icon.src = '/v1/admin/plugins/icon/' + encodeURIComponent(pluginId);
    icon.classList.remove('hidden');
    icon.onerror = function () { icon.classList.add('hidden'); };
  }
  if (sw) sw.checked = !!P._editorPlugin.enabled;
}

async function _preOpenEditor(P, pluginId) {
  P._editorPluginId = pluginId;
  P._editorPlugin = P._plugins.find(function (p) { return p.id === pluginId; }) || null;
  if (!P._editorPlugin) return;

  P.showMainView(true);
  P.setEditorTab('visual');

  _preFillEditorHeader(P, pluginId);

  var msg = P.el('pluginsEditorMessage');
  if (msg) msg.textContent = P.t('plugins.loading');

  try {
    var bundle = await Api.fetchJson('/v1/admin/plugins/config/' + encodeURIComponent(pluginId) + '/bundle');
    if (!bundle.success) throw new Error(bundle.error || 'bundle failed');
    P._editorBundle = bundle;
    P._editorDraft = P.deepClone(bundle.config || {});
    var editor = P.el('pluginsConfigEditor');
    if (editor) editor.value = bundle.raw_config || '';
    P.renderPluginConfigVisual(bundle.schema || {}, P._editorDraft);
    if (msg) msg.textContent = bundle.message || '';
    await P.loadEditorDetail(pluginId);
  } catch (err) {
    if (msg) msg.textContent = P.t('plugins.loadFailed', { error: err.message || String(err) });
  }
}

async function _preLoadEditorRuntime(P, pluginId) {
  var runtime = P.el('pluginsEditorRuntime');
  if (!runtime) return;
  try {
    var comp = await Api.fetchJson('/v1/admin/plugins/runtime/components/' + encodeURIComponent(pluginId));
    var items = (comp && comp.components) ? comp.components : [];
    runtime.textContent = items.length
      ? items.map(function (c) { return (c.type || 'component') + ': ' + (c.id || c.name || ''); }).join('\n')
      : P.t('plugins.noRuntimeComponents');
  } catch (e2) {
    runtime.textContent = '';
  }
}

async function _preLoadEditorDetail(P, pluginId) {
  var readme = P.el('pluginsEditorReadme');
  var changelog = P.el('pluginsEditorChangelog');
  if (readme) readme.textContent = P.t('plugins.loading');
  if (changelog) changelog.textContent = '';
  try {
    var resp = await Api.fetchJson('/v1/admin/plugins/local-readme/' + encodeURIComponent(pluginId));
    if (readme) {
      readme.textContent = (resp && resp.success && resp.data) ? resp.data : P.t('plugins.noReadme');
    }
    var ch = await Api.fetchJson('/v1/admin/plugins/local-changelog/' + encodeURIComponent(pluginId));
    if (changelog) {
      changelog.textContent = (ch && ch.success && ch.data) ? ch.data : P.t('plugins.noChangelog');
    }
    await _preLoadEditorRuntime(P, pluginId);
  } catch (e) {
    if (readme) readme.textContent = P.t('plugins.loadFailed', { error: e.message || String(e) });
  }
}

function _preCloseEditor(P) {
  if (P._editorPanelHandle && typeof P._editorPanelHandle.destroy === 'function') {
    P._editorPanelHandle.destroy();
  }
  P._editorPanelHandle = null;
  P._editorPanelId = '';
  P._editorPluginId = '';
  P._editorPlugin = null;
  P._editorBundle = null;
  P.showMainView(false);
}

async function _preSaveConfigSource(P) {
  var editor = P.el('pluginsConfigEditor');
  await Api.put('/v1/admin/plugins/config/' + encodeURIComponent(P._editorPluginId), { raw: editor ? editor.value : '' });
}

async function _preSaveConfigVisual(P) {
  if (P._editorPanelHandle && typeof P._editorPanelHandle.getConfig === 'function') {
    P._editorDraft = P._editorPanelHandle.getConfig();
  }
  await Api.put('/v1/admin/plugins/config/' + encodeURIComponent(P._editorPluginId), { config: P._editorDraft });
  var editor2 = P.el('pluginsConfigEditor');
  if (editor2) {
    var refreshed = await Api.fetchJson('/v1/admin/plugins/config/' + encodeURIComponent(P._editorPluginId));
    editor2.value = refreshed.raw || '';
  }
}

async function _preSaveConfig(P) {
  if (!P._editorPluginId) return;
  var msg = P.el('pluginsEditorMessage');
  try {
    if (P._editorTab === 'source') {
      await _preSaveConfigSource(P);
    } else {
      await _preSaveConfigVisual(P);
    }
    if (msg) msg.textContent = P.t('common.saved');
  } catch (err) {
    if (msg) msg.textContent = P.t('plugins.actionFailed', { error: err.message || String(err) });
  }
}

async function _preResetConfig(P) {
  if (!P._editorPluginId) return;
  if (!await showConfirmDialog(P.t('plugins.resetConfirm'), { title: P.t('plugins.resetConfig') || 'Reset Config' })) return;
  var msg = P.el('pluginsEditorMessage');
  try {
    var resp = await Api.post('/v1/admin/plugins/config/' + encodeURIComponent(P._editorPluginId) + '/reset', {});
    if (!resp.success) throw new Error(resp.error || 'reset failed');
    P._editorDraft = P.deepClone(resp.config || {});
    var editor = P.el('pluginsConfigEditor');
    if (editor) editor.value = resp.raw_config || '';
    if (P._editorBundle) P.renderPluginConfigVisual(P._editorBundle.schema || {}, P._editorDraft);
    if (msg) msg.textContent = P.t('plugins.resetOk');
  } catch (err) {
    if (msg) msg.textContent = P.t('plugins.actionFailed', { error: err.message || String(err) });
  }
}

function _preOpenInstallDialog(P, url, pluginId) {
  P._installTarget = { url: url || '', pluginId: pluginId || '' };
  var urlInput = P.el('pluginsInstallUrl');
  var refInput = P.el('pluginsInstallRef');
  if (urlInput) urlInput.value = url || '';
  if (refInput) refInput.value = '';
  P.showModal('pluginsInstallModal', true);
}

function _attachPluginsRenderEditorMethods(P) {
  P.showModal = function showModal(modalId, show) { _preShowModal(P, modalId, show); };
  P.showMainView = function showMainView(showEditor) { _preShowMainView(P, showEditor); };
  P.setEditorTab = function setEditorTab(tab) { _preSetEditorTab(P, tab); };
  P.renderPluginConfigVisual = function renderPluginConfigVisual(schema, config) { _preRenderPluginConfigVisual(P, schema, config); };
  P.openEditor = async function openEditor(pluginId) { await _preOpenEditor(P, pluginId); };
  P.loadEditorDetail = async function loadEditorDetail(pluginId) { await _preLoadEditorDetail(P, pluginId); };
  P.closeEditor = function closeEditor() { _preCloseEditor(P); };
  P.saveConfig = async function saveConfig() { await _preSaveConfig(P); };
  P.resetConfig = async function resetConfig() { await _preResetConfig(P); };
  P.openInstallDialog = function openInstallDialog(url, pluginId) { _preOpenInstallDialog(P, url, pluginId); };
}
