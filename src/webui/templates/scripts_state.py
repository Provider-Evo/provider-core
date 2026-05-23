from __future__ import annotations

"""WebUI 状态与公共工具脚本。"""

__all__ = ["WEBUI_SCRIPTS_STATE"]

WEBUI_SCRIPTS_STATE = """
    const defaultSettings = {
      theme: 'auto',
      refreshInterval: 0,
      timeoutMs: 6000,
      compact: '0'
    };
    const initialTab = localStorage.getItem('provider.webui.activeTab') || '__INITIAL_TAB__';
    const state = {
      timer: null,
      models: [],
      summary: null,
      settings: loadSettings(),
      activeTab: initialTab,
      configDirty: false,
      configSaveTimer: null,
      configSaveDebounceMs: 1000,
    };

    const logBox = document.getElementById('logBox');
    const platformGrid = document.getElementById('platformGrid');
    const modelGrid = document.getElementById('modelGrid');
    const configGrid = document.getElementById('configGrid');
    const configJsonBox = document.getElementById('configJsonBox');
    const configEditArea = document.getElementById('configEditArea');
    const configSaveStatus = document.getElementById('configSaveStatus');
    const overviewGrid = document.getElementById('overviewGrid');
    const overviewNotice = document.getElementById('overviewNotice');
    const portablePanel = document.getElementById('portablePanel');
    const themeState = document.getElementById('themeState');
    const refreshState = document.getElementById('refreshState');
    const toastWrap = document.getElementById('toastWrap');
    const socketNotice = document.getElementById('socketNotice');
    let logsSocket = null;

    function log(message) {
      const line = '[' + new Date().toLocaleTimeString() + '] ' + message;
      logBox.textContent = line + '\\n' + logBox.textContent;
    }

    function toast(message, type) {
      const node = document.createElement('div');
      node.className = 'min-w-[220px] max-w-[340px] rounded-xl border border-border bg-panel shadow-panel px-3 py-2.5 text-[13px] leading-relaxed';
      node.textContent = '[' + (type || 'info') + '] ' + message;
      toastWrap.appendChild(node);
      setTimeout(function() {
        node.remove();
      }, 3200);
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
      updateThemeIcon();
    }

    function updateThemeIcon() {
      const theme = state.settings.theme;
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      const effective = theme === 'auto' ? (prefersDark ? 'dark' : 'light') : theme;
      const fabIcon = document.getElementById('fabThemeIcon');
      if (fabIcon) {
        fabIcon.innerHTML = effective === 'dark' ? '&#9788;' : '&#9790;';
      }
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
        refreshState.textContent = 'refresh: ' + interval + 's';
      } else {
        refreshState.textContent = 'refresh: manual';
      }
    }

    function updateConfigSaveStatus() {
      if (configSaveStatus) {
        if (state.configDirty) {
          configSaveStatus.textContent = '未保存';
          configSaveStatus.className = 'status-dirty flex items-center';
        } else {
          configSaveStatus.textContent = '已保存';
          configSaveStatus.className = 'status-saved flex items-center';
        }
      }
    }

    function scheduleConfigSave() {
      if (state.configSaveTimer) clearTimeout(state.configSaveTimer);
      state.configDirty = true;
      updateConfigSaveStatus();
      state.configSaveTimer = setTimeout(function() {
        saveConfig();
      }, state.configSaveDebounceMs);
    }

    function switchTab(nextTab) {
      state.activeTab = nextTab;
      localStorage.setItem('provider.webui.activeTab', nextTab);
      document.querySelectorAll('.tab-button').forEach(function(node) {
        node.classList.toggle('active', node.dataset.tab === nextTab);
        node.setAttribute('aria-selected', node.dataset.tab === nextTab ? 'true' : 'false');
      });
      document.querySelectorAll('.tab-panel').forEach(function(node) {
        node.classList.toggle('active', node.id === 'tab-' + nextTab);
      });
    }

    async function fetchJson(url, options) {
      const controller = new AbortController();
      const timeout = Number(state.settings.timeoutMs || defaultSettings.timeoutMs);
      const timer = setTimeout(function() { controller.abort(); }, timeout);
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
"""
