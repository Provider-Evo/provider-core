/**
 * WebUI shell — tab aliases, settings sub-nav, tool-view bar.
 */
function _wsBindSettingsSubnav() {
  document.querySelectorAll('.settings-subnav-btn').forEach(function (node) {
    node.addEventListener('click', function () {
      var section = node.dataset.settingsSection;
      WebuiShell.setSettingsSection(section);
      if (typeof switchTab === 'function') switchTab('settings');
      if (section === 'config' && typeof activateConfigPanel === 'function') {
        activateConfigPanel(typeof state !== 'undefined' ? state.summary : null);
      }
    });
  });
}

function _wsBindToolViewEscape() {
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape' || e.defaultPrevented) return;
    if (typeof state === 'undefined' || !WebuiShell.isToolTab(state.activeTab)) return;
    var openModal = document.querySelector('.ui-modal-backdrop, .terminal-ssh-dialog-overlay, .confirm-overlay.is-open');
    if (openModal) return;
    WebuiShell.leaveTools();
  });
}

function _wsBindSidebarCollapse() {
  var collapseBtn = document.getElementById('sidebarCollapseBtn');
  var bodyEl = document.getElementById('webuiBody');
  if (collapseBtn && bodyEl) {
    collapseBtn.addEventListener('click', function () {
      bodyEl.classList.toggle('expanded');
      var compressed = !bodyEl.classList.contains('expanded');
      if (window._tabLayoutConfig) window._tabLayoutConfig.sidebarCompressed = compressed;
      if (typeof _persistTabLayoutPatch === 'function') {
        _persistTabLayoutPatch({ sidebarCompressed: compressed });
      }
    });
  }
}

var WebuiShell = (function () {
  var ctx = {
    settingsSection: localStorage.getItem('provider.webui.settingsSection') || 'config',
    lastPrimaryTab: localStorage.getItem('provider.webui.lastPrimaryTab') || 'dashboard',
  };

  function leaveTools() {
    if (typeof switchTab === 'function') switchTab(ctx.lastPrimaryTab || 'dashboard');
  }

  return {
    resolveTab: _shellResolveTab,
    isPrimaryTab: _shellIsPrimaryTab,
    isToolTab: _shellIsToolTab,
    settingsSectionForTab: _shellSettingsSectionForTab,
    getSettingsSection: function () { return ctx.settingsSection; },
    setSettingsSection: function (section) { _shellSetSettingsSection(ctx, section); },
    setLastPrimaryTab: function (tab) { _shellSetLastPrimaryTab(ctx, tab); },
    getLastPrimaryTab: function () { return ctx.lastPrimaryTab || 'dashboard'; },
    leaveTools: leaveTools,
    onTabActivated: function (tab) { _shellOnTabActivated(ctx, tab); },
    bind: function () { _shellBind(ctx, leaveTools); },
    PRIMARY_TABS: SHELL_PRIMARY_TABS,
    TOOL_TABS: SHELL_TOOL_TABS,
  };
})();
