/**
 * PluginsPanel pure helpers -- version compare/compat checks, status meta,
 * progress rendering, and misc utility functions used by plugins.js.
 * Split out of plugins.js to keep each file under the line-length budget.
 * Attaches onto the shared P object passed in from plugins.js.
 */
function _attachPluginsHelpers(P) {
  _attachPluginsBasics(P);
  _attachPluginsVersionHelpers(P);
  _attachPluginsStatusHelpers(P);
  _attachPluginsProgressHelpers(P);
  _attachPluginsMiscHelpers(P);
}

function _attachPluginsBasics(P) {
  P.t = function t(key, vars) {
    if (typeof i18n !== 'undefined' && i18n.t) return i18n.t(key, vars);
    return key;
  };

  P.el = function el(id) { return document.getElementById(id); };

  P.escapeHtml = function escapeHtml(text) {
    return String(text || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  };

  P.escapeAttr = function escapeAttr(text) {
    return P.escapeHtml(text).replace(/'/g, '&#39;');
  };

  P.typeLabel = function typeLabel(ptype) {
    var map = {
      platform: P.t('plugins.typePlatform'),
      fncall: P.t('plugins.typeFncall'),
      webui: P.t('plugins.typeWebui'),
      coplan: P.t('plugins.typeCoplan'),
      general: P.t('plugins.typeGeneral'),
    };
    return map[ptype] || ptype || '-';
  };
}

function _attachPluginsVersionHelpers(P) {
  P.parseVersionTuple = function parseVersionTuple(version) {
    var parts = String(version || '0.0.0').split('-')[0].split('.');
    return [
      parseInt(parts[0], 10) || 0,
      parseInt(parts[1], 10) || 0,
      parseInt(parts[2], 10) || 0,
    ];
  };

  P.compareVersions = function compareVersions(current, latest) {
    var a = P.parseVersionTuple(current);
    var b = P.parseVersionTuple(latest);
    for (var i = 0; i < 3; i++) {
      if (b[i] > a[i]) return 1;
      if (b[i] < a[i]) return -1;
    }
    return 0;
  };

  P.isCompatible = function isCompatible(manifest) {
    if (!P._hostVersion || !manifest || !manifest.host_application) return true;
    var min = P.parseVersionTuple(manifest.host_application.min_version);
    var current = [P._hostVersion.version_major || 0, P._hostVersion.version_minor || 0, P._hostVersion.version_patch || 0];
    for (var i = 0; i < 3; i++) {
      if (current[i] < min[i]) return false;
      if (current[i] > min[i]) break;
    }
    var maxVersion = manifest.host_application.max_version;
    if (maxVersion) {
      var max = P.parseVersionTuple(maxVersion);
      for (var j = 0; j < 3; j++) {
        if (current[j] > max[j]) return current[0] === max[0];
        if (current[j] < max[j]) break;
      }
    }
    return true;
  };
}

function _attachPluginsStatusHelpers(P) {
  P.statusMeta = function statusMeta(plugin) {
    if (plugin.circuit_status === 'open') {
      return { dot: 'err', badge: 'status-err', label: P.t('plugins.circuitOpen') };
    }
    if (!plugin.enabled) {
      return { dot: 'muted', badge: 'status-warn', label: P.t('plugins.statusInactive') };
    }
    if (plugin.loaded) {
      return { dot: 'ok', badge: 'status-ok', label: P.t('plugins.statusLoaded') };
    }
    if (plugin.load_status === 'failed') {
      return { dot: 'err', badge: 'status-err', label: P.t('plugins.statusFailed') };
    }
    if (plugin.load_status === 'loading') {
      return { dot: 'warn', badge: 'status-warn', label: P.t('plugins.statusLoading') };
    }
    return { dot: 'warn', badge: 'status-warn', label: P.t('plugins.statusUnknown') };
  };

  P.hasMarketUpdate = function hasMarketUpdate(plugin) {
    var market = P._marketById[plugin.id];
    if (!market || !market.manifest) return false;
    return P.compareVersions(plugin.version, market.manifest.version || '') > 0;
  };
}

function _attachPluginsProgressHelpers(P) {
  P.showProgress = function showProgress(visible) {
    var wrap = P.el('pluginsProgressWrap');
    if (wrap) wrap.classList.toggle('hidden', !visible);
  };

  P.renderProgress = function renderProgress(data) {
    if (!data) return;
    var msg = P.el('pluginsProgressMessage');
    var pct = P.el('pluginsProgressPercent');
    var bar = P.el('pluginsProgressBar');
    var statusEl = P.el('pluginsStatus');
    if (msg) msg.textContent = data.message || data.stage || '';
    if (pct) pct.textContent = String(data.progress || 0) + '%';
    if (bar) bar.style.width = String(data.progress || 0) + '%';
    if (statusEl && data.message) statusEl.textContent = data.message;
    if (data.operation && data.operation !== 'idle') P.showProgress(true);
    if (data.progress >= 100 || data.stage === 'error') {
      setTimeout(function () { P.showProgress(false); }, 1200);
    }
  };

  P.onProgressFromSocket = function onProgressFromSocket(data) {
    P.renderProgress(data);
    if (data && (data.progress >= 100 || data.stage === 'error')) {
      P.refresh();
    }
  };

  P.runWithProgress = async function runWithProgress(promise, operationLabel) {
    var statusEl = P.el('pluginsStatus');
    if (statusEl) statusEl.textContent = operationLabel || P.t('plugins.loading');
    P.showProgress(true);
    try {
      return await promise;
    } finally {
      try {
        var data = await Api.fetchJson('/v1/admin/plugins/progress');
        P.renderProgress(data);
      } catch (e) { /* ignore */ }
    }
  };
}

function _attachPluginsMiscHelpers(P) {
  P.deepClone = function deepClone(obj) {
    return JSON.parse(JSON.stringify(obj || {}));
  };

  P.loadHostVersion = async function loadHostVersion() {
    try {
      P._hostVersion = await Api.fetchJson('/v1/admin/plugins/version');
    } catch (e) {
      P._hostVersion = { version: '0.0.0', version_major: 0, version_minor: 0, version_patch: 0 };
    }
  };

  P.indexMarket = function indexMarket() {
    P._marketById = {};
    P._market.forEach(function (item) {
      var id = item.id || (item.manifest && item.manifest.id);
      if (id) P._marketById[id] = item;
    });
  };
}
