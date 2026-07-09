/**
 * 插件管理面板（MaiBot 式：列表行 + 配置编辑器 + 市场）
 */
var PluginsPanel = (function () {
  var _loaded = false;
  var _plugins = [];
  var _market = [];
  var _marketById = {};
  var _hostVersion = null;
  var _marketConfig = null;
  var _activeTab = 'installed';
  var _editorPluginId = '';
  var _editorPlugin = null;
  var _editorBundle = null;
  var _editorTab = 'visual';
  var _editorDraft = {};
  var _editorPanelHandle = null;
  var _editorPanelId = '';
  var _actingPluginId = '';
  var _showUpdatesOnly = false;
  var _searchQuery = '';
  var _installTarget = { url: '', pluginId: '' };

  function t(key, vars) {
    if (typeof I18n !== 'undefined' && I18n.t) return I18n.t(key, vars);
    return key;
  }

  function el(id) { return document.getElementById(id); }

  function escapeHtml(text) {
    return String(text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function escapeAttr(text) {
    return escapeHtml(text).replace(/'/g, '&#39;');
  }

  function typeLabel(ptype) {
    var map = {
      platform: t('plugins.typePlatform'),
      fncall: t('plugins.typeFncall'),
      webui: t('plugins.typeWebui'),
      coplan: t('plugins.typeCoplan'),
      general: t('plugins.typeGeneral'),
    };
    return map[ptype] || ptype || '-';
  }

  function parseVersionTuple(version) {
    var parts = String(version || '0.0.0').split('-')[0].split('.');
    return [
      parseInt(parts[0], 10) || 0,
      parseInt(parts[1], 10) || 0,
      parseInt(parts[2], 10) || 0,
    ];
  }

  function compareVersions(current, latest) {
    var a = parseVersionTuple(current);
    var b = parseVersionTuple(latest);
    for (var i = 0; i < 3; i++) {
      if (b[i] > a[i]) return 1;
      if (b[i] < a[i]) return -1;
    }
    return 0;
  }

  function isCompatible(manifest) {
    if (!_hostVersion || !manifest || !manifest.host_application) return true;
    var min = parseVersionTuple(manifest.host_application.min_version);
    var current = [_hostVersion.version_major || 0, _hostVersion.version_minor || 0, _hostVersion.version_patch || 0];
    for (var i = 0; i < 3; i++) {
      if (current[i] < min[i]) return false;
      if (current[i] > min[i]) break;
    }
    var maxVersion = manifest.host_application.max_version;
    if (maxVersion) {
      var max = parseVersionTuple(maxVersion);
      for (var j = 0; j < 3; j++) {
        if (current[j] > max[j]) return current[0] === max[0];
        if (current[j] < max[j]) break;
      }
    }
    return true;
  }

  function statusMeta(plugin) {
    if (plugin.circuit_status === 'open') {
      return { dot: 'err', badge: 'status-err', label: t('plugins.circuitOpen') };
    }
    if (!plugin.enabled) {
      return { dot: 'muted', badge: 'status-warn', label: t('plugins.statusInactive') };
    }
    if (plugin.loaded) {
      return { dot: 'ok', badge: 'status-ok', label: t('plugins.statusLoaded') };
    }
    if (plugin.load_status === 'failed') {
      return { dot: 'err', badge: 'status-err', label: t('plugins.statusFailed') };
    }
    if (plugin.load_status === 'loading') {
      return { dot: 'warn', badge: 'status-warn', label: t('plugins.statusLoading') };
    }
    return { dot: 'warn', badge: 'status-warn', label: t('plugins.statusUnknown') };
  }

  function hasMarketUpdate(plugin) {
    var market = _marketById[plugin.id];
    if (!market || !market.manifest) return false;
    return compareVersions(plugin.version, market.manifest.version || '') > 0;
  }

  function showProgress(visible) {
    var wrap = el('pluginsProgressWrap');
    if (wrap) wrap.classList.toggle('hidden', !visible);
  }

  function renderProgress(data) {
    if (!data) return;
    var msg = el('pluginsProgressMessage');
    var pct = el('pluginsProgressPercent');
    var bar = el('pluginsProgressBar');
    var statusEl = el('pluginsStatus');
    if (msg) msg.textContent = data.message || data.stage || '';
    if (pct) pct.textContent = String(data.progress || 0) + '%';
    if (bar) bar.style.width = String(data.progress || 0) + '%';
    if (statusEl && data.message) statusEl.textContent = data.message;
    if (data.operation && data.operation !== 'idle') showProgress(true);
    if (data.progress >= 100 || data.stage === 'error') {
      setTimeout(function () { showProgress(false); }, 1200);
    }
  }

  function onProgressFromSocket(data) {
    renderProgress(data);
    if (data && (data.progress >= 100 || data.stage === 'error')) {
      refresh();
    }
  }

  async function runWithProgress(promise, operationLabel) {
    var statusEl = el('pluginsStatus');
    if (statusEl) statusEl.textContent = operationLabel || t('plugins.loading');
    showProgress(true);
    try {
      return await promise;
    } finally {
      try {
        var data = await Api.fetchJson('/v1/admin/plugins/progress');
        renderProgress(data);
      } catch (e) { /* ignore */ }
    }
  }

  function renderSummary(summary) {
    summary = summary || {};
    var loaded = el('pluginsSummaryLoaded');
    var failed = el('pluginsSummaryFailed');
    var inactive = el('pluginsSummaryInactive');
    if (loaded) loaded.textContent = t('plugins.summaryLoaded', { count: summary.loaded || 0 });
    if (failed) failed.textContent = t('plugins.summaryFailed', { count: summary.failed || 0 });
    if (inactive) inactive.textContent = t('plugins.summaryInactive', { count: summary.inactive || 0 });
  }

  function setTab(tab) {
    _activeTab = tab;
    var installedBtn = el('pluginsTabInstalled');
    var marketBtn = el('pluginsTabMarket');
    var mirrorsBtn = el('pluginsTabMirrors');
    var installedPane = el('pluginsInstalledPane');
    var marketPane = el('pluginsMarketPane');
    var mirrorsPane = el('pluginsMirrorsPane');
    var activeCls = 'border-accent text-accent';
    var idleCls = 'border-border text-text hover:bg-panel-alt';
    if (installedBtn) installedBtn.className = 'tab-button cursor-pointer font-bold rounded-lg px-4 py-2 border bg-panel ' + (tab === 'installed' ? activeCls : idleCls);
    if (marketBtn) marketBtn.className = 'tab-button cursor-pointer font-bold rounded-lg px-4 py-2 border bg-panel ' + (tab === 'market' ? activeCls : idleCls);
    if (mirrorsBtn) mirrorsBtn.className = 'tab-button cursor-pointer font-bold rounded-lg px-4 py-2 border bg-panel ' + (tab === 'mirrors' ? activeCls : idleCls);
    if (installedPane) installedPane.classList.toggle('hidden', tab !== 'installed');
    if (marketPane) marketPane.classList.toggle('hidden', tab !== 'market');
    if (mirrorsPane) mirrorsPane.classList.toggle('hidden', tab !== 'mirrors');
    if (tab === 'market' && !_market.length) loadMarket();
    if (tab === 'mirrors') loadMirrors();
  }

  function filteredPlugins() {
    var query = _searchQuery.trim().toLowerCase();
    return _plugins.filter(function (plugin) {
      if (_showUpdatesOnly && !hasMarketUpdate(plugin)) return false;
      if (!query) return true;
      var hay = [plugin.id, plugin.name, plugin.description, plugin.plugin_type, plugin.version].join(' ').toLowerCase();
      return hay.indexOf(query) !== -1;
    });
  }

  function renderList() {
    var list = el('pluginsList');
    if (!list) return;
    var items = filteredPlugins();
    if (!items.length) {
      list.innerHTML = '<div class="plugins-empty">' + t('plugins.empty') + '</div>';
      return;
    }
    var html = '';
    items.forEach(function (plugin) {
      var meta = statusMeta(plugin);
      var iconUrl = plugin.id ? '/v1/admin/plugins/icon/' + encodeURIComponent(plugin.id) : '';
      var acting = _actingPluginId === plugin.id;
      var updateAvail = hasMarketUpdate(plugin);
      var err = plugin.load_error
        ? '<div class="plugins-load-error">' + escapeHtml(plugin.load_error) + '</div>'
        : '';
      html += '<div class="plugins-row' + (plugin.enabled ? '' : ' is-disabled') + '" data-plugin-id="' + escapeAttr(plugin.id) + '" role="button" tabindex="0">' +
        '<span class="plugins-status-dot ' + meta.dot + '" title="' + escapeAttr(meta.label) + '"></span>' +
        (iconUrl ? '<img class="plugins-row-icon" src="' + escapeAttr(iconUrl) + '" alt="" onerror="this.classList.add(\'hidden\')">' : '<div class="plugins-row-icon"></div>') +
        '<div class="plugins-row-main">' +
        '<div class="plugins-row-title">' +
        '<span>' + escapeHtml(plugin.name || plugin.path) + '</span>' +
        '<span class="plugins-badge">v' + escapeHtml(plugin.version || '-') + '</span>' +
        '<span class="plugins-badge">' + escapeHtml(typeLabel(plugin.plugin_type)) + '</span>' +
        '<span class="plugins-badge ' + meta.badge + '">' + escapeHtml(meta.label) + '</span>' +
        (updateAvail ? '<span class="plugins-badge status-warn">' + t('plugins.hasUpdate') + '</span>' : '') +
        '</div>' +
        '<div class="plugins-row-desc">' + escapeHtml(plugin.description || '') + '</div>' +
        err +
        '</div>' +
        '<div class="plugins-row-actions">' +
        '<button type="button" class="plugins-icon-btn" data-action="config" data-id="' + escapeAttr(plugin.id) + '" title="' + escapeAttr(t('plugins.config')) + '">&#9881;</button>' +
        '<button type="button" class="plugins-icon-btn' + (updateAvail ? ' has-update' : '') + '" data-action="update" data-id="' + escapeAttr(plugin.id) + '" title="' + escapeAttr(t('plugins.update')) + '"' + (acting ? ' disabled' : '') + '>&#8593;</button>' +
        '<label class="config-toggle" title="' + escapeAttr(plugin.enabled ? t('plugins.disable') : t('plugins.enable')) + '">' +
        '<input type="checkbox" data-action="toggle" data-id="' + escapeAttr(plugin.id) + '"' + (plugin.enabled ? ' checked' : '') + (acting ? ' disabled' : '') + '>' +
        '<span class="toggle-slider"></span></label>' +
        '<button type="button" class="plugins-icon-btn" data-action="uninstall" data-path="' + escapeAttr(plugin.path) + '" data-id="' + escapeAttr(plugin.id) + '" title="' + escapeAttr(t('plugins.uninstall')) + '"' + (acting ? ' disabled' : '') + '>&#128465;</button>' +
        '</div></div>';
    });
    list.innerHTML = html;
  }

  function renderMarket() {
    var grid = el('pluginsMarketGrid');
    if (!grid) return;
    var query = el('pluginsMarketSearch') ? String(el('pluginsMarketSearch').value || '').trim().toLowerCase() : '';
    var typeFilter = el('pluginsMarketType') ? el('pluginsMarketType').value : '';
    var sortBy = el('pluginsMarketSort') ? el('pluginsMarketSort').value : 'name';
    var showInstalled = el('pluginsMarketShowInstalled') ? el('pluginsMarketShowInstalled').checked : false;
    var installedIds = {};
    _plugins.forEach(function (p) { if (p.id) installedIds[p.id] = p; });

    var items = _market.filter(function (item) {
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

    if (!items.length) {
      grid.innerHTML = '<div class="plugins-empty col-span-full">' + t('plugins.empty') + '</div>';
      return;
    }

    var html = '';
    items.forEach(function (item) {
      var manifest = item.manifest || {};
      var id = item.id || manifest.id || '';
      var installed = installedIds[id];
      var compatible = isCompatible(manifest);
      var repo = manifest.urls && manifest.urls.repository ? manifest.urls.repository : (manifest.repository_url || '');
      var icon = item.assets && item.assets.icon_64 ? item.assets.icon_64 : '';
      var iconLocal = id ? '/v1/admin/plugins/icon/' + encodeURIComponent(id) : '';
      html += '<div class="plugins-market-card">' +
        '<div class="flex items-start gap-2">' +
        '<img class="plugins-row-icon" src="' + escapeAttr(icon || iconLocal) + '" alt="" onerror="this.style.visibility=\'hidden\'">' +
        '<div class="flex-1 min-w-0">' +
        '<div class="font-semibold truncate">' + escapeHtml(manifest.name || id) + '</div>' +
        '<div class="text-xs text-muted">' + escapeHtml(manifest.version || '') + ' · ' + escapeHtml(typeLabel(manifest.plugin_type)) + '</div>' +
        '</div></div>' +
        '<div class="text-xs text-muted line-clamp-3">' + escapeHtml(manifest.description || '') + '</div>' +
        '<div class="flex flex-wrap gap-1 mt-auto">' +
        '<button type="button" class="cursor-pointer text-xs rounded-lg px-2 py-1 border border-border bg-panel" data-market-action="detail" data-id="' + escapeAttr(id) + '">' + t('plugins.readme') + '</button>' +
        '<button type="button" class="cursor-pointer text-xs rounded-lg px-2 py-1 border border-border bg-panel" data-market-action="like" data-id="' + escapeAttr(id) + '">' + t('plugins.like') + '</button>';
      if (!installed && repo && compatible) {
        html += '<button type="button" class="cursor-pointer text-xs rounded-lg px-2 py-1 border border-accent text-accent bg-panel" data-market-action="install" data-url="' + escapeAttr(repo) + '" data-id="' + escapeAttr(id) + '">' + t('plugins.install') + '</button>';
      } else if (installed) {
        html += '<span class="text-xs text-ok px-2 py-1">' + t('plugins.installed') + '</span>';
      } else if (!compatible) {
        html += '<span class="text-xs text-warn px-2 py-1">' + t('plugins.incompatible') + '</span>';
      }
      html += '</div></div>';
    });
    grid.innerHTML = html;
  }

  function showModal(modalId, show) {
    var modal = el(modalId);
    if (!modal) return;
    modal.classList.toggle('hidden', !show);
    modal.classList.toggle('flex', show);
  }

  function showMainView(showEditor) {
    var main = el('pluginsMainView');
    var editor = el('pluginsEditorView');
    if (main) main.classList.toggle('hidden', showEditor);
    if (editor) editor.classList.toggle('hidden', !showEditor);
  }

  function setEditorTab(tab) {
    _editorTab = tab;
    document.querySelectorAll('.plugins-editor-tab').forEach(function (node) {
      node.classList.toggle('active', node.getAttribute('data-editor-tab') === tab);
    });
    var panes = { visual: 'pluginsEditorVisual', source: 'pluginsEditorSource', detail: 'pluginsEditorDetail' };
    Object.keys(panes).forEach(function (key) {
      var pane = el(panes[key]);
      if (pane) pane.classList.toggle('hidden', key !== tab);
    });
  }

  function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj || {}));
  }

  function renderPluginConfigVisual(schema, config) {
    var grid = el('pluginsConfigGrid');
    var tabs = el('pluginsConfigSectionTabs');
    if (!grid) return;
    if (typeof window.renderEmbeddedConfigPanel === 'function') {
      if (_editorPanelHandle && typeof _editorPanelHandle.destroy === 'function') {
        _editorPanelHandle.destroy();
      }
      _editorPanelId = 'plugin-' + _editorPluginId;
      _editorPanelHandle = window.renderEmbeddedConfigPanel({
        panelId: _editorPanelId,
        container: grid,
        tabsContainer: tabs,
        jsonSchema: schema || {},
        config: config,
        onChange: function(cfg) { _editorDraft = cfg; }
      });
      return;
    }
    grid.innerHTML = '<div class="plugins-empty">' + t('plugins.noSchema') + '</div>';
  }

  async function openEditor(pluginId) {
    _editorPluginId = pluginId;
    _editorPlugin = _plugins.find(function (p) { return p.id === pluginId; }) || null;
    if (!_editorPlugin) return;

    showMainView(true);
    setEditorTab('visual');

    var title = el('pluginsEditorTitle');
    var meta = el('pluginsEditorMeta');
    var icon = el('pluginsEditorIcon');
    var sw = el('pluginsEditorSwitch');
    if (title) title.textContent = _editorPlugin.name || pluginId;
    if (meta) meta.textContent = pluginId + ' · v' + (_editorPlugin.version || '-') + ' · ' + typeLabel(_editorPlugin.plugin_type);
    if (icon) {
      icon.src = '/v1/admin/plugins/icon/' + encodeURIComponent(pluginId);
      icon.classList.remove('hidden');
      icon.onerror = function () { icon.classList.add('hidden'); };
    }
    if (sw) sw.checked = !!_editorPlugin.enabled;

    var msg = el('pluginsEditorMessage');
    if (msg) msg.textContent = t('plugins.loading');

    try {
      var bundle = await Api.fetchJson('/v1/admin/plugins/config/' + encodeURIComponent(pluginId) + '/bundle');
      if (!bundle.success) throw new Error(bundle.error || 'bundle failed');
      _editorBundle = bundle;
      _editorDraft = deepClone(bundle.config || {});
      var editor = el('pluginsConfigEditor');
      if (editor) editor.value = bundle.raw_config || '';
      renderPluginConfigVisual(bundle.schema || {}, _editorDraft);
      if (msg) msg.textContent = bundle.message || '';
      await loadEditorDetail(pluginId);
    } catch (err) {
      if (msg) msg.textContent = t('plugins.loadFailed', { error: err.message || String(err) });
    }
  }

  async function loadEditorDetail(pluginId) {
    var readme = el('pluginsEditorReadme');
    var changelog = el('pluginsEditorChangelog');
    if (readme) readme.textContent = t('plugins.loading');
    if (changelog) changelog.textContent = '';
    try {
      var resp = await Api.fetchJson('/v1/admin/plugins/local-readme/' + encodeURIComponent(pluginId));
      if (readme) {
        readme.textContent = (resp && resp.success && resp.data) ? resp.data : t('plugins.noReadme');
      }
      var ch = await Api.fetchJson('/v1/admin/plugins/local-changelog/' + encodeURIComponent(pluginId));
      if (changelog) {
        changelog.textContent = (ch && ch.success && ch.data) ? ch.data : t('plugins.noChangelog');
      }
      var runtime = el('pluginsEditorRuntime');
      if (runtime) {
        try {
          var comp = await Api.fetchJson('/v1/admin/plugins/runtime/components/' + encodeURIComponent(pluginId));
          var items = (comp && comp.components) ? comp.components : [];
          runtime.textContent = items.length
            ? items.map(function (c) { return (c.type || 'component') + ': ' + (c.id || c.name || ''); }).join('\n')
            : t('plugins.noRuntimeComponents');
        } catch (e2) {
          runtime.textContent = '';
        }
      }
    } catch (e) {
      if (readme) readme.textContent = t('plugins.loadFailed', { error: e.message || String(e) });
    }
  }

  function closeEditor() {
    if (_editorPanelHandle && typeof _editorPanelHandle.destroy === 'function') {
      _editorPanelHandle.destroy();
    }
    _editorPanelHandle = null;
    _editorPanelId = '';
    _editorPluginId = '';
    _editorPlugin = null;
    _editorBundle = null;
    showMainView(false);
  }

  async function saveConfig() {
    if (!_editorPluginId) return;
    var msg = el('pluginsEditorMessage');
    try {
      if (_editorTab === 'source') {
        var editor = el('pluginsConfigEditor');
        await Api.put('/v1/admin/plugins/config/' + encodeURIComponent(_editorPluginId), { raw: editor ? editor.value : '' });
      } else {
        if (_editorPanelHandle && typeof _editorPanelHandle.getConfig === 'function') {
          _editorDraft = _editorPanelHandle.getConfig();
        }
        await Api.put('/v1/admin/plugins/config/' + encodeURIComponent(_editorPluginId), { config: _editorDraft });
        var editor2 = el('pluginsConfigEditor');
        if (editor2) {
          var refreshed = await Api.fetchJson('/v1/admin/plugins/config/' + encodeURIComponent(_editorPluginId));
          editor2.value = refreshed.raw || '';
        }
      }
      if (msg) msg.textContent = t('common.saved');
    } catch (err) {
      if (msg) msg.textContent = t('plugins.actionFailed', { error: err.message || String(err) });
    }
  }

  async function resetConfig() {
    if (!_editorPluginId) return;
    if (!window.confirm(t('plugins.resetConfirm'))) return;
    var msg = el('pluginsEditorMessage');
    try {
      var resp = await Api.post('/v1/admin/plugins/config/' + encodeURIComponent(_editorPluginId) + '/reset', {});
      if (!resp.success) throw new Error(resp.error || 'reset failed');
      _editorDraft = deepClone(resp.config || {});
      var editor = el('pluginsConfigEditor');
      if (editor) editor.value = resp.raw_config || '';
      if (_editorBundle) renderPluginConfigVisual(_editorBundle.schema || {}, _editorDraft);
      if (msg) msg.textContent = t('plugins.resetOk');
    } catch (err) {
      if (msg) msg.textContent = t('plugins.actionFailed', { error: err.message || String(err) });
    }
  }

  async function loadHostVersion() {
    try {
      _hostVersion = await Api.fetchJson('/v1/admin/plugins/version');
    } catch (e) {
      _hostVersion = { version: '0.0.0', version_major: 0, version_minor: 0, version_patch: 0 };
    }
  }

  function indexMarket() {
    _marketById = {};
    _market.forEach(function (item) {
      var id = item.id || (item.manifest && item.manifest.id);
      if (id) _marketById[id] = item;
    });
  }

  async function loadMarket() {
    var statusEl = el('pluginsStatus');
    if (statusEl) statusEl.textContent = t('plugins.loading');
    try {
      if (!_marketConfig) {
        _marketConfig = await Api.fetchJson('/v1/admin/plugins/market-config');
      }
      var cfg = _marketConfig || {};
      var resp = await Api.post('/v1/admin/plugins/fetch-raw', {
        owner: cfg.owner,
        repo: cfg.repo,
        branch: cfg.branch,
        file_path: cfg.details_file || 'plugin_details.json',
      });
      if (!resp.success || !resp.data) throw new Error(resp.error || 'fetch failed');
      _market = JSON.parse(resp.data);
      indexMarket();
      renderMarket();
      if (_activeTab === 'installed') renderList();
      if (statusEl) statusEl.textContent = t('plugins.ready');
    } catch (err) {
      renderMarket();
      if (statusEl) statusEl.textContent = t('plugins.loadFailed', { error: err.message || String(err) });
    }
  }

  async function refresh() {
    var statusEl = el('pluginsStatus');
    if (statusEl) statusEl.textContent = t('plugins.loading');
    try {
      await loadHostVersion();
      var listResp = await Api.fetchJson('/v1/admin/plugins/installed');
      _plugins = (listResp && listResp.plugins) ? listResp.plugins : [];
      var statusResp = await Api.fetchJson('/v1/admin/plugins/status');
      renderSummary(statusResp && statusResp.summary);
      renderList();
      if (_activeTab === 'market') renderMarket();
      else if (_market.length) renderList();
      if (_editorPluginId) {
        _editorPlugin = _plugins.find(function (p) { return p.id === _editorPluginId; }) || _editorPlugin;
        var sw = el('pluginsEditorSwitch');
        if (sw && _editorPlugin) sw.checked = !!_editorPlugin.enabled;
      }
      if (statusEl) statusEl.textContent = t('plugins.ready');
    } catch (err) {
      if (statusEl) statusEl.textContent = t('plugins.loadFailed', { error: err.message || String(err) });
    }
  }

  async function installFromGit(url, ref, pluginId) {
    var statusEl = el('pluginsStatus');
    if (statusEl) statusEl.textContent = t('plugins.installing');
    var body = { url: url };
    if (ref) body.ref = ref;
    if (pluginId) body.plugin_id = pluginId;
    try {
      var resp = await runWithProgress(Api.post('/v1/admin/plugins/install', body), t('plugins.installing'));
      if (statusEl) statusEl.textContent = t('plugins.installOk');
      if (resp && resp.summary) renderSummary(resp.summary);
      showModal('pluginsInstallModal', false);
      await refresh();
    } catch (err) {
      if (statusEl) statusEl.textContent = t('plugins.installFailed', { error: err.message || String(err) });
    }
  }

  async function togglePlugin(pluginId) {
    _actingPluginId = pluginId;
    renderList();
    var statusEl = el('pluginsStatus');
    try {
      var resp = await runWithProgress(Api.post('/v1/admin/plugins/toggle', { plugin_id: pluginId }), t('plugins.reloading'));
      if (statusEl) statusEl.textContent = t('plugins.toggleOk');
      if (resp && resp.summary) renderSummary(resp.summary);
      await refresh();
    } catch (err) {
      if (statusEl) statusEl.textContent = t('plugins.actionFailed', { error: err.message || String(err) });
    } finally {
      _actingPluginId = '';
      renderList();
    }
  }

  async function updatePlugin(pluginId) {
    _actingPluginId = pluginId;
    renderList();
    var statusEl = el('pluginsStatus');
    try {
      var resp = await runWithProgress(Api.post('/v1/admin/plugins/update', { plugin_id: pluginId }), t('plugins.updating'));
      if (statusEl) statusEl.textContent = t('plugins.updateOk');
      if (resp && resp.summary) renderSummary(resp.summary);
      await refresh();
    } catch (err) {
      if (statusEl) statusEl.textContent = t('plugins.actionFailed', { error: err.message || String(err) });
    } finally {
      _actingPluginId = '';
      renderList();
    }
  }

  async function uninstallPlugin(pluginId, folder) {
    if (!window.confirm(t('plugins.uninstallConfirm', { path: folder }))) return;
    _actingPluginId = pluginId;
    renderList();
    var statusEl = el('pluginsStatus');
    try {
      var resp = await runWithProgress(Api.post('/v1/admin/plugins/uninstall', { path: folder }), t('plugins.uninstalling'));
      if (statusEl) statusEl.textContent = t('plugins.uninstallOk');
      if (resp && resp.summary) renderSummary(resp.summary);
      if (_editorPluginId === pluginId) closeEditor();
      await refresh();
    } catch (err) {
      if (statusEl) statusEl.textContent = t('plugins.actionFailed', { error: err.message || String(err) });
    } finally {
      _actingPluginId = '';
      renderList();
    }
  }

  function openInstallDialog(url, pluginId) {
    _installTarget = { url: url || '', pluginId: pluginId || '' };
    var urlInput = el('pluginsInstallUrl');
    var refInput = el('pluginsInstallRef');
    if (urlInput) urlInput.value = url || '';
    if (refInput) refInput.value = '';
    showModal('pluginsInstallModal', true);
  }

  async function handleListClick(event) {
    var toggle = event.target.closest('[data-action="toggle"]');
    if (toggle) {
      event.stopPropagation();
      await togglePlugin(toggle.getAttribute('data-id'));
      return;
    }
    var btn = event.target.closest('[data-action]');
    if (btn) {
      event.stopPropagation();
      var action = btn.getAttribute('data-action');
      var pluginId = btn.getAttribute('data-id');
      if (action === 'config') await openEditor(pluginId);
      else if (action === 'update') await updatePlugin(pluginId);
      else if (action === 'uninstall') await uninstallPlugin(pluginId, btn.getAttribute('data-path'));
      return;
    }
    var row = event.target.closest('[data-plugin-id]');
    if (row) await openEditor(row.getAttribute('data-plugin-id'));
  }

  async function loadMirrors() {
    var list = el('pluginsMirrorsList');
    if (!list) return;
    list.textContent = t('plugins.loading');
    try {
      var resp = await Api.fetchJson('/v1/admin/plugins/mirrors');
      var mirrors = (resp && resp.mirrors) ? resp.mirrors : [];
      if (!mirrors.length) {
        list.innerHTML = '<div class="plugins-empty">' + t('plugins.empty') + '</div>';
        return;
      }
      var html = '';
      mirrors.forEach(function (m) {
        html += '<div class="flex flex-wrap gap-2 items-center py-2 border-t border-border">' +
          '<span class="font-semibold text-sm">' + escapeHtml(m.name || m.id) + '</span>' +
          '<span class="text-xs text-muted flex-1">' + escapeHtml(m.base_url || '') + '</span>' +
          '<button type="button" class="plugins-icon-btn" data-mirror-delete="' + escapeAttr(m.id) + '">&#128465;</button></div>';
      });
      list.innerHTML = html;
    } catch (err) {
      list.textContent = t('plugins.loadFailed', { error: err.message || String(err) });
    }
  }

  async function addMirror() {
    var nameInput = el('pluginsMirrorName');
    var urlInput = el('pluginsMirrorUrl');
    var name = nameInput ? nameInput.value.trim() : '';
    var base_url = urlInput ? urlInput.value.trim() : '';
    if (!name || !base_url) return;
    await Api.post('/v1/admin/plugins/mirrors', { name: name, base_url: base_url });
    if (nameInput) nameInput.value = '';
    if (urlInput) urlInput.value = '';
    await loadMirrors();
  }

  async function deleteMirror(mirrorId) {
    await Api.fetchJson('/v1/admin/plugins/mirrors/' + encodeURIComponent(mirrorId), { method: 'DELETE' });
    await loadMirrors();
  }

  async function handleMarketAction(event) {
    var btn = event.target.closest('[data-market-action]');
    if (!btn) return;
    var action = btn.getAttribute('data-market-action');
    if (action === 'install') {
      openInstallDialog(btn.getAttribute('data-url'), btn.getAttribute('data-id'));
      return;
    }
    if (action === 'detail') {
      var pluginId = btn.getAttribute('data-id');
      var marketItem = _marketById[pluginId];
      var installed = _plugins.find(function (p) { return p.id === pluginId; });
      if (installed) {
        await openEditor(pluginId);
        setEditorTab('detail');
      } else if (marketItem) {
        var desc = marketItem.manifest ? marketItem.manifest.description : '';
        var changelog = marketItem.changelog || '';
        alert(desc + '\n\n' + changelog);
      }
      return;
    }
    if (action === 'like') {
      var likeId = btn.getAttribute('data-id');
      try {
        await Api.post('/v1/admin/plugins/stats/' + encodeURIComponent(likeId) + '/like', {});
        btn.textContent = t('plugins.liked');
      } catch (e) { /* ignore */ }
    }
  }

  function bindEvents() {
    var refreshBtn = el('pluginsRefreshBtn');
    var list = el('pluginsList');
    var tabInstalled = el('pluginsTabInstalled');
    var tabMarket = el('pluginsTabMarket');
    var tabMirrors = el('pluginsTabMirrors');
    var mirrorAdd = el('pluginsMirrorAdd');
    var mirrorsList = el('pluginsMirrorsList');
    var search = el('pluginsSearch');
    var showUpdates = el('pluginsShowUpdatesOnly');
    var marketRefresh = el('pluginsMarketRefreshBtn');
    var marketSearch = el('pluginsMarketSearch');
    var marketType = el('pluginsMarketType');
    var marketSort = el('pluginsMarketSort');
    var marketShowInstalled = el('pluginsMarketShowInstalled');
    var marketGrid = el('pluginsMarketGrid');
    var installFromGitBtn = el('pluginsInstallFromGitBtn');
    var installBtn = el('pluginsInstallBtn');
    var installClose = el('pluginsInstallClose');
    var installCancel = el('pluginsInstallCancel');
    var editorBack = el('pluginsEditorBack');
    var editorSwitch = el('pluginsEditorSwitch');
    var editorUpdate = el('pluginsEditorUpdate');
    var editorUninstall = el('pluginsEditorUninstall');
    var configSave = el('pluginsConfigSave');
    var configReset = el('pluginsConfigReset');

    if (refreshBtn) refreshBtn.addEventListener('click', refresh);
    if (list) {
      list.addEventListener('click', handleListClick);
      list.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') {
          var row = e.target.closest('[data-plugin-id]');
          if (row) { e.preventDefault(); openEditor(row.getAttribute('data-plugin-id')); }
        }
      });
    }
    if (tabInstalled) tabInstalled.addEventListener('click', function () { setTab('installed'); });
    if (tabMarket) tabMarket.addEventListener('click', function () { setTab('market'); });
    if (tabMirrors) tabMirrors.addEventListener('click', function () { setTab('mirrors'); });
    if (mirrorAdd) mirrorAdd.addEventListener('click', addMirror);
    if (mirrorsList) mirrorsList.addEventListener('click', function (e) {
      var del = e.target.closest('[data-mirror-delete]');
      if (del) deleteMirror(del.getAttribute('data-mirror-delete'));
    });
    if (search) search.addEventListener('input', function () { _searchQuery = search.value; renderList(); });
    if (showUpdates) showUpdates.addEventListener('change', function () { _showUpdatesOnly = showUpdates.checked; renderList(); });
    if (marketRefresh) marketRefresh.addEventListener('click', loadMarket);
    if (marketSearch) marketSearch.addEventListener('input', renderMarket);
    if (marketType) marketType.addEventListener('change', renderMarket);
    if (marketSort) marketSort.addEventListener('change', renderMarket);
    if (marketShowInstalled) marketShowInstalled.addEventListener('change', renderMarket);
    if (marketGrid) marketGrid.addEventListener('click', handleMarketAction);
    if (installFromGitBtn) installFromGitBtn.addEventListener('click', function () { openInstallDialog('', ''); });
    if (installBtn) installBtn.addEventListener('click', function () {
      var urlInput = el('pluginsInstallUrl');
      var refInput = el('pluginsInstallRef');
      var url = urlInput ? String(urlInput.value || '').trim() : _installTarget.url;
      if (!url) {
        var statusEl = el('pluginsStatus');
        if (statusEl) statusEl.textContent = t('plugins.urlRequired');
        return;
      }
      var ref = refInput && refInput.value.trim() ? refInput.value.trim() : '';
      installFromGit(url, ref, _installTarget.pluginId);
    });
    if (installClose) installClose.addEventListener('click', function () { showModal('pluginsInstallModal', false); });
    if (installCancel) installCancel.addEventListener('click', function () { showModal('pluginsInstallModal', false); });
    if (editorBack) editorBack.addEventListener('click', closeEditor);
    if (editorSwitch) editorSwitch.addEventListener('change', function () {
      if (_editorPluginId) togglePlugin(_editorPluginId);
    });
    if (editorUpdate) editorUpdate.addEventListener('click', function () {
      if (_editorPluginId) updatePlugin(_editorPluginId);
    });
    if (editorUninstall) editorUninstall.addEventListener('click', function () {
      if (_editorPlugin && _editorPluginId) uninstallPlugin(_editorPluginId, _editorPlugin.path);
    });
    if (configSave) configSave.addEventListener('click', saveConfig);
    if (configReset) configReset.addEventListener('click', resetConfig);
    document.querySelectorAll('.plugins-editor-tab').forEach(function (node) {
      node.addEventListener('click', function () {
        setEditorTab(node.getAttribute('data-editor-tab'));
      });
    });
  }

  function init() {
    if (_loaded) {
      refresh();
      return;
    }
    _loaded = true;
    bindEvents();
    setTab('installed');
    showMainView(false);
    refresh();
    loadMarket();
  }

  return {
    init: init,
    refresh: refresh,
    onProgress: onProgressFromSocket,
  };
})();

function initPluginsPanel() {
  PluginsPanel.init();
}

if (typeof window !== 'undefined') {
  window.PluginsPanel = PluginsPanel;
}
