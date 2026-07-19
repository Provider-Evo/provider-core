// Terminal tab color -- thin wrapper around shared tabbar_color.js.
// Handles terminal-specific persistence keyed by tab.sessionId.

var _savedTabColors = {};

function _attachColorMethods(ctx) {
  _attachColorPersistMethods(ctx);
  _attachColorTabMethods(ctx);
  _attachColorPickerShowMethods(ctx);
}

function _attachColorPersistMethods(ctx) {

  /**
   * Persist tab colors keyed by session ID (survives reconnection/reload).
   */
  async function _saveTabColors() {
    try {
      if (typeof persistSave !== 'function') return;
      var existing = await persistLoad('terminals.json') || {};
      var colors = {};
      for (var i = 0; i < ctx.tabs.length; i++) {
        var tab = ctx.tabs[i];
        var key = tab.sessionId || tab.id;
        if (tab.color) colors[key] = tab.color;
      }
      existing.tabColors = colors;
      await persistSave('terminals.json', existing);
    } catch (e) { /* ignore */ }
  }

  async function _loadTabColors() {
    try {
      if (typeof persistLoad !== 'function') return;
      var data = await persistLoad('terminals.json');
      if (data && data.tabColors) _savedTabColors = data.tabColors;
    } catch (e) { /* ignore */ }
  }

  /**
   * Apply a previously-persisted color to a tab once its session ID is
   * known (called after createTab/reconnect assigns tab.sessionId).
   */
  function _applySavedColor(tab) {
    var key = tab.sessionId || tab.id;
    var color = _savedTabColors[key];
    if (color) {
      tab.color = color;
      if (ctx.bar) ctx.bar.setColor(tab.id, color);
    }
  }

  ctx.saveTabColors = _saveTabColors;
  ctx.loadTabColors = _loadTabColors;
  ctx.applySavedColor = _applySavedColor;
}

function _attachColorTabMethods(ctx) {

  /**
   * Set a tab's color, apply it to the TabBar indicator and persist it.
   */
  function _setTabColor(tabId, color) {
    var tab = ctx.getTabById(tabId);
    if (!tab) return;
    tab.color = color || '';
    if (ctx.bar) ctx.bar.setColor(tabId, tab.color);
    ctx.saveTabColors();
  }

  function _hideColorPicker() {
    _hideTabColorPicker();
  }

  ctx.setTabColor = _setTabColor;
  ctx.hideColorPicker = _hideColorPicker;
}

function _attachColorPickerShowMethods(ctx) {

  /**
   * Show the tab color picker anchored at the given screen coordinates.
   */
  function _showColorPicker(tabId, x, y) {
    var tab = ctx.getTabById(tabId);
    if (!tab) return;
    _showTabColorPicker(tabId, x, y, {
      currentColor: tab.color || '',
      headerLabel: t('terminal.tabColor'),
      onApply: function (color) { ctx.setTabColor(tabId, color); },
      onReset: function () { ctx.setTabColor(tabId, null); },
    });
  }

  ctx.showColorPicker = _showColorPicker;
}
