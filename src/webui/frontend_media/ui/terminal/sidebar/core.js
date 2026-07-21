/**
 * TerminalSidebar core sub-module -- collapse/expand persistence and
 * sub-tab switching/rendering dispatch. Attaches init onto the shared ctx
 * object used by sidebar.js.
 */
function _attachTerminalSidebarCore(ctx) {
  var _state = { collapsed: false, activeSubTab: 'servers' };

  var _collapse = _attachTerminalSidebarCoreSubCollapse(ctx, _state);
  var _subTab = _attachTerminalSidebarCoreSubSubTab(ctx, _state);

  function init() {
    var toggleBtn = document.getElementById('terminalSidebarToggle');
    var tabsEl = document.getElementById('terminalSidebarTabs');

    if (!toggleBtn || !tabsEl) return;

    toggleBtn.addEventListener('click', function () {
      _collapse.toggleCollapsed();
    });

    var tabBtns = tabsEl.querySelectorAll('.terminal-sidebar-tab');
    for (var i = 0; i < tabBtns.length; i++) {
      (function (btn) {
        btn.addEventListener('click', function () {
          _subTab.switchSubTab(btn.getAttribute('data-sidebar-tab'));
        });
      })(tabBtns[i]);
    }

    _collapse.loadCollapsedState();
    _subTab.renderActiveSubTab();
  }

  ctx.init = init;
}

function _attachTerminalSidebarCoreSubCollapse(ctx, state) {
  function _applyCollapsedState() {
    var sidebar = document.getElementById('terminalSidebar');
    var icon = document.getElementById('terminalSidebarToggleIcon');
    if (!sidebar) return;
    if (state.collapsed) {
      sidebar.classList.add('collapsed');
      if (icon) icon.innerHTML = '&#8249;';
    } else {
      sidebar.classList.remove('collapsed');
      if (icon) icon.innerHTML = '&#8250;';
    }
  }

  function _toggleCollapsed() {
    state.collapsed = !state.collapsed;
    _applyCollapsedState();
    _saveCollapsedState();
  }

  async function _loadCollapsedState() {
    try {
      if (typeof persistLoad === 'function') {
        var data = await persistLoad('terminals.json');
        if (data && typeof data.serverSidebarCollapsed === 'boolean') {
          state.collapsed = data.serverSidebarCollapsed;
        }
      }
    } catch (e) { /* ignore */ }
    _applyCollapsedState();
  }

  async function _saveCollapsedState() {
    try {
      if (typeof mergeTerminalsPersist === 'function') {
        await mergeTerminalsPersist({ serverSidebarCollapsed: state.collapsed });
      } else if (typeof persistSave === 'function') {
        var existing = await persistLoad('terminals.json') || {};
        existing.serverSidebarCollapsed = state.collapsed;
        await persistSave('terminals.json', existing);
      }
    } catch (e) { /* ignore */ }
  }

  return {
    toggleCollapsed: _toggleCollapsed,
    loadCollapsedState: _loadCollapsedState,
  };
}

function _attachTerminalSidebarCoreSubSubTab(ctx, state) {
  function _switchSubTab(name) {
    if (!name) return;
    state.activeSubTab = name;

    var tabsEl = document.getElementById('terminalSidebarTabs');
    if (tabsEl) {
      var btns = tabsEl.querySelectorAll('.terminal-sidebar-tab');
      for (var i = 0; i < btns.length; i++) {
        var isActive = btns[i].getAttribute('data-sidebar-tab') === name;
        btns[i].classList.toggle('active', isActive);
      }
    }

    var panels = {
      servers: document.getElementById('terminalSidebarPanelServers'),
      audit: document.getElementById('terminalSidebarPanelAudit'),
      commands: document.getElementById('terminalSidebarPanelCommands'),
    };
    var keys = Object.keys(panels);
    for (var j = 0; j < keys.length; j++) {
      if (panels[keys[j]]) panels[keys[j]].classList.toggle('active', keys[j] === name);
    }

    _renderActiveSubTab();
  }

  function _renderActiveSubTab() {
    if (state.activeSubTab === 'servers') ctx.renderServers();
    else if (state.activeSubTab === 'audit') ctx.renderAudit();
    else if (state.activeSubTab === 'commands') ctx.renderCommands();
  }

  return {
    switchSubTab: _switchSubTab,
    renderActiveSubTab: _renderActiveSubTab,
  };
}

window._attachTerminalSidebarCore = _attachTerminalSidebarCore;
