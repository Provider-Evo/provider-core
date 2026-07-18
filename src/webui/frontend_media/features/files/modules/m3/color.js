/**
 * File Manager -- tab color picker integration.
 *
 * Wraps the shared tabbar_color.js picker for the files bundle.
 * Persists colors inside files.json under the "tabColors" key.
 */

var _fileTabColors = {};

/**
 * Apply a color (from persistence or direct assignment) to a tab object.
 * Does not persist -- callers that need persistence use _setFileTabColor.
 */
function _applyFileTabColor(tab, color) {
  tab.color = color || '';
  if (_bar) _bar.setColor(tab.id, tab.color);
}

/**
 * Set a tab's color, apply it to the TabBar and persist.
 */
async function _setFileTabColor(tabId, color) {
  var tab = _getTabById(tabId);
  if (!tab) return;
  _applyFileTabColor(tab, color);
  _fileTabColors[tabId] = color || '';
  await _saveFileTabColors();
  // Also keep color in session data so it survives full reload
  _saveSession();
}

async function _saveFileTabColors() {
  try {
    if (typeof persistSave === 'function') {
      var existing = await persistLoad('files.json') || {};
      existing.tabColors = _fileTabColors;
      await persistSave('files.json', existing);
    }
  } catch (e) { /* ignore */ }
}

async function _loadFileTabColors() {
  try {
    if (typeof persistLoad === 'function') {
      var data = await persistLoad('files.json');
      if (data && data.tabColors) _fileTabColors = data.tabColors;
    }
  } catch (e) { /* ignore */ }
}

/**
 * Show the shared tab color picker anchored to the given screen coordinates.
 */
function _showFileTabColorPicker(tabId, x, y) {
  var tab = _getTabById(tabId);
  if (!tab) return;
  _showTabColorPicker(tabId, x, y, {
    currentColor: tab.color || '',
    headerLabel: t('files.tabColor'),
    onApply: function (color) { _setFileTabColor(tabId, color); },
    onReset: function () { _setFileTabColor(tabId, null); },
  });
}
