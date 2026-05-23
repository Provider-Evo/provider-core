from __future__ import annotations

"""内置 WebUI 页面。"""

from src.core.config import get_config


_HTML_TEMPLATE = """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Provider-V2 WebUI</title>
  <style>
    :root {
      color-scheme: light dark;
      --bg: #f5f7fb;
      --panel: #ffffff;
      --panel-alt: #eef2ff;
      --text: #18212f;
      --muted: #5d6a7d;
      --accent: #4263eb;
      --accent-soft: rgba(66, 99, 235, 0.12);
      --ok: #1c9b5f;
      --warn: #d9822b;
      --err: #d64545;
      --border: #d8dfeb;
      --shadow: 0 12px 32px rgba(21, 33, 56, 0.08);
    }
    [data-theme="dark"] {
      --bg: #0f1723;
      --panel: #18212f;
      --panel-alt: #1f2b3c;
      --text: #edf2ff;
      --muted: #a8b3c7;
      --accent: #8aa4ff;
      --accent-soft: rgba(138, 164, 255, 0.16);
      --ok: #35c97b;
      --warn: #ffb454;
      --err: #ff7b7b;
      --border: #2d3b50;
      --shadow: none;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    .layout {
      max-width: 1180px;
      margin: 0 auto;
      padding: 20px;
      display: grid;
      gap: 16px;
    }
    .hero,
    .panel {
      background: var(--panel);
      border: 1px solid var(--border);
      border-radius: 16px;
      box-shadow: var(--shadow);
    }
    .hero {
      padding: 20px;
      display: grid;
      gap: 14px;
    }
    .hero-top,
    .toolbar,
    .status-grid,
    .platform-grid,
    .settings-grid {
      display: grid;
      gap: 12px;
    }
    .hero-top {
      grid-template-columns: 1fr auto;
      align-items: center;
    }
    .toolbar {
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    }
    .status-grid {
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    }
    .platform-grid {
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    }
    .settings-grid {
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      align-items: end;
    }
    .panel { padding: 18px; }
    .muted { color: var(--muted); }
    .title { font-size: 28px; margin: 0; }
    .subtitle { margin: 0; color: var(--muted); }
    .metric,
    .platform-card,
    .setting-card {
      border: 1px solid var(--border);
      border-radius: 14px;
      padding: 14px;
      background: var(--panel-alt);
    }
    .metric-label,
    .platform-name,
    .setting-title {
      font-size: 13px;
      color: var(--muted);
      margin-bottom: 8px;
    }
    .metric-value {
      font-size: 24px;
      font-weight: bold;
    }
    .platform-value {
      font-size: 14px;
      margin: 4px 0;
    }
    button,
    select,
    input {
      width: 100%;
      border-radius: 10px;
      border: 1px solid var(--border);
      background: var(--panel);
      color: var(--text);
      padding: 10px 12px;
      font-size: 14px;
    }
    button {
      cursor: pointer;
      background: var(--accent);
      color: #ffffff;
      border: none;
      font-weight: bold;
    }
    button.secondary {
      background: transparent;
      color: var(--text);
      border: 1px solid var(--border);
    }
    .row {
      display: flex;
      gap: 10px;
      flex-wrap: wrap;
      align-items: center;
    }
    .chip {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border-radius: 999px;
      padding: 6px 10px;
      font-size: 12px;
      background: var(--accent-soft);
      color: var(--text);
    }
    .chip.ok { color: var(--ok); }
    .chip.warn { color: var(--warn); }
    .chip.err { color: var(--err); }
    .log {
      min-height: 88px;
      max-height: 220px;
      overflow: auto;
      font-family: monospace;
      font-size: 13px;
      line-height: 1.5;
      white-space: pre-wrap;
    }
    .footnote {
      font-size: 12px;
      color: var(--muted);
    }
    .hidden { display: none; }
    @media (max-width: 720px) {
      .hero-top { grid-template-columns: 1fr; }
      .layout { padding: 12px; }
    }
  </style>
</head>
<body>
  <div class="layout" id="app">
    <section class="hero">
      <div class="hero-top">
        <div>
          <h1 class="title">Provider-V2 WebUI</h1>
          <p class="subtitle">轻量管理面板，适用于本地管理、状态浏览和便携设置。</p>
        </div>
        <div class="row">
          <span class="chip">版本 __VERSION__</span>
          <span class="chip">__HOST__:__PORT__</span>
          <span class="chip" id="themeState">theme: auto</span>
        </div>
      </div>
      <div class="toolbar">
        <button id="refreshButton">刷新状态</button>
        <button id="refreshModelsButton">刷新模型缓存</button>
        <button class="secondary" id="themeButton">切换主题</button>
        <button class="secondary" id="portableButton">显示便携设置</button>
      </div>
      <div class="status-grid">
        <div class="metric">
          <div class="metric-label">平台数量</div>
          <div class="metric-value" id="platformCount">-</div>
        </div>
        <div class="metric">
          <div class="metric-label">模型数量</div>
          <div class="metric-value" id="modelCount">-</div>
        </div>
        <div class="metric">
          <div class="metric-label">最近刷新</div>
          <div class="metric-value" id="lastRefresh">-</div>
        </div>
        <div class="metric">
          <div class="metric-label">服务状态</div>
          <div class="metric-value" id="healthValue">-</div>
        </div>
      </div>
    </section>

    <section class="panel hidden" id="portablePanel">
      <h2>便携设置</h2>
      <div class="settings-grid">
        <label class="setting-card">
          <div class="setting-title">主题模式</div>
          <select id="themeSelect">
            <option value="auto">auto</option>
            <option value="light">light</option>
            <option value="dark">dark</option>
          </select>
        </label>
        <label class="setting-card">
          <div class="setting-title">自动刷新间隔（秒）</div>
          <input id="refreshIntervalInput" type="number" min="0" max="300" step="5">
        </label>
        <label class="setting-card">
          <div class="setting-title">请求超时（毫秒）</div>
          <input id="timeoutInput" type="number" min="500" max="30000" step="500">
        </label>
        <label class="setting-card">
          <div class="setting-title">显示紧凑模式</div>
          <select id="compactSelect">
            <option value="0">关闭</option>
            <option value="1">开启</option>
          </select>
        </label>
      </div>
      <p class="footnote">便携设置存储在当前浏览器 localStorage，不依赖外部服务。</p>
    </section>

    <section class="panel">
      <h2>平台状态</h2>
      <div class="platform-grid" id="platformGrid"></div>
    </section>

    <section class="panel">
      <h2>运行日志</h2>
      <div class="log" id="logBox"></div>
    </section>
  </div>
  <script>
    const defaultSettings = {
      theme: 'auto',
      refreshInterval: 0,
      timeoutMs: 6000,
      compact: '0'
    };
    const state = {
      timer: null,
      models: [],
      settings: loadSettings()
    };

    const logBox = document.getElementById('logBox');
    const platformGrid = document.getElementById('platformGrid');
    const portablePanel = document.getElementById('portablePanel');
    const themeState = document.getElementById('themeState');

    function log(message) {
      const line = '[' + new Date().toLocaleTimeString() + '] ' + message;
      logBox.textContent = line + '\n' + logBox.textContent;
    }

    function loadSettings() {
      try {
        return Object.assign({}, defaultSettings, JSON.parse(localStorage.getItem('provider.webui.settings') || '{}'));
      } catch (error) {
        return Object.assign({}, defaultSettings);
      }
    }

    function saveSettings() {
      localStorage.setItem('provider.webui.settings', JSON.stringify(state.settings));
      applyTheme();
      applyCompact();
      scheduleRefresh();
    }

    function applyTheme() {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      const theme = state.settings.theme === 'auto' ? (prefersDark ? 'dark' : 'light') : state.settings.theme;
      document.documentElement.setAttribute('data-theme', theme);
      themeState.textContent = 'theme: ' + state.settings.theme;
      document.getElementById('themeSelect').value = state.settings.theme;
    }

    function applyCompact() {
      document.body.dataset.compact = state.settings.compact;
      document.getElementById('compactSelect').value = state.settings.compact;
    }

    function scheduleRefresh() {
      if (state.timer) {
        clearInterval(state.timer);
      }
      const interval = Number(state.settings.refreshInterval || 0);
      if (interval > 0) {
        state.timer = setInterval(refreshAll, interval * 1000);
      }
    }

    async function fetchJson(url, options) {
      const controller = new AbortController();
      const timeout = Number(state.settings.timeoutMs || defaultSettings.timeoutMs);
      const timer = setTimeout(() => controller.abort(), timeout);
      try {
        const response = await fetch(url, Object.assign({ signal: controller.signal }, options || {}));
        if (!response.ok) {
          throw new Error(response.status + ' ' + response.statusText);
        }
        return await response.json();
      } finally {
        clearTimeout(timer);
      }
    }

    function renderPlatforms(platforms) {
      const entries = Object.entries(platforms || {});
      document.getElementById('platformCount').textContent = String(entries.length);
      platformGrid.innerHTML = '';
      if (!entries.length) {
        platformGrid.innerHTML = '<div class="platform-card">暂无平台状态。</div>';
        return;
      }
      entries.forEach(function(entry) {
        const name = entry[0];
        const info = entry[1] || {};
        const card = document.createElement('div');
        card.className = 'platform-card';
        const stateText = info.error ? '<span class="chip err">error</span>' : (Number(info.available || 0) > 0 ? '<span class="chip ok">available</span>' : '<span class="chip warn">idle</span>');
        card.innerHTML = [
          '<div class="platform-name">' + name + ' ' + stateText + '</div>',
          '<div class="platform-value">candidates: ' + String(info.candidates ?? '-') + '</div>',
          '<div class="platform-value">available: ' + String(info.available ?? '-') + '</div>',
          '<div class="platform-value">models: ' + String(info.models ?? '-') + '</div>'
        ].join('');
        platformGrid.appendChild(card);
      });
    }

    async function refreshAll() {
      try {
        log('开始刷新状态。');
        const results = await Promise.allSettled([
          fetchJson('/health'),
          fetchJson('/v1/status'),
          fetchJson('/v1/models')
        ]);
        const health = results[0].status === 'fulfilled' ? results[0].value : null;
        const status = results[1].status === 'fulfilled' ? results[1].value : null;
        const models = results[2].status === 'fulfilled' ? results[2].value : null;
        document.getElementById('healthValue').textContent = health && health.status ? health.status : 'degraded';
        document.getElementById('lastRefresh').textContent = new Date().toLocaleTimeString();
        state.models = (models && models.data) ? models.data : [];
        document.getElementById('modelCount').textContent = String(state.models.length);
        renderPlatforms(status && status.platforms ? status.platforms : {});
        if (results.some(function(item) { return item.status === 'rejected'; })) {
          log('部分接口刷新失败，界面已降级展示。');
        } else {
          log('状态刷新完成。');
        }
      } catch (error) {
        log('刷新失败：' + String(error));
      }
    }

    async function refreshModels() {
      try {
        log('开始刷新模型缓存。');
        const result = await fetchJson('/v1/admin/refresh_models', { method: 'POST' });
        log('模型刷新完成：' + JSON.stringify(result.refreshed || {}));
        await refreshAll();
      } catch (error) {
        log('模型刷新失败：' + String(error));
      }
    }

    document.getElementById('refreshButton').addEventListener('click', refreshAll);
    document.getElementById('refreshModelsButton').addEventListener('click', refreshModels);
    document.getElementById('themeButton').addEventListener('click', function() {
      const order = ['auto', 'light', 'dark'];
      const index = order.indexOf(state.settings.theme);
      state.settings.theme = order[(index + 1) % order.length];
      saveSettings();
      log('主题已切换为 ' + state.settings.theme + '。');
    });
    document.getElementById('portableButton').addEventListener('click', function() {
      portablePanel.classList.toggle('hidden');
    });
    document.getElementById('themeSelect').addEventListener('change', function(event) {
      state.settings.theme = event.target.value;
      saveSettings();
    });
    document.getElementById('refreshIntervalInput').value = String(state.settings.refreshInterval);
    document.getElementById('refreshIntervalInput').addEventListener('change', function(event) {
      state.settings.refreshInterval = Number(event.target.value || 0);
      saveSettings();
      log('自动刷新间隔已更新。');
    });
    document.getElementById('timeoutInput').value = String(state.settings.timeoutMs);
    document.getElementById('timeoutInput').addEventListener('change', function(event) {
      state.settings.timeoutMs = Number(event.target.value || defaultSettings.timeoutMs);
      saveSettings();
    });
    document.getElementById('compactSelect').addEventListener('change', function(event) {
      state.settings.compact = event.target.value;
      saveSettings();
    });

    applyTheme();
    applyCompact();
    scheduleRefresh();
    refreshAll();
  </script>
</body>
</html>
"""


def render_webui() -> str:
    """渲染管理 WebUI。

    Returns:
        内联样式和脚本的完整 HTML。
    """
    cfg = get_config()
    return (
        _HTML_TEMPLATE.replace('__VERSION__', cfg.server.version)
        .replace('__HOST__', cfg.server.host)
        .replace('__PORT__', str(cfg.server.port))
    )
