/**
 * 插件管理面板
 */
var PluginsPanel = (function () {
  var _loaded = false;
  var _plugins = [];

  function t(key, vars) {
    if (typeof I18n !== 'undefined' && I18n.t) {
      return I18n.t(key, vars);
    }
    return key;
  }

  function el(id) {
    return document.getElementById(id);
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

  function statusBadge(plugin) {
    if (!plugin.enabled) {
      return '<span class="inline-flex rounded-lg px-2 py-0.5 text-xs bg-panel-soft text-muted">' + t('plugins.statusInactive') + '</span>';
    }
    if (plugin.loaded) {
      return '<span class="inline-flex rounded-lg px-2 py-0.5 text-xs bg-ok/15 text-ok">' + t('plugins.statusLoaded') + '</span>';
    }
    if (plugin.load_status === 'failed') {
      return '<span class="inline-flex rounded-lg px-2 py-0.5 text-xs bg-err/15 text-err">' + t('plugins.statusFailed') + '</span>';
    }
    return '<span class="inline-flex rounded-lg px-2 py-0.5 text-xs bg-warn/15 text-warn">' + t('plugins.statusUnknown') + '</span>';
  }

  function renderSummary(summary) {
    var node = el('pluginsSummary');
    if (!node || !summary) return;
    node.textContent = t('plugins.summary', {
      loaded: summary.loaded || 0,
      failed: summary.failed || 0,
      inactive: summary.inactive || 0,
    });
  }

  function renderTable() {
    var body = el('pluginsTableBody');
    if (!body) return;
    if (!_plugins.length) {
      body.innerHTML = '<tr><td colspan="6" class="px-3 py-4 text-muted text-center">' + t('plugins.empty') + '</td></tr>';
      return;
    }
    var html = '';
    _plugins.forEach(function (plugin) {
      var err = plugin.load_error ? '<div class="text-xs text-err mt-1 break-all">' + escapeHtml(plugin.load_error) + '</div>' : '';
      html += '<tr class="border-t border-border hover:bg-panel-alt/40">' +
        '<td class="px-3 py-2 align-top"><div class="font-semibold">' + escapeHtml(plugin.name || plugin.path) + '</div>' +
        '<div class="text-xs text-muted break-all">' + escapeHtml(plugin.id || '') + '</div></td>' +
        '<td class="px-3 py-2 align-top text-sm">' + escapeHtml(plugin.version || '-') + '</td>' +
        '<td class="px-3 py-2 align-top text-sm">' + escapeHtml(typeLabel(plugin.plugin_type)) + '</td>' +
        '<td class="px-3 py-2 align-top">' + statusBadge(plugin) + err + '</td>' +
        '<td class="px-3 py-2 align-top text-xs text-muted max-w-xs">' + escapeHtml(plugin.description || '') + '</td>' +
        '<td class="px-3 py-2 align-top"><div class="flex flex-wrap gap-1">' +
        '<button class="cursor-pointer text-xs rounded-lg px-2 py-1 border border-border bg-panel hover:bg-panel-alt transition" data-action="toggle" data-id="' + escapeAttr(plugin.id) + '" type="button">' +
        (plugin.enabled ? t('plugins.disable') : t('plugins.enable')) + '</button>' +
        '<button class="cursor-pointer text-xs rounded-lg px-2 py-1 border border-border bg-panel hover:bg-panel-alt transition" data-action="update" data-id="' + escapeAttr(plugin.id) + '" type="button">' + t('plugins.update') + '</button>' +
        '<button class="cursor-pointer text-xs rounded-lg px-2 py-1 border border-err text-err bg-panel hover:bg-err hover:text-white transition" data-action="uninstall" data-path="' + escapeAttr(plugin.path) + '" type="button">' + t('plugins.uninstall') + '</button>' +
        '</div></td></tr>';
    });
    body.innerHTML = html;
  }

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

  async function refresh() {
    var statusEl = el('pluginsStatus');
    if (statusEl) statusEl.textContent = t('plugins.loading');
    try {
      var listResp = await Api.fetchJson('/v1/admin/plugins');
      _plugins = (listResp && listResp.plugins) ? listResp.plugins : [];
      var statusResp = await Api.fetchJson('/v1/admin/plugins/status');
      renderSummary(statusResp && statusResp.summary);
      renderTable();
      if (statusEl) statusEl.textContent = t('plugins.ready');
    } catch (err) {
      if (statusEl) statusEl.textContent = t('plugins.loadFailed', { error: err.message || String(err) });
    }
  }

  async function installFromGit() {
    var urlInput = el('pluginsInstallUrl');
    var refInput = el('pluginsInstallRef');
    var statusEl = el('pluginsStatus');
    var url = urlInput ? String(urlInput.value || '').trim() : '';
    if (!url) {
      if (statusEl) statusEl.textContent = t('plugins.urlRequired');
      return;
    }
    var body = { url: url };
    if (refInput && refInput.value.trim()) {
      body.ref = refInput.value.trim();
    }
    if (statusEl) statusEl.textContent = t('plugins.installing');
    try {
      await Api.post('/v1/admin/plugins/install', body);
      if (urlInput) urlInput.value = '';
      if (refInput) refInput.value = '';
      if (statusEl) statusEl.textContent = t('plugins.installOk');
      await refresh();
    } catch (err) {
      if (statusEl) statusEl.textContent = t('plugins.installFailed', { error: err.message || String(err) });
    }
  }

  async function handleAction(event) {
    var btn = event.target.closest('[data-action]');
    if (!btn) return;
    var action = btn.getAttribute('data-action');
    var statusEl = el('pluginsStatus');
    try {
      if (action === 'toggle') {
        var pluginId = btn.getAttribute('data-id');
        await Api.post('/v1/admin/plugins/toggle', { plugin_id: pluginId });
        if (statusEl) statusEl.textContent = t('plugins.toggleOk');
        await refresh();
      } else if (action === 'update') {
        var updateId = btn.getAttribute('data-id');
        if (statusEl) statusEl.textContent = t('plugins.updating');
        await Api.post('/v1/admin/plugins/update', { plugin_id: updateId });
        if (statusEl) statusEl.textContent = t('plugins.updateOk');
        await refresh();
      } else if (action === 'uninstall') {
        var folder = btn.getAttribute('data-path');
        if (!window.confirm(t('plugins.uninstallConfirm', { path: folder }))) return;
        await Api.post('/v1/admin/plugins/uninstall', { path: folder });
        if (statusEl) statusEl.textContent = t('plugins.uninstallOk');
        await refresh();
      }
    } catch (err) {
      if (statusEl) statusEl.textContent = t('plugins.actionFailed', { error: err.message || String(err) });
    }
  }

  function bindEvents() {
    var refreshBtn = el('pluginsRefreshBtn');
    var installBtn = el('pluginsInstallBtn');
    var table = el('pluginsTableBody');
    if (refreshBtn) refreshBtn.addEventListener('click', refresh);
    if (installBtn) installBtn.addEventListener('click', installFromGit);
    if (table) table.addEventListener('click', handleAction);
  }

  function init() {
    if (_loaded) {
      refresh();
      return;
    }
    _loaded = true;
    bindEvents();
    refresh();
  }

  return { init: init, refresh: refresh };
})();

function initPluginsPanel() {
  PluginsPanel.init();
}
