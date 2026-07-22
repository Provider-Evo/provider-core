/**
 * Terminal resize/visibility tracking -- fit propagation to backend,
 * main-panel visibility detection, and split-pane status routing.
 *
 * Exposes via _attachResizeMethods(ctx):
 * - ctx.setBarStatus(tab, status)
 * - ctx.isMainTerminalPanelVisible()
 * - ctx.fitAndResize(tab, force)
 * - ctx.rememberDimensions(tab)
 * - ctx.watchMainTabVisibility()
 */
function _attachResizeMethods(ctx) {
  _attachResizeSubStatusBar(ctx);
  var _visibility = _attachResizeSubVisibility(ctx);
  var _dimensions = _attachResizeSubDimensions(ctx);
  _attachResizeSubFit(ctx, _visibility, _dimensions);
  _attachResizeSubWatch(ctx, _visibility, _dimensions);
}

/**
 * Push a status update for a tab to the TabBar, routing split panes to
 * the secondary (paired) dot instead of the primary one.
 */
function _attachResizeSubStatusBar(ctx) {
  function _setBarStatus(tab, status) {
    if (!ctx.bar) return;
    if (tab._isSplit) {
      var parentId = tab._parentId;
      if (!parentId) return;
      var parent = ctx.getTabById(parentId);
      if (!parent || !parent.split) return;
      ctx.bar.setSplitStatus(parentId, status);
    } else {
      ctx.bar.setStatus(tab.id, status);
    }
  }

  ctx.setBarStatus = _setBarStatus;
}

function _attachResizeSubVisibility(ctx) {
  function _isMainTerminalPanelVisible() {
    var panel = document.getElementById('tab-terminal');
    return !!(panel && panel.classList.contains('active') && !panel.classList.contains('hidden'));
  }

  function _isTabPaneVisible(tab) {
    if (!tab || !_isMainTerminalPanelVisible()) return false;
    // Use the xterm container's actual rendered box instead of matching
    // 'terminal-pane-<id>' by id: split panes (id = '<tabId>-split') live
    // inside the primary tab's pane element, so no such id ever exists for
    // them and this check previously always returned false for splits,
    // silently skipping fit()/resize propagation whenever the split pane's
    // container was resized (window resize, sidebar toggle, etc).
    var container = tab._container;
    if (!container) return false;
    return container.offsetWidth > 0 && container.offsetHeight > 0;
  }

  ctx.isMainTerminalPanelVisible = _isMainTerminalPanelVisible;

  return {
    isMainTerminalPanelVisible: _isMainTerminalPanelVisible,
    isTabPaneVisible: _isTabPaneVisible,
  };
}

function _attachResizeSubDimensions(ctx) {
  function _rememberDimensions(tab) {
    if (!tab || !tab.xterm) return;
    if (tab.xterm.cols >= 2 && tab.xterm.rows >= 2) {
      tab._lastCols = tab.xterm.cols;
      tab._lastRows = tab.xterm.rows;
    }
  }

  function _sendResize(tab) {
    if (!tab.ws || tab.ws.readyState !== WebSocket.OPEN || !tab.xterm) return;
    var cols = tab.xterm.cols;
    var rows = tab.xterm.rows;
    if (cols < 2 || rows < 2) return;
    if (tab._sentCols === cols && tab._sentRows === rows) return;
    tab._sentCols = cols;
    tab._sentRows = rows;
    tab.ws.send(JSON.stringify({
      type: 'resize',
      cols: cols,
      rows: rows,
    }));
  }

  ctx.rememberDimensions = _rememberDimensions;

  return {
    rememberDimensions: _rememberDimensions,
    sendResize: _sendResize,
  };
}

function _attachResizeSubFit(ctx, visibility, dimensions) {
  function _fitAndResize(tab, force) {
    if (!tab || !tab.xterm || !tab.fitAddon) return;
    if (!force && !visibility.isTabPaneVisible(tab)) return;

    var prevCols = tab._lastCols || tab.xterm.cols;
    var prevRows = tab._lastRows || tab.xterm.rows;

    try {
      tab.fitAddon.fit();
    } catch (e) {
      return;
    }

    if (tab.xterm.cols < 2 || tab.xterm.rows < 2) {
      if (prevCols >= 2 && prevRows >= 2) {
        tab.xterm.resize(prevCols, prevRows);
      }
      return;
    }

    dimensions.rememberDimensions(tab);
    dimensions.sendResize(tab);
  }

  ctx.fitAndResize = _fitAndResize;

  return _fitAndResize;
}

function _attachResizeSubWatch(ctx, visibility, dimensions) {
  function _watchMainTabVisibility() {
    var panel = document.getElementById('tab-terminal');
    if (!panel || typeof MutationObserver === 'undefined') return;
    var observer = new MutationObserver(function () {
      if (visibility.isMainTerminalPanelVisible()) {
        var tab = ctx.getActiveTab();
        if (!tab) return;
        requestAnimationFrame(function () {
          ctx.fitAndResize(tab, true);
        });
        return;
      }
      for (var i = 0; i < ctx.tabs.length; i++) {
        dimensions.rememberDimensions(ctx.tabs[i]);
      }
    });
    observer.observe(panel, { attributes: true, attributeFilter: ['class'] });
  }

  ctx.watchMainTabVisibility = _watchMainTabVisibility;
}
