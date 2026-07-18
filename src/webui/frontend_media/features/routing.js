/**
 * Build the fallback-chains and circuit-breaker cards for the routing
 * health panel. Split out of refresh() to keep it under the line cap.
 */
function _routingBuildHealthCards(status, config) {
  var fallback = config.fallback || {};
  var chains = fallback.chains || {};
  var circuit = status.circuit || {};
  var html = [];

  var chainNames = Object.keys(chains);
  html.push(_card(t('routing.fallbackChains'), chainNames.length
    ? chainNames.map(function (name) {
      var chain = chains[name] || [];
      return name + ' → ' + (Array.isArray(chain) ? chain.join(', ') : '-');
    })
    : [t('routing.noFallback')]));

  var circuitEntries = Object.entries(circuit);
  if (circuitEntries.length) {
    circuitEntries.forEach(function (entry) {
      var name = entry[0];
      var st = entry[1] || {};
      var open = st.open || st.state === 'open';
      html.push(_card(name, [
        (open ? t('routing.circuitOpen') : t('routing.circuitClosed')),
        t('routing.failures') + ': ' + String(st.failures ?? st.failure_count ?? '-'),
      ], open ? 'warn' : 'ok'));
    });
  } else {
    html.push(_card(t('routing.circuitBreaker'), [t('routing.noCircuitData')]));
  }

  return html;
}

function _card(title, lines, tone) {
  var chip = '';
  if (tone === 'ok') chip = '<span class="ui-chip ui-chip--ok">' + t('routing.healthy') + '</span>';
  if (tone === 'warn') chip = '<span class="ui-chip ui-chip--warn">' + t('routing.degraded') + '</span>';
  var body = (lines || []).map(function (line) {
    return '<div class="text-[13px] text-muted">' + line + '</div>';
  }).join('');
  return '<div class="ui-stat-card">'
    + '<div class="flex justify-between items-start gap-2 mb-2">'
    + '<div class="ui-stat-card__label m-0">' + title + '</div>' + chip + '</div>'
    + body + '</div>';
}

/**
 * Routing — 平台/模型 + 熔断与 fallback 摘要。
 */
var RoutingFeature = (function () {
  var _panel = null;

  function init() {
    _panel = document.getElementById('routingHealthGrid');
    if (!_panel) return;
    refresh();
  }

  async function refresh() {
    if (!_panel) return;
    _panel.innerHTML = '<div class="ui-empty"><p class="ui-empty__desc">' + t('common.loading') + '</p></div>';
    try {
      var status = await Api.fetchJson('/v1/status');
      var summary = (typeof state !== 'undefined' && state.summary) ? state.summary : {};
      var config = summary.config || {};
      var html = [];

      html.push(_card(t('routing.serviceStatus'), [
        t('routing.status') + ': ' + (status.status || '-'),
        t('routing.timestamp') + ': ' + String(status.timestamp || '-'),
      ]));

      html = html.concat(_routingBuildHealthCards(status, config));

      _panel.innerHTML = html.join('');
    } catch (e) {
      _panel.innerHTML = '<div class="ui-empty"><p class="ui-empty__title">' + t('routing.loadFailed', { error: e.message }) + '</p></div>';
    }
  }

  return { init: init, refresh: refresh };
})();

function _initRoutingTab() {
  if (typeof RoutingFeature !== 'undefined') RoutingFeature.init();
  var btn = document.getElementById('routingRefreshBtn');
  if (btn && !btn.dataset.bound) {
    btn.dataset.bound = '1';
    btn.addEventListener('click', function () {
      if (typeof refreshAll === 'function') refreshAll();
      if (typeof RoutingFeature !== 'undefined') RoutingFeature.refresh();
    });
  }
}
