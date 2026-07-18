// ========================= Tabs =========================
// 拆分自 state.js。依赖 state_core.js（state）、state_logrender.js（_renderLogs/_logAutoScrollToBottom）已加载。

var _initializedTabs = new Set();

function _switchTabResolveTarget(nextTab) {
  var rawTab = nextTab;
  if (typeof WebuiShell !== 'undefined') {
    var section = WebuiShell.settingsSectionForTab && WebuiShell.settingsSectionForTab(nextTab);
    if (section && typeof WebuiShell.setSettingsSection === 'function') {
      WebuiShell.setSettingsSection(section);
    }
    if (WebuiShell.isPrimaryTab && WebuiShell.isPrimaryTab(rawTab)) {
      WebuiShell.setLastPrimaryTab(rawTab);
    }
    if (rawTab === 'settings') {
      WebuiShell.setLastPrimaryTab('settings');
    }
    nextTab = WebuiShell.resolveTab(nextTab);
  }
  return { rawTab: rawTab, nextTab: nextTab };
}

function _switchTabUpdateNav(nextTab) {
  document.querySelectorAll('.tab-button[data-tab]').forEach(function(node) {
    var tab = node.dataset.tab;
    var active = tab === nextTab
      || (nextTab === 'settings' && (tab === 'config' || tab === 'autoupdate'))
      || (nextTab === 'dashboard' && (tab === 'overview' || tab === 'stats'))
      || (nextTab === 'routing' && (tab === 'platforms' || tab === 'models'));
    node.classList.toggle('active', active);
    node.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  document.querySelectorAll('.sidebar-nav-item[data-tab]').forEach(function(node) {
    node.classList.toggle('active', node.dataset.tab === nextTab);
  });
}

function _switchTabUpdatePanels(nextTab) {
  document.querySelectorAll('.tab-panel').forEach(function(node) {
    var isActive = node.id === 'tab-' + nextTab;
    node.classList.toggle('active', isActive);
    node.classList.toggle('hidden', !isActive);
  });
}

async function switchTab(nextTab) {
  var resolved = _switchTabResolveTarget(nextTab);
  var rawTab = resolved.rawTab;
  nextTab = resolved.nextTab;

  state.activeTab = nextTab;
  localStorage.setItem('provider.webui.activeTab', nextTab);
  _switchTabUpdateNav(nextTab);

  // Lazy-load tab resources before activating the panel — avoids CSS/JS layout race
  if (typeof LazyLoader !== 'undefined' && !LazyLoader.isTabLoaded(nextTab)) {
    await LazyLoader.loadTabResources(nextTab);
  }

  _switchTabUpdatePanels(nextTab);

  if (typeof WebuiShell !== 'undefined' && WebuiShell.onTabActivated) {
    WebuiShell.onTabActivated(rawTab);
  }

  _initTab(nextTab);
  if ((nextTab === 'settings' || nextTab === 'config') && typeof activateConfigPanel === 'function') {
    activateConfigPanel(state.summary);
  }
  if (nextTab === 'logs') {
    requestAnimationFrame(function() {
      _renderLogs();
      _logAutoScrollToBottom();
    });
  }
}

function _initTabSettings() {
  if (typeof WebuiShell !== 'undefined' && WebuiShell.getSettingsSection() === 'autoupdate') {
    typeof _initAutoupdateTab === 'function' && _initAutoupdateTab();
  } else if (typeof WebuiShell !== 'undefined' && WebuiShell.getSettingsSection() === 'config') {
    if (typeof _bindConfigPanel === 'function') _bindConfigPanel();
  }
}

function _initTabSimple(tabName) {
  switch (tabName) {
    case 'dashboard':
      typeof _initDashboardTab === 'function' && _initDashboardTab();
      break;
    case 'routing':
      typeof _initRoutingTab === 'function' && _initRoutingTab();
      break;
    case 'keys':
      typeof _initKeysTab === 'function' && _initKeysTab();
      break;
    case 'requests':
      typeof _initRequestsTab === 'function' && _initRequestsTab();
      break;
    case 'chat':
      typeof _initChatTab === 'function' && _initChatTab();
      break;
    case 'stats':
      typeof _initStatsTab === 'function' && _initStatsTab();
      break;
    case 'autoupdate':
      typeof _initAutoupdateTab === 'function' && _initAutoupdateTab();
      break;
    case 'plugins':
      typeof initPluginsPanel === 'function' && initPluginsPanel();
      break;
    case 'config':
      if (typeof _bindConfigPanel === 'function') _bindConfigPanel();
      break;
    case 'terminal':
      typeof _initTerminalTab === 'function' && _initTerminalTab();
      break;
    // files — no special init needed (uses Router.register activate)
    default:
      break;
  }
}

function _initTab(tabName) {
  if (_initializedTabs.has(tabName)) return;
  _initializedTabs.add(tabName);

  if (tabName === 'settings') {
    _initTabSettings();
    return;
  }
  if (tabName === 'logs') {
    _applyLogFontSize();
    _renderLogs();
    return;
  }
  _initTabSimple(tabName);
}
