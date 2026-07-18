/**
 * StatsCards helper builders -- split out of stats_cards.js to keep the
 * facade IIFE under the line cap. Attaches methods onto the shared S
 * state object via _attachStatsCardsMethods(S).
 */
function _attachStatsCardsTimeline(S) {
  function _timelineBars(buckets) {
    var maxR = Math.max.apply(null, buckets.map(function (b) { return b.r; })) || 1;
    return buckets.slice(-60).map(function (b) {
      var h = Math.max(2, Math.round((b.r / maxR) * 48));
      var errH = b.e > 0 ? Math.max(1, Math.round((b.e / maxR) * 48)) : 0;
      return '<div class="timeline-bar" style="height:' + h + 'px" title="' + b.r + ' req, ' + b.e + ' err">'
        + (errH > 0 ? '<div class="timeline-bar-err" style="height:' + errH + 'px"></div>' : '')
        + '</div>';
    }).join('');
  }

  function timelineCard(buckets) {
    if (!buckets.length) {
      return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt col-span-full">'
        + '<div class="text-[13px] text-muted mb-2">' + t('stats.timeline') + '</div>'
        + '<div class="text-muted text-[13px]">' + t('stats.noTimelineData') + '</div></div>';
    }
    return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt col-span-full">'
      + '<div class="text-[13px] text-muted mb-2">' + t('stats.timelineWindows', { count: Math.min(buckets.length, 60) }) + '</div>'
      + '<div class="timeline-chart">' + _timelineBars(buckets) + '</div></div>';
  }

  S.timelineCard = timelineCard;
}

function _attachStatsCardsStatus(S) {
  function _statusRows(entries, total) {
    return entries.map(function (e) {
      var pct = total > 0 ? (e[1] / total * 100).toFixed(1) : '0';
      var cls = parseInt(e[0]) >= 400 ? 'text-err' : 'text-ok';
      return '<div class="flex justify-between items-center text-[13px]">'
        + '<span class="font-mono ' + cls + '">' + e[0] + '</span>'
        + '<span class="text-muted">' + e[1] + ' (' + pct + '%)</span>'
        + '</div>';
    }).join('');
  }

  function statusCard(byStatus) {
    var entries = Object.entries(byStatus).sort(function (a, b) { return b[1] - a[1]; });
    if (!entries.length) return '';
    var total = entries.reduce(function (s, e) { return s + e[1]; }, 0);
    return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">'
      + '<div class="text-[13px] text-muted m-0 mb-2">' + t('stats.statusDistribution') + '</div>'
      + _statusRows(entries, total) + '</div>';
  }

  S.statusCard = statusCard;
}

function _attachStatsCardsRank(S) {
  function _rankRows(items, maxC) {
    return items.map(function (item, i) {
      var pct = Math.round((item.count / maxC) * 100);
      return '<div class="flex items-center gap-2 text-[13px] mb-1.5">'
        + '<span class="text-muted w-5 text-right">' + (i + 1) + '</span>'
        + '<span class="flex-1 truncate" title="' + item.name + '">' + item.name + '</span>'
        + '<div class="w-20 h-2 bg-panel rounded-full overflow-hidden">'
        + '<div class="h-full bg-accent rounded-full" style="width:' + pct + '%"></div></div>'
        + '<span class="text-muted w-12 text-right">' + S.fmt(item.count) + '</span>'
        + '</div>';
    }).join('');
  }

  function rankCard(title, items) {
    if (!items.length) return '';
    var maxC = items[0] ? items[0].count : 1;
    return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">'
      + '<div class="text-[13px] text-muted m-0 mb-2">' + title + '</div>' + _rankRows(items, maxC) + '</div>';
  }

  S.rankCard = rankCard;
}

function _attachStatsCardsRecent(S) {
  function _recentTimestamp(r) {
    var time = new Date(r.t * 1000);
    return time.getHours().toString().padStart(2, '0') + ':'
      + time.getMinutes().toString().padStart(2, '0') + ':'
      + time.getSeconds().toString().padStart(2, '0');
  }

  function _recentRows(recent) {
    return recent.slice(-10).reverse().map(function (r) {
      var statusCls = r.s >= 400 ? 'text-err' : 'text-ok';
      return '<div class="flex items-center gap-2 text-[12px] font-mono">'
        + '<span class="text-muted">' + _recentTimestamp(r) + '</span>'
        + '<span class="' + statusCls + '">' + r.s + '</span>'
        + '<span class="flex-1 truncate">' + (r.m || '-') + '</span>'
        + '<span class="text-muted">' + r.l + 'ms</span>'
        + '</div>';
    }).join('');
  }

  function recentCard(recent) {
    if (!recent.length) return '';
    return '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift col-span-full">'
      + '<div class="text-[13px] text-muted m-0 mb-2">' + t('stats.recentRequests') + '</div>' + _recentRows(recent) + '</div>';
  }

  S.recentCard = recentCard;
}

function _attachStatsCardsMethods(S) {
  _attachStatsCardsTimeline(S);
  _attachStatsCardsStatus(S);
  _attachStatsCardsRank(S);
  _attachStatsCardsRecent(S);
}
