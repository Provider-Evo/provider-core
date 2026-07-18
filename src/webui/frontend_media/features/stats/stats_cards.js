/**
 * StatsCards -- pure HTML-string card builders + format helpers used by
 * features/stats/stats.js to render the stats grid. Split out so each
 * builder function stays small and independently testable.
 */
var StatsCards = (function () {
  var S = {};

  function fmt(n) {
    if (n == null) return '-';
    if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
    return String(n);
  }

  function fmtUptime(s) {
    if (!s) return '-';
    var d = Math.floor(s / 86400);
    var h = Math.floor((s % 86400) / 3600);
    var m = Math.floor((s % 3600) / 60);
    if (d > 0) return d + 'd ' + h + 'h';
    if (h > 0) return h + 'h ' + m + 'm';
    return m + 'm';
  }

  function metricCard(title, value, sub) {
    return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">'
      + '<div class="text-[13px] text-muted m-0 mb-2">' + title + '</div>'
      + '<div class="text-2xl font-bold">' + value + '</div>'
      + (sub || '')
      + '</div>';
  }

  function sub(text, colorClass) {
    var cls = colorClass ? 'text-' + colorClass : 'text-muted';
    return '<div class="text-[12px] ' + cls + ' mt-1">' + text + '</div>';
  }

  S.fmt = fmt;
  S.fmtUptime = fmtUptime;
  S.metricCard = metricCard;
  S.sub = sub;

  // timelineCard/statusCard/rankCard/recentCard attached from
  // stats_cardshelpers.js (must load before this file, see lazy_assets.js).
  _attachStatsCardsMethods(S);

  return S;
})();
