from __future__ import annotations

"""WebUI 动作脚本。"""

__all__ = ["WEBUI_SCRIPTS_ACTIONS"]

WEBUI_SCRIPTS_ACTIONS = """
    function copyText(text, successMessage) {
      navigator.clipboard.writeText(text).then(function() {
        toast(successMessage, 'ok');
      }).catch(function(error) {
        toast('复制失败：' + String(error), 'error');
      });
    }

    function exportSummary() {
      const payload = JSON.stringify(state.summary || {}, null, 2);
      const blob = new Blob([payload], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'provider-summary.json';
      link.click();
      URL.revokeObjectURL(url);
      toast('摘要已导出', 'ok');
    }

    function connectLogsSocket() {
      if (!window.WebSocket) {
        socketNotice.textContent = '日志 WebSocket: 当前浏览器不支持';
        return;
      }
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = protocol + '//' + window.location.host + '/v1/webui/ws/logs';
      logsSocket = new WebSocket(url);
      logsSocket.onopen = function() {
        socketNotice.textContent = '日志 WebSocket: 已连接';
        log('日志 WebSocket 已连接，正在加载历史日志...');
      };
      logsSocket.onmessage = function(event) {
        try {
          const payload = JSON.parse(event.data);
          if (payload.type === 'hello') {
            // hello 不显示，历史日志会紧随其后
          }
          if (payload.type === 'history') {
            log('已加载 ' + payload.count + ' 条历史日志。');
          }
          if (payload.type === 'log' && payload.message) {
            const line = '[' + (payload.timestamp || '--:--:--') + '] [' + (payload.level || 'INFO') + '] ' + payload.message;
            logBox.textContent = line + '\\n' + logBox.textContent;
          }
          if (payload.type === 'pong') {
            // 心跳响应不显示
          }
        } catch (error) {
          logBox.textContent = '[error] 消息解析失败：' + String(error) + '\\n' + logBox.textContent;
        }
      };
      logsSocket.onerror = function() {
        socketNotice.textContent = '日志 WebSocket: 连接异常';
      };
      logsSocket.onclose = function() {
        socketNotice.textContent = '日志 WebSocket: 已关闭';
      };
    }

    async function refreshAll() {
      try {
        const [summaryResult, healthResult] = await Promise.allSettled([
          fetchJson('/v1/webui/summary'),
          fetchJson('/health')
        ]);
        if (summaryResult.status === 'fulfilled') {
          state.summary = summaryResult.value;
          renderOverview(summaryResult.value);
          renderConfig(summaryResult.value);
          renderModels(summaryResult.value.models || []);
          renderPlatforms(summaryResult.value.platforms || {});
        }
        if (healthResult.status === 'fulfilled') {
          document.getElementById('healthValue').textContent = healthResult.value && healthResult.value.status ? healthResult.value.status : 'degraded';
        }
        document.getElementById('lastRefresh').textContent = new Date().toLocaleTimeString();
      } catch (error) {
        toast('状态刷新失败：' + String(error), 'error');
      }
    }

    async function refreshModels() {
      try {
        log('开始刷新模型缓存。');
        const result = await fetchJson('/v1/admin/refresh_models', { method: 'POST' });
        toast('模型刷新完成', 'ok');
        await refreshAll();
      } catch (error) {
        toast('模型刷新失败：' + String(error), 'error');
        log('模型刷新失败：' + String(error));
      }
    }

    async function saveConfig() {
      try {
        log('正在保存配置...');
        let configData;
        if (configEditArea && !configEditArea.classList.contains('hidden')) {
          configData = JSON.parse(configEditArea.value);
        } else {
          configData = JSON.parse(configJsonBox.textContent || '{}');
        }
        const response = await fetch('/v1/config', {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(configData)
        });
        const result = await response.json();
        if (result.status === 'ok') {
          state.configDirty = false;
          updateConfigSaveStatus();
          toast('配置已保存并重新加载', 'ok');
          log('配置已保存并重新加载。');
          await refreshAll();
        } else {
          toast('保存失败：' + (result.error || '未知错误'), 'error');
          log('配置保存失败：' + JSON.stringify(result));
        }
      } catch (error) {
        toast('保存失败：' + String(error), 'error');
        log('配置保存失败：' + String(error));
      }
    }

    async function reloadServer() {
      try {
        log('正在请求服务重启...');
        const response = await fetch('/v1/admin/reload', { method: 'POST' });
        const result = await response.json();
        if (result.status === 'ok') {
          toast('服务正在重启，页面将自动刷新', 'ok');
          log('服务重启已触发，页面将在3秒后刷新。');
          setTimeout(function() { location.reload(); }, 3000);
        } else {
          toast('重启失败：' + (result.error || '未知错误'), 'error');
          log('服务重启失败：' + JSON.stringify(result));
        }
      } catch (error) {
        toast('重启失败：' + String(error), 'error');
        log('服务重启失败：' + String(error));
      }
    }

    async function reloadConfigFromFile() {
      try {
        log('正在从文件重新加载配置...');
        const response = await fetch('/v1/config/reload', { method: 'POST' });
        const result = await response.json();
        if (result.status === 'ok') {
          state.configDirty = false;
          updateConfigSaveStatus();
          toast('配置已从文件重新加载', 'ok');
          log('配置已从文件重新加载。');
          await refreshAll();
        } else {
          toast('重载失败：' + (result.error || '未知错误'), 'error');
        }
      } catch (error) {
        toast('重载失败：' + String(error), 'error');
        log('配置重载失败：' + String(error));
      }
    }

    function toggleConfigEdit() {
      if (!configEditArea) return;
      const isHidden = configEditArea.classList.contains('hidden');
      if (isHidden) {
        configEditArea.value = configJsonBox.textContent || '';
        configEditArea.classList.remove('hidden');
        document.getElementById('configEditToggle').textContent = '收起编辑';
      } else {
        try {
          const parsed = JSON.parse(configEditArea.value);
          configJsonBox.textContent = JSON.stringify(parsed, null, 2);
        } catch (e) {
          toast('JSON 格式错误，未保存更改', 'error');
        }
        configEditArea.classList.add('hidden');
        document.getElementById('configEditToggle').textContent = '编辑配置';
      }
    }
"""
