/**
 * File Manager -- keyboard shortcut handlers for the files feature.
 * Split out of tabs.js/init() to keep functions under the length limit.
 *
 * Part of the files.js split. Depends on state.js and calls into
 * ops.js (_clipboardCopy/_clipboardCut/_clipboardPaste, _deleteEntries,
 * _showRenameDialog), dirlist.js (_loadDirectory, _goUp), files-search.js
 * (_focusSearch, _clearSearch, _hideSearchResults), tabs.js (createTab,
 * closeTab, _reopenLastTab), preview.js (_previewFile), dirlist.js
 * (_navigateTo).
 */

function _isFilesTabActive() {
  if (typeof switchTab === 'function' && typeof getActiveTab === 'function') {
    return getActiveTab() === 'files';
  }
  return true;
}

function _handleClipboardKeydown(e) {
  if (!e.ctrlKey && !e.metaKey) return;
  var tag = (e.target.tagName || '').toLowerCase();
  if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) return;
  if (!_isFilesTabActive()) return;
  var tab = _getActiveTab();
  if (!tab) return;
  if (!_lastSelectedPath) return;

  if (e.key === 'c' || e.key === 'C') {
    e.preventDefault();
    _clipboardCopy([_lastSelectedPath]);
    _renderContent();
  } else if (e.key === 'x' || e.key === 'X') {
    e.preventDefault();
    _clipboardCut([_lastSelectedPath]);
    _renderContent();
  } else if (e.key === 'v' || e.key === 'V') {
    if (_clipboard.paths.length > 0) {
      e.preventDefault();
      _clipboardPaste(tab);
    }
  }
}

function _handleSearchKeydown(e) {
  if (!_isFilesTabActive()) return;

  if ((e.key === 'f' && (e.ctrlKey || e.metaKey)) || e.key === 'F3') {
    e.preventDefault();
    _focusSearch();
    return;
  }

  if (e.key === 'Escape') {
    if (_searchInput && document.activeElement === _searchInput) {
      e.preventDefault();
      _clearSearch();
      _searchInput.blur();
      return;
    }
    if (_searchResults && _searchResults.classList.contains('visible')) {
      e.preventDefault();
      _hideSearchResults();
    }
  }
}

function _handleTabActionKeydown(e, tab) {
  if ((e.key === 't' || e.key === 'T') && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
    e.preventDefault();
    createTab(_projectRoot || '/');
    return true;
  }
  if ((e.key === 'w' || e.key === 'W') && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    if (tab) closeTab(tab.id);
    return true;
  }
  if ((e.key === 't' || e.key === 'T') && (e.ctrlKey || e.metaKey) && e.shiftKey) {
    e.preventDefault();
    _reopenLastTab();
    return true;
  }
  if (e.key === 'F5') {
    e.preventDefault();
    if (tab) _loadDirectory(tab, tab.path);
    return true;
  }
  return false;
}

function _handleEntryActionKeydown(e, tab) {
  if (e.key === 'Delete' && tab && _lastSelectedPath) {
    e.preventDefault();
    _deleteEntries(tab, [_lastSelectedPath]);
    return true;
  }
  if (e.key === 'F2' && tab && _lastSelectedPath) {
    e.preventDefault();
    var entries = _sortEntries(tab);
    for (var i = 0; i < entries.length; i++) {
      if (entries[i].path === _lastSelectedPath) {
        _showRenameDialog(tab, entries[i]);
        break;
      }
    }
    return true;
  }
  if (e.key === 'Enter' && tab && _selectedIndex >= 0) {
    e.preventDefault();
    var sorted = _sortEntries(tab);
    if (_selectedIndex < sorted.length) {
      var entry = sorted[_selectedIndex];
      if (entry.type === 'dir') {
        _navigateTo(tab, entry.path);
      } else {
        _previewFile(entry);
      }
    }
    return true;
  }
  if (e.key === 'Backspace' || (e.altKey && e.key === 'ArrowUp')) {
    e.preventDefault();
    if (tab) _goUp(tab);
    return true;
  }
  return false;
}

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
