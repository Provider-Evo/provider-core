/**
 * Dashboard — 合并概览 KPI 与核心统计。
 * 统计数据由 StatsFeature 通过 /v1/webui/ws/stats WebSocket 统一接收并推送，
 * 本模块不再单独维护轮询定时器，避免与 StatsFeature 重复请求。
 */
var DashboardFeature = (function () {
  function _container() {
    return document.getElementById('dashboardStatsGrid');
  }

  function init() {
    var panel = document.getElementById('tab-dashboard');
    if (!panel) return;
    if (typeof StatsFeature !== 'undefined') StatsFeature.init();
    if (panel.classList.contains('active')) refresh();
  }

  async function refresh() {
    var grid = _container();
    if (!grid) return;
    try {
      var data = await Api.fetchJson('/v1/webui/stats');
      if (typeof StatsFeature !== 'undefined' && StatsFeature.renderTo) {
        StatsFeature.renderTo(grid, data, { compact: true });
      }
    } catch (e) {
      grid.innerHTML = '<div class="ui-empty"><p class="ui-empty__title">' + t('stats.loadFailed', { error: e.message }) + '</p></div>';
    }
  }

  return { init: init, refresh: refresh };
})();

function _initDashboardTab() {
  if (typeof DashboardFeature !== 'undefined') DashboardFeature.init();
  var refreshBtn = document.getElementById('dashboardStatsRefreshBtn');
  var resetBtn = document.getElementById('dashboardStatsResetBtn');
  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = '1';
    refreshBtn.addEventListener('click', function () {
      if (typeof DashboardFeature !== 'undefined') DashboardFeature.refresh();
    });
  }
  if (resetBtn && !resetBtn.dataset.bound) {
    resetBtn.dataset.bound = '1';
    resetBtn.addEventListener('click', async function () {
      try {
        await Api.post('/v1/webui/stats/reset');
        toast(t('stats.resetOk'), 'ok');
        if (typeof DashboardFeature !== 'undefined') DashboardFeature.refresh();
      } catch (e) {
        toast(t('stats.resetFailed', { error: e.message }), 'error');
      }
    });
  }
}
