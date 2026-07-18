/**
 * StatsFeature helper builders -- split out of stats.js to keep the
 * facade IIFE under the line cap. Attaches methods onto the shared S
 * state object (holding _container/_lastData/_ws/_reconnectTimer) via
 * _attachStatsFeatureMethods(S).
 */
function _attachStatsFeatureConn(S) {
  function _isStatsVisible() {
    var dash = document.getElementById('tab-dashboard');
    var stats = document.getElementById('tab-stats');
    return (dash && dash.classList.contains('active'))
      || (stats && stats.classList.contains('active'));
  }

  function _connect() {
    if (S._ws && (S._ws.readyState === WebSocket.CONNECTING || S._ws.readyState === WebSocket.OPEN)) return;
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    S._ws = new WebSocket(proto + '//' + location.host + '/v1/webui/ws/stats');
    S._ws.onmessage = function (e) {
      try {
        var msg = JSON.parse(e.data);
        if (msg.type === 'stats' && msg.data) S._applyData(msg.data);
      } catch (err) {}
    };
    S._ws.onclose = function () {
      if (!document.hidden) {
        S._reconnectTimer = setTimeout(_connect, 3000);
      }
    };
    S._ws.onerror = function () {};
  }

  function _applyData(data) {
    S._lastData = data;
    if (!_isStatsVisible()) return;
    var target = document.getElementById('dashboardStatsGrid') || document.getElementById('statsGrid') || S._container;
    if (!target) return;
    S._container = target;
    S.renderTo(target, data, { compact: target.id === 'dashboardStatsGrid' });
  }

  S._isStatsVisible = _isStatsVisible;
  S._connect = _connect;
  S._applyData = _applyData;
}

function _attachStatsFeatureRefresh(S) {
  async function refresh() {
    var target = document.getElementById('dashboardStatsGrid') || document.getElementById('statsGrid') || S._container;
    if (!target) return;
    S._container = target;
    try {
      var data = await Api.fetchJson('/v1/webui/stats');
      S._lastData = data;
      S.renderTo(target, data, { compact: target.id === 'dashboardStatsGrid' });
    } catch (e) {
      target.innerHTML = '<div class="text-err p-4">' + t('stats.loadFailed', { error: e.message }) + '</div>';
    }
  }

  function renderTo(container, d, opts) {
    if (!container) return;
    S._container = container;
    S.render(d, opts || {});
  }

  S.refresh = refresh;
  S.renderTo = renderTo;
}

function _attachStatsFeatureRender(S) {
  function _buildTopMetricsHtml(d) {
    var lat = d.latency || {};
    var tok = d.tokens || {};
    var sys = d.system || {};
    var html = [];
    html.push(StatsCards.metricCard(t('stats.totalRequests'), StatsCards.fmt(d.total), StatsCards.sub(t('stats.reqPerSec', { rps: d.rps }))));
    html.push(StatsCards.metricCard(t('stats.errorRate'), d.error_rate + '%', StatsCards.sub(t('stats.errorsCount', { count: d.errors }), d.error_rate > 5 ? 'err' : 'ok')));
    html.push(StatsCards.metricCard(t('stats.p95Latency'), lat.p95 + 'ms', StatsCards.sub(t('stats.latencySub', { p50: lat.p50, p99: lat.p99 }))));
    html.push(StatsCards.metricCard(t('stats.tokenUsage'), StatsCards.fmt(tok.total), StatsCards.sub(t('stats.tokenSub', { input: StatsCards.fmt(tok.input), output: StatsCards.fmt(tok.output) }))));
    html.push(StatsCards.metricCard(t('stats.uptime'), StatsCards.fmtUptime(d.uptime_seconds), StatsCards.sub(t('stats.pidSub', { pid: (sys.pid || '-') }))));
    html.push(StatsCards.metricCard(t('stats.memory'), sys.memory_mb ? sys.memory_mb + ' MB' : '-', StatsCards.sub(t('stats.cpuSub', { count: (sys.cpu_count || '-') }))));
    return html;
  }

  function render(d, opts) {
    opts = opts || {};
    var compact = !!opts.compact;
    var html = _buildTopMetricsHtml(d);

    html.push(StatsCards.timelineCard(d.timeline || []));
    html.push(StatsCards.statusCard(d.by_status || {}));
    html.push(StatsCards.rankCard(t('stats.topPlatforms'), d.top_platforms || []));
    html.push(StatsCards.rankCard(t('stats.topModels'), d.top_models || []));

    if (!compact) {
      html.push(StatsCards.recentCard(d.recent || []));
    }

    S._container.innerHTML = html.join('');
  }

  S.render = render;
}

function _attachStatsFeatureMethods(S) {
  _attachStatsFeatureConn(S);
  _attachStatsFeatureRefresh(S);
  _attachStatsFeatureRender(S);
}
