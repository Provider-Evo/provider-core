/**
 * Feature: 请求统计 — 独立的统计面板模块。
 *
 * 职责：
 * - 从 /v1/webui/stats 拉取数据
 * - 渲染统计卡片（请求量、错误率、延迟、Token 用量）
 * - 渲染时间线 sparkline
 * - 渲染 Top 平台 / Top 模型
 * - 渲染系统资源
 */
var StatsFeature = (function () {
  var _container = null;
  var _timer = null;
  var _interval = 3000;
  var _lastData = null;

  function init() {
    _container = document.getElementById('statsGrid');
    if (!_container) return;
    // Poll: refresh when stats tab is visible
    _timer = setInterval(function () {
      var panel = document.getElementById('tab-stats');
      if (panel && panel.classList.contains('active')) {
        refresh();
      }
    }, _interval);
    // Initial refresh if already visible
    var panel = document.getElementById('tab-stats');
    if (panel && panel.classList.contains('active')) {
      refresh();
    }
  }

  async function refresh() {
    if (!_container) return;
    try {
      var data = await Api.fetchJson('/v1/webui/stats');
      _lastData = data;
      render(data);
    } catch (e) {
      _container.innerHTML = '<div class="text-err p-4">' + t('stats.loadFailed', { error: e.message }) + '</div>';
    }
  }

  function render(d) {
    var lat = d.latency || {};
    var tok = d.tokens || {};
    var sys = d.system || {};
    var html = [];

    // Row 1: Key metrics
    html.push(_metricCard(t('stats.totalRequests'), _fmt(d.total), _sub(t('stats.reqPerSec', { rps: d.rps }))));
    html.push(_metricCard(t('stats.errorRate'), d.error_rate + '%', _sub(t('stats.errorsCount', { count: d.errors }), d.error_rate > 5 ? 'err' : 'ok')));
    html.push(_metricCard(t('stats.p95Latency'), lat.p95 + 'ms', _sub(t('stats.latencySub', { p50: lat.p50, p99: lat.p99 }))));
    html.push(_metricCard(t('stats.tokenUsage'), _fmt(tok.total), _sub(t('stats.tokenSub', { input: _fmt(tok.input), output: _fmt(tok.output) }))));
    html.push(_metricCard(t('stats.uptime'), _fmtUptime(d.uptime_seconds), _sub(t('stats.pidSub', { pid: (sys.pid || '-') }))));
    html.push(_metricCard(t('stats.memory'), sys.memory_mb ? sys.memory_mb + ' MB' : '-', _sub(t('stats.cpuSub', { count: (sys.cpu_count || '-') }))));

    // Row 2: Timeline sparkline
    html.push(_timelineCard(d.timeline || []));

    // Row 3: Status code distribution
    html.push(_statusCard(d.by_status || {}));

    // Row 4: Top platforms + models
    html.push(_rankCard(t('stats.topPlatforms'), d.top_platforms || []));
    html.push(_rankCard(t('stats.topModels'), d.top_models || []));

    // Row 5: Recent requests
    html.push(_recentCard(d.recent || []));

    _container.innerHTML = html.join('');
  }

  // -- Card builders --

  function _metricCard(title, value, sub) {
    return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">'
      + '<div class="text-[13px] text-muted m-0 mb-2">' + title + '</div>'
      + '<div class="text-2xl font-bold">' + value + '</div>'
      + (sub || '')
      + '</div>';
  }

  function _sub(text, colorClass) {
    var cls = colorClass ? 'text-' + colorClass : 'text-muted';
    return '<div class="text-[12px] ' + cls + ' mt-1">' + text + '</div>';
  }

  function _timelineCard(buckets) {
    if (!buckets.length) {
      return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt col-span-full">'
        + '<div class="text-[13px] text-muted mb-2">' + t('stats.timeline') + '</div>'
        + '<div class="text-muted text-[13px]">' + t('stats.noTimelineData') + '</div></div>';
    }
    var maxR = Math.max.apply(null, buckets.map(function (b) { return b.r; })) || 1;
    var bars = buckets.slice(-60).map(function (b) {
      var h = Math.max(2, Math.round((b.r / maxR) * 48));
      var errH = b.e > 0 ? Math.max(1, Math.round((b.e / maxR) * 48)) : 0;
      var color = b.e > 0 ? 'bg-err' : 'bg-accent';
      return '<div class="timeline-bar" style="height:' + h + 'px" title="' + b.r + ' req, ' + b.e + ' err">'
        + (errH > 0 ? '<div class="timeline-bar-err" style="height:' + errH + 'px"></div>' : '')
        + '</div>';
    }).join('');
    return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt col-span-full">'
      + '<div class="text-[13px] text-muted mb-2">' + t('stats.timelineWindows', { count: Math.min(buckets.length, 60) }) + '</div>'
      + '<div class="timeline-chart">' + bars + '</div></div>';
  }

  function _statusCard(byStatus) {
    var entries = Object.entries(byStatus).sort(function (a, b) { return b[1] - a[1]; });
    if (!entries.length) return '';
    var total = entries.reduce(function (s, e) { return s + e[1]; }, 0);
    var rows = entries.map(function (e) {
      var pct = total > 0 ? (e[1] / total * 100).toFixed(1) : '0';
      var cls = parseInt(e[0]) >= 400 ? 'text-err' : 'text-ok';
      return '<div class="flex justify-between items-center text-[13px]">'
        + '<span class="font-mono ' + cls + '">' + e[0] + '</span>'
        + '<span class="text-muted">' + e[1] + ' (' + pct + '%)</span>'
        + '</div>';
    }).join('');
    return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">'
      + '<div class="text-[13px] text-muted m-0 mb-2">' + t('stats.statusDistribution') + '</div>' + rows + '</div>';
  }

  function _rankCard(title, items) {
    if (!items.length) return '';
    var maxC = items[0] ? items[0].count : 1;
    var rows = items.map(function (item, i) {
      var pct = Math.round((item.count / maxC) * 100);
      return '<div class="flex items-center gap-2 text-[13px] mb-1.5">'
        + '<span class="text-muted w-5 text-right">' + (i + 1) + '</span>'
        + '<span class="flex-1 truncate" title="' + item.name + '">' + item.name + '</span>'
        + '<div class="w-20 h-2 bg-panel rounded-full overflow-hidden">'
        + '<div class="h-full bg-accent rounded-full" style="width:' + pct + '%"></div></div>'
        + '<span class="text-muted w-12 text-right">' + _fmt(item.count) + '</span>'
        + '</div>';
    }).join('');
    return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">'
      + '<div class="text-[13px] text-muted m-0 mb-2">' + title + '</div>' + rows + '</div>';
  }

  function _recentCard(recent) {
    if (!recent.length) return '';
    var rows = recent.slice(-10).reverse().map(function (r) {
      var statusCls = r.s >= 400 ? 'text-err' : 'text-ok';
      var time = new Date(r.t * 1000);
      var ts = time.getHours().toString().padStart(2, '0') + ':'
        + time.getMinutes().toString().padStart(2, '0') + ':'
        + time.getSeconds().toString().padStart(2, '0');
      return '<div class="flex items-center gap-2 text-[12px] font-mono">'
        + '<span class="text-muted">' + ts + '</span>'
        + '<span class="' + statusCls + '">' + r.s + '</span>'
        + '<span class="flex-1 truncate">' + (r.m || '-') + '</span>'
        + '<span class="text-muted">' + r.l + 'ms</span>'
        + '</div>';
    }).join('');
    return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift col-span-full">'
      + '<div class="text-[13px] text-muted m-0 mb-2">' + t('stats.recentRequests') + '</div>' + rows + '</div>';
  }

  // -- Helpers --

  function _fmt(n) {
    if (n == null) return '-';
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
  }

  function _fmtUptime(s) {
    if (!s) return '-';
    var d = Math.floor(s / 86400);
    var h = Math.floor((s % 86400) / 3600);
    var m = Math.floor((s % 3600) / 60);
    if (d > 0) return d + 'd ' + h + 'h';
    if (h > 0) return h + 'h ' + m + 'm';
    return m + 'm';
  }

  return { init: init, refresh: refresh };
})();
