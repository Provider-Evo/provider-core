function _handleNavigationKeydown(e, tab) {
  if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return false;
  if (!tab) return true;
  e.preventDefault();
  var sorted = _sortEntries(tab);
  if (sorted.length === 0) return true;
  if (e.key === 'ArrowDown') {
    _selectedIndex = Math.min(_selectedIndex + 1, sorted.length - 1);
  } else {
    _selectedIndex = Math.max(_selectedIndex - 1, 0);
  }
  _lastSelectedPath = sorted[_selectedIndex].path;
  _renderContent();
  return true;
}

function _handleFileManagerActionsKeydown(e) {
  var panel = document.getElementById('tab-files');
  if (!panel || panel.classList.contains('hidden')) return;
  if (typeof getActiveTab === 'function' && getActiveTab() !== 'files') return;

  var active = document.activeElement;
  if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.tagName === 'SELECT')) return;

  var tab = _getActiveTab();

  if (_handleTabActionKeydown(e, tab)) return;
  if (_handleEntryActionKeydown(e, tab)) return;
  _handleNavigationKeydown(e, tab);
}
