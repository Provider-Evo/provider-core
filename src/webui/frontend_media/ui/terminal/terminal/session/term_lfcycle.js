// ========================= Terminal: Tab Lifecycle (Close/Rename/Move) =========================
// Split from terminal.js. Handles tab lookup, closing (including split-pane
// teardown), renaming, duplicating, moving, exporting, and clear/restart.

function _attachLifecycleMethods(ctx) {
  _attachLifecycleTabLookupMethods(ctx);
  _attachLifecycleSplitTeardownMethods(ctx);
  _attachLifecycleTabTeardownMethods(ctx);
  _attachLifecycleCloseMethods(ctx);
  _attachLifecycleTabOpsMethods(ctx);
  _attachLifecycleTabMoveMethods(ctx);
  _attachLifecycleHistoryMethods(ctx);
}

function _attachLifecycleTabLookupMethods(ctx) {

  function _getTabById(tabId) {
    for (var i = 0; i < ctx.tabs.length; i++) {
      if (ctx.tabs[i].id === tabId) return ctx.tabs[i];
    }
    return null;
  }

  function _getActiveTab() {
    return _getTabById(ctx.activeTabId);
  }

  ctx.getTabById = _getTabById;
  ctx.getActiveTab = _getActiveTab;
}

function _attachLifecycleSplitTeardownMethods(ctx) {

  function _teardownSplitState(splitState) {
    splitState._closing = true;
    if (splitState._reconnectTimer) {
      clearTimeout(splitState._reconnectTimer);
      splitState._reconnectTimer = null;
    }
    if (splitState.ws && splitState.ws.readyState === WebSocket.OPEN) {
      try { splitState.ws.send(JSON.stringify({ type: 'close_session' })); } catch (e) {}
    }
    var splitWsRef = splitState.ws;
    setTimeout(function () {
      if (splitWsRef) { try { splitWsRef.close(); } catch (e) {} }
    }, 50);
    if (splitState._resizeObserver) {
      try { splitState._resizeObserver.disconnect(); } catch (e) {}
    }
    if (splitState.xterm) {
      try { splitState.xterm.dispose(); } catch (e) {}
    }
    if (splitState.fitAddon) {
      try { splitState.fitAddon.dispose(); } catch (e) {}
    }
  }

  ctx.teardownSplitState = _teardownSplitState;
}

function _attachLifecycleTabTeardownMethods(ctx) {

  // Shared helper: tear down WS + observers + xterm for a tab (or split pane).
  function _teardownTabResources(tab) {
    tab._closing = true;
    if (tab._reconnectTimer) {
      clearTimeout(tab._reconnectTimer);
      tab._reconnectTimer = null;
    }
    // Send close_session to backend so the process is killed (explicit close).
    if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
      try { tab.ws.send(JSON.stringify({ type: 'close_session' })); } catch (e) {}
    }
    var wsRef = tab.ws;
    setTimeout(function () {
      if (wsRef) { try { wsRef.close(); } catch (e) {} }
    }, 50);
    if (tab._resizeObserver) {
      try { tab._resizeObserver.disconnect(); } catch (e) {}
    }
    if (tab.xterm) { try { tab.xterm.dispose(); } catch (e) {} }
    if (tab.fitAddon) { try { tab.fitAddon.dispose(); } catch (e) {} }
    if (tab.split) {
      ctx.teardownSplitState(tab.split);
      tab.split = null;
    }
  }

  ctx.teardownTabResources = _teardownTabResources;
}

function _attachLifecycleCloseMethods(ctx) {

  function closeTab(tabId) {
    var idx = -1;
    for (var i = 0; i < ctx.tabs.length; i++) {
      if (ctx.tabs[i].id === tabId) { idx = i; break; }
    }
    if (idx === -1) return;

    var tab = ctx.tabs[idx];
    ctx.teardownTabResources(tab);

    // Remove DOM pane
    var pane = document.getElementById('terminal-pane-' + tabId);
    if (pane) pane.remove();

    ctx.tabs.splice(idx, 1);
    if (ctx.bar) ctx.bar.removeTab(tabId);

    // Switch to another tab if this one was active
    if (ctx.activeTabId === tabId) {
      if (ctx.tabs.length > 0) {
        var newIdx = Math.min(idx, ctx.tabs.length - 1);
        ctx.switchToTab(ctx.tabs[newIdx].id);
      } else {
        ctx.activeTabId = null;
        ctx.showTabPane(null);
      }
    }
  }

  function closeAllTabs() {
    var ids = ctx.tabs.map(function (t) { return t.id; });
    for (var i = 0; i < ids.length; i++) {
      closeTab(ids[i]);
    }
  }

  function closeOtherTabs(keepTabId) {
    var ids = ctx.tabs.map(function (t) { return t.id; });
    for (var i = 0; i < ids.length; i++) {
      if (ids[i] !== keepTabId) closeTab(ids[i]);
    }
  }

  ctx.closeTab = closeTab;
  ctx.closeAllTabs = closeAllTabs;
  ctx.closeOtherTabs = closeOtherTabs;
}

function _attachLifecycleTabOpsMethods(ctx) {

  function renameTab(tabId, newName) {
    var tab = ctx.getTabById(tabId);
    if (tab && newName) {
      tab.name = newName;
      if (ctx.bar) ctx.bar.setTitle(tabId, newName);
    }
  }

  function _duplicateTab(tabId) {
    var tab = ctx.getTabById(tabId);
    if (!tab) return;

    var opts = {};
    for (var key in tab.options) {
      if (Object.prototype.hasOwnProperty.call(tab.options, key)) {
        opts[key] = tab.options[key];
      }
    }
    opts.name = tab.name + ' (' + t('terminal.duplicate') + ')';
    opts.color = tab.color;
    ctx.createTab(tab.kind, opts);
  }

  function _closeTabsToRight(tabId) {
    var index = -1;
    for (var i = 0; i < ctx.tabs.length; i++) {
      if (ctx.tabs[i].id === tabId) { index = i; break; }
    }
    if (index === -1) return;

    var toClose = ctx.tabs.slice(index + 1).map(function (t) { return t.id; });
    for (var j = 0; j < toClose.length; j++) {
      ctx.closeTab(toClose[j]);
    }
  }

  ctx.renameTab = renameTab;
  ctx.duplicateTab = _duplicateTab;
  ctx.closeTabsToRight = _closeTabsToRight;
}

function _attachLifecycleTabMoveMethods(ctx) {

  function _moveTab(tabId, direction) {
    var index = -1;
    for (var i = 0; i < ctx.tabs.length; i++) {
      if (ctx.tabs[i].id === tabId) { index = i; break; }
    }
    if (index === -1) return;

    var newIndex = direction === 'left' ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= ctx.tabs.length) return;

    var tab = ctx.tabs.splice(index, 1)[0];
    ctx.tabs.splice(newIndex, 0, tab);
    if (ctx.bar) ctx.bar.moveTab(tabId, newIndex);
  }

  /**
   * Export the scrollback buffer of a tab to a downloaded .txt file.
   */
  function _exportText(tabId) {
    var tab = ctx.getTabById(tabId);
    if (!tab || !tab.xterm) return;

    var buffer = tab.xterm.buffer.active;
    var content = '';
    for (var i = 0; i < buffer.length; i++) {
      var line = buffer.getLine(i);
      if (line) {
        content += line.translateToString(true) + '\n';
      }
    }

    var blob = new Blob([content], { type: 'text/plain' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = (tab.name || 'terminal') + '.txt';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }

  ctx.moveTab = _moveTab;
  ctx.exportText = _exportText;
}

function _attachLifecycleHistoryMethods(ctx) {

  function _clearHistory(tabId) {
    var tab = ctx.getTabById(tabId);
    if (!tab || !tab.ws || tab.ws.readyState !== WebSocket.OPEN) return;

    try {
      tab.ws.send(JSON.stringify({ type: 'clear' }));
      if (tab.xterm) {
        tab.xterm.clear();
        tab.xterm.write('\x1b[33m[' + t('terminal.historyCleared') + ']\x1b[0m\r\n');
      }
    } catch (e) {
      console.error('Failed to send clear command:', e);
    }
  }

  function _restartTerminal(tabId) {
    var tab = ctx.getTabById(tabId);
    if (!tab || !tab.ws || tab.ws.readyState !== WebSocket.OPEN) return;

    showConfirmDialog(t('terminal.restartConfirm'), {
      title: t('terminal.restartTitle'),
      confirmText: t('terminal.restartButton'),
      cancelText: t('common.cancel')
    }).then(function(confirmed) {
      if (!confirmed) return;

      try {
        var cols = tab.xterm ? tab.xterm.cols : 80;
        var rows = tab.xterm ? tab.xterm.rows : 24;
        tab.ws.send(JSON.stringify({ type: 'restart', cols: cols, rows: rows }));
        if (tab.xterm) {
          tab.xterm.clear();
          tab.xterm.write('\x1b[33m[' + t('terminal.restartingMsg') + ']\x1b[0m\r\n');
        }
      } catch (e) {
        console.error('Failed to send restart command:', e);
      }
    });
  }

  ctx.clearHistory = _clearHistory;
  ctx.restartTerminal = _restartTerminal;
}
