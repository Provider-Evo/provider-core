from __future__ import annotations

"""WebUI 事件绑定脚本。"""

__all__ = ["WEBUI_SCRIPTS_BOOTSTRAP"]

WEBUI_SCRIPTS_BOOTSTRAP = """
    document.getElementById('refreshButton').addEventListener('click', refreshAll);
    document.getElementById('refreshModelsButton').addEventListener('click', refreshModels);
    document.getElementById('fabThemeButton').addEventListener('click', function() {
      const order = ['auto', 'light', 'dark'];
      const index = order.indexOf(state.settings.theme);
      state.settings.theme = order[(index + 1) % order.length];
      saveSettings();
      toast('主题已切换为 ' + state.settings.theme, 'ok');
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
    document.getElementById('platformSearchInput').addEventListener('input', function() {
      renderPlatforms((state.summary || {}).platforms || {});
    });
    document.getElementById('modelSearchInput').addEventListener('input', function() {
      renderModels(state.models);
    });
    document.getElementById('modelPlatformSelect').addEventListener('change', function() {
      renderModels(state.models);
    });
    document.getElementById('modelCapabilitySelect').addEventListener('change', function() {
      renderModels(state.models);
    });
    document.getElementById('copySummaryButton').addEventListener('click', function() {
      copyText(JSON.stringify(state.summary || {}, null, 2), '摘要已复制');
    });
    document.getElementById('exportSummaryButton').addEventListener('click', exportSummary);
    document.getElementById('copyConfigButton').addEventListener('click', function() {
      copyText(configJsonBox.textContent || '{}', '配置摘要已复制');
    });
    document.getElementById('clearLogButton').addEventListener('click', function() {
      logBox.textContent = '';
      toast('日志已清空', 'ok');
    });
    document.getElementById('reloadServerButton').addEventListener('click', reloadServer);
    document.getElementById('reloadConfigButton').addEventListener('click', reloadConfigFromFile);
    document.getElementById('configEditToggle').addEventListener('click', toggleConfigEdit);
    if (configEditArea) {
      configEditArea.addEventListener('input', function() {
        try {
          JSON.parse(configEditArea.value);
          scheduleConfigSave();
        } catch (e) {
          toast('JSON 格式错误', 'error');
        }
      });
    }
    document.querySelectorAll('.tab-button').forEach(function(node) {
      node.id = 'tab-' + node.dataset.tab + '-button';
      node.addEventListener('click', function() {
        switchTab(node.dataset.tab);
      });
    });

    applyTheme();
    applyCompact();
    scheduleRefresh();
    switchTab(initialTab);
    connectLogsSocket();
    refreshAll();
"""
