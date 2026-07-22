// ========================= Terminal: Split Layout Persistence =========================
// Persists primary/split session pairing to terminals.json so page refresh
// can restore the two-pane layout instead of showing two separate tabs.

function _tabSessionKey(tab) {
  if (!tab) return '';
  return tab.sessionId || tab.id || '';
}

async function _splitpersistLoadLayouts() {
  try {
    if (typeof persistLoad !== 'function') return {};
    var data = await persistLoad('terminals.json');
    if (!data || !data.splitLayouts || typeof data.splitLayouts !== 'object') return {};
    return data.splitLayouts;
  } catch (e) {
    return {};
  }
}

async function _splitpersistWriteLayouts(layouts) {
  try {
    if (typeof mergeTerminalsPersist === 'function') {
      await mergeTerminalsPersist({ splitLayouts: layouts || {} });
    } else if (typeof persistSave === 'function' && typeof persistLoad === 'function') {
      var existing = await persistLoad('terminals.json') || {};
      existing.splitLayouts = layouts || {};
      await persistSave('terminals.json', existing);
    }
  } catch (e) {
    // ignore persist errors
  }
}

function _splitpersistFindTab(ctx, sessionId) {
  for (var i = 0; i < ctx.tabs.length; i++) {
    var tab = ctx.tabs[i];
    if (tab.sessionId === sessionId || tab.id === sessionId) return tab;
  }
  return null;
}

function _splitpersistChildIndex(layouts) {
  var childToPrimary = {};
  var keys = Object.keys(layouts || {});
  for (var i = 0; i < keys.length; i++) {
    var primaryId = keys[i];
    var entry = layouts[primaryId];
    if (entry && entry.splitSessionId) {
      childToPrimary[entry.splitSessionId] = primaryId;
    }
  }
  return childToPrimary;
}

function _splitpersistSessionAlive(sessions, sessionId) {
  for (var i = 0; i < sessions.length; i++) {
    if (sessions[i].session_id === sessionId && sessions[i].alive) return true;
  }
  return false;
}

function _attachSplitpersistIo(ctx) {
  async function _saveSplitLayout(parentTab, splitState, activePane) {
    var primaryId = _tabSessionKey(parentTab);
    var splitId = _tabSessionKey(splitState);
    if (!primaryId || !splitId) return;
    var layouts = await _splitpersistLoadLayouts();
    layouts[primaryId] = {
      splitSessionId: splitId,
      activePane: activePane || parentTab._activePane || 'primary',
    };
    await _splitpersistWriteLayouts(layouts);
  }

  async function _clearSplitLayout(parentTab) {
    var primaryId = _tabSessionKey(parentTab);
    if (!primaryId) return;
    var layouts = await _splitpersistLoadLayouts();
    if (!layouts[primaryId]) return;
    delete layouts[primaryId];
    await _splitpersistWriteLayouts(layouts);
  }

  async function _persistSplitActivePane(parentTab) {
    if (!parentTab || !parentTab.split) return;
    var primaryId = _tabSessionKey(parentTab);
    var splitId = _tabSessionKey(parentTab.split);
    if (!primaryId || !splitId) return;
    var layouts = await _splitpersistLoadLayouts();
    if (!layouts[primaryId]) return;
    layouts[primaryId].activePane = parentTab._activePane || 'primary';
    await _splitpersistWriteLayouts(layouts);
  }

  ctx.loadSplitLayouts = _splitpersistLoadLayouts;
  ctx.saveSplitLayout = _saveSplitLayout;
  ctx.clearSplitLayout = _clearSplitLayout;
  ctx.persistSplitActivePane = _persistSplitActivePane;
  ctx.buildSplitChildIndex = _splitpersistChildIndex;
}

function _attachSplitpersistRestore(ctx) {
  async function _restoreSplitLayouts(sessions) {
    var layouts = await _splitpersistLoadLayouts();
    var keys = Object.keys(layouts);
    if (!keys.length) return;

    var dirty = false;
    for (var i = 0; i < keys.length; i++) {
      var primaryId = keys[i];
      var entry = layouts[primaryId];
      if (!entry || !entry.splitSessionId) {
        delete layouts[primaryId];
        dirty = true;
        continue;
      }
      var alive = _splitpersistSessionAlive(sessions, primaryId)
        && _splitpersistSessionAlive(sessions, entry.splitSessionId);
      if (!alive) {
        delete layouts[primaryId];
        dirty = true;
        continue;
      }
      var parentTab = _splitpersistFindTab(ctx, primaryId);
      if (!parentTab || parentTab.split) continue;
      if (typeof ctx.restoreSplitPane === 'function') {
        ctx.restoreSplitPane(parentTab, entry.splitSessionId, entry.activePane || 'primary');
      }
    }
    if (dirty) await _splitpersistWriteLayouts(layouts);
  }

  function _onSplitPaneReady(splitState) {
    if (!splitState || !splitState._isSplit || !splitState._parentId) return;
    var parentTab = ctx.getTabById(splitState._parentId);
    if (!parentTab || !parentTab.split) return;
    if (!parentTab.sessionId || !splitState.sessionId) return;
    ctx.saveSplitLayout(parentTab, splitState, parentTab._activePane);
  }

  ctx.restoreSplitLayouts = _restoreSplitLayouts;
  ctx.onSplitPaneReady = _onSplitPaneReady;
}

function _attachSplitPersistMethods(ctx) {
  _attachSplitpersistIo(ctx);
  _attachSplitpersistRestore(ctx);
}
