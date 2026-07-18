/**
 * Feature: 请求统计 — 独立的统计面板模块。
 *
 * 职责：
 * - 通过 /v1/webui/ws/stats WebSocket 接收服务端定时推送的统计数据（替代轮询）
 * - 渲染统计卡片（请求量、错误率、延迟、Token 用量）
 * - 渲染时间线 sparkline
 * - 渲染 Top 平台 / Top 模型
 * - 渲染系统资源
 *
 * Card HTML builders live in the sibling stats_cards.js (StatsCards) so
 * this file only holds state, WebSocket wiring, and top-level render flow.
 */
var StatsFeature = (function () {
  var S = {
    _container: null,
    _lastData: null,
    _ws: null,
    _reconnectTimer: null,
  };

  _attachStatsFeatureMethods(S);

  function init() {
    S._container = document.getElementById('dashboardStatsGrid') || document.getElementById('statsGrid');
    if (!S._container) return;
    S._connect();
  }

  return { init: init, refresh: S.refresh, render: S.render, renderTo: S.renderTo };
})();
