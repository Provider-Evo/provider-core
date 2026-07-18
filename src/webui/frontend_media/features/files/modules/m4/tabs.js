/**
 * File Manager -- initialization, tab lifecycle, and session persistence.
 *
 * Part of the files.js split. Depends on state.js (shared vars/helpers)
 * and calls into render.js (_renderContent), dirlist.js
 * (_loadDirectory), menu.js (_showTabContextMenu, _showBgContextMenu),
 * upload.js (_uploadFiles), kbd.js (keydown handlers). Must load
 * after all of those modules define their functions, since bindings
 * resolve at call time.
 */

function _buildTabBarOptions() {
  return {
    tabBarEl: _tabBar,
    bodyEl: _body,
    layout: 'horizontal',
    collapsed: false,
    closeAllThreshold: 6,
    onSwitch: function (id) { _switchToTab(id); },
    onClose: function (id) { closeTab(id); },
    onContextMenu: function (id, event) { _showTabContextMenu(event, id); },
    onAdd: function () { createTab(_projectRoot || '/'); },
    onCloseAll: function () { _closeAllTabs(); },
    onToggleCollapsed: _onToggleCollapsed,
  };
}

function _onToggleCollapsed(collapsed) {
  propagateTabBarCollapsed(_bar, collapsed);
}

function _setupTabBar() {
  if (typeof TabBar === 'undefined') return;

  _bar = TabBar.create(_container, _buildTabBarOptions());

  // Register in global registry for bootstrap.js layout toggle
  if (window._tabBars) {
    window._tabBars.files = _bar;
  }

  // Apply current layout from _tabLayoutConfig (may have been loaded from persist)
  if (typeof _tabLayoutConfig !== 'undefined') {
    _bar.setLayout(_tabLayoutConfig.layout || 'horizontal', _tabLayoutConfig.sidebarCompressed || false);
  }
}

function _setupUploadInput() {
  if (document.getElementById('filesUploadInput')) return;
  var fileInput = document.createElement('input');
  fileInput.type = 'file';
  fileInput.multiple = true;
  fileInput.id = 'filesUploadInput';
  fileInput.style.display = 'none';
  document.body.appendChild(fileInput);
  fileInput.addEventListener('change', function () {
    var tab = _getActiveTab();
    if (tab && fileInput.files.length > 0) {
      _uploadFiles(tab, tab.path, fileInput.files);
    }
    // Reset so the same file can be selected again
    fileInput.value = '';
  });
}

function _setupKeyboardShortcuts() {
  document.addEventListener('keydown', _handleClipboardKeydown);
  document.addEventListener('keydown', _handleSearchKeydown);
  document.addEventListener('keydown', _handleFileManagerActionsKeydown, true);
}

async function init() {
  _container = document.getElementById('filesContainer');
  _tabBar = document.getElementById('filesTabBar');
  _body = document.getElementById('filesBody');
  if (!_container || !_tabBar || !_body) return;

  _setupTabBar();

  document.addEventListener('click', function () { _hideContextMenu(); });

  _setupKeyboardShortcuts();
  _setupUploadInput();

  // Register with Router
  if (typeof Router !== 'undefined') {
    Router.register('files', {
      activate: function () { _onActivate(); },
      deactivate: function () { _onDeactivate(); },
    });
  }

  // Fetch drives and project root before restoring session
  await _fetchDrives();
  await _fetchProjectRoot();

  // Load persisted tab colors before restoring session so colors are
  // available when _restoreSessionFromData applies them.
  if (typeof _loadFileTabColors === 'function') {
    await _loadFileTabColors();
  }

  // Restore saved tabs
  _restoreSession();

  // Background right-click on files body
  _body.addEventListener('contextmenu', function (e) {
    if (e.target.closest('tr') || e.target.closest('.files-toolbar')) return;
    e.preventDefault();
    var tab = _getActiveTab();
    if (tab) _showBgContextMenu(e, tab);
  });
}

function _onActivate() {
  // Refresh current tab listing
  var tab = _getActiveTab();
  if (tab) _loadDirectory(tab, tab.path);
}

function _onDeactivate() { /* nothing special */ }

// ========================= Tab Management =========================

function _createTabState(path, name) {
  return {
    id: 'file-' + _tabCounter + '-' + Date.now(),
    name: name,
    path: path,
    color: '',
    history: [path],
    historyIdx: 0,
    entries: [],
    sortCol: 'name',
    sortAsc: true,
    loading: false,
    _lazyOffset: 0,
    _lazyTotal: 0,
    _lazyLimit: 200,
    _lazyLoadingMore: false,
    _lazyAllLoaded: false,
    isDrives: false,
  };
}

function createTab(path) {
  if (typeof switchTab === 'function') switchTab('files');

  _tabCounter++;
  path = path || _projectRoot || '/';
  var name = _pathDisplayName(path);
  var tab = _createTabState(path, name);
  var tabId = tab.id;

  _tabs.push(tab);

  // Add tab to TabBar with folder icon
  if (_bar) {
    _bar.addTab({
      id: tabId,
      type: 'file',
      icon: '&#128193;',
      title: name,
      closable: true,
    });
    _bar.setActive(tabId);
  }

  _activeTabId = tabId;
  _renderContent();
  _loadDirectory(tab, path);
  _saveSession();
  return tab;
}

function _switchToTab(tabId) {
  _activeTabId = tabId;
  if (_bar) _bar.setActive(tabId);
  _renderContent();
  localStorage.setItem('files_last_active_tab', tabId);
}

function closeTab(tabId) {
  var idx = -1;
  for (var i = 0; i < _tabs.length; i++) {
    if (_tabs[i].id === tabId) { idx = i; break; }
  }
  if (idx === -1) return;

  // Save for Ctrl+Shift+T reopen
  _closedTabs.push({ path: _tabs[idx].path });
  if (_closedTabs.length > 20) _closedTabs.shift();

  _tabs.splice(idx, 1);

  // Remove from TabBar
  if (_bar) _bar.removeTab(tabId);

  if (_activeTabId === tabId) {
    if (_tabs.length > 0) {
      var newIdx = Math.min(idx, _tabs.length - 1);
      _switchToTab(_tabs[newIdx].id);
    } else {
      _activeTabId = null;
      _renderContent();
    }
  }
  _saveSession();
}

function _reopenLastTab() {
  if (_closedTabs.length === 0) return;
  var info = _closedTabs.pop();
  createTab(info.path);
}

function _getActiveTab() {
  for (var i = 0; i < _tabs.length; i++) {
    if (_tabs[i].id === _activeTabId) return _tabs[i];
  }
  return null;
}

// ========================= Close helpers =========================

function _closeOtherTabs(keepId) {
  var ids = _tabs.map(function (t) { return t.id; });
  for (var i = 0; i < ids.length; i++) {
    if (ids[i] !== keepId) closeTab(ids[i]);
  }
}

function _closeAllTabs() {
  var ids = _tabs.map(function (t) { return t.id; });
  for (var i = 0; i < ids.length; i++) { closeTab(ids[i]); }
}

// ========================= Session Persistence =========================

async function _saveSession() {
  // Skip save while restoration is in progress to avoid writing
  // partial state (e.g., only 1 of N tabs recreated so far).
  if (_restoringSession) return;
  var activeIdx = -1;
  for (var i = 0; i < _tabs.length; i++) {
    if (_tabs[i].id === _activeTabId) { activeIdx = i; break; }
  }
  var data = {
    tabs: _tabs.map(function (t) {
      return { path: t.path, name: t.name, color: t.color || '' };
    }),
    activeTabId: _activeTabId,
    activeTabIndex: activeIdx,
  };
  if (typeof persistSave === 'function') {
    await persistSave('files.json', data);
  }
}

function _resolveRestoreIndex(data) {
  var restoreIdx = data.activeTabIndex;
  if (restoreIdx != null && restoreIdx >= 0 && restoreIdx < _tabs.length) return restoreIdx;
  // Fallback: try matching by saved ID, then default to last tab
  restoreIdx = _tabs.length - 1;
  if (data.activeTabId) {
    for (var j = 0; j < _tabs.length; j++) {
      if (_tabs[j].id === data.activeTabId) return j;
    }
  }
  return restoreIdx;
}

async function _restoreSessionFromData(data) {
  // Suppress _saveSession during batch creation to avoid
  // overwriting the saved state with partial data.
  _restoringSession = true;
  for (var i = 0; i < data.tabs.length; i++) {
    var tab = createTab(data.tabs[i].path);
    // Restore persisted name if it was renamed
    if (data.tabs[i].name && tab) {
      tab.name = data.tabs[i].name;
      if (_bar) _bar.setTitle(tab.id, tab.name);
    }
    // Restore persisted color
    if (data.tabs[i].color && tab) {
      _applyFileTabColor(tab, data.tabs[i].color);
    }
  }
  _restoringSession = false;

  var restoreIdx = _resolveRestoreIndex(data);
  if (restoreIdx >= 0 && restoreIdx < _tabs.length) {
    _switchToTab(_tabs[restoreIdx].id);
  }

  // Persist the now-complete restored state
  _saveSession();
}

async function _restoreSession() {
  try {
    if (typeof persistLoad === 'function') {
      var data = await persistLoad('files.json');
      if (data && data.tabs && data.tabs.length > 0) {
        await _restoreSessionFromData(data);
        return;
      }
    }
  } catch (e) { /* ignore */ }

  // No saved session — open at project root
  _restoringSession = false;
  createTab(_projectRoot || '/');
}

// ========================= Public entry point =========================

function openPath(path) {
  if (!path) return;
  if (typeof switchTab === 'function') switchTab('files');
  var tab = _getActiveTab();
  if (!tab) {
    createTab(path);
    return;
  }
  _navigateTo(tab, path, true);
}

// ========================= Tab Manipulation =========================

function renameTab(tabId) {
  var tab = _getTabById(tabId);
  if (!tab) return;
  showInputDialog(
    t('files.renameTabTitle'),
    t('files.renameTabPrompt'),
    tab.name,
    t('files.renameTabPlaceholder')
  ).then(function (newName) {
    if (!newName || !newName.trim()) return;
    tab.name = newName.trim();
    if (_bar) _bar.setTitle(tabId, tab.name);
    _saveSession();
  });
}

function moveTab(tabId, direction) {
  var idx = -1;
  for (var i = 0; i < _tabs.length; i++) {
    if (_tabs[i].id === tabId) { idx = i; break; }
  }
  if (idx === -1) return;
  var newIdx = direction === 'left' ? idx - 1 : idx + 1;
  if (newIdx < 0 || newIdx >= _tabs.length) return;
  var tmp = _tabs[idx];
  _tabs[idx] = _tabs[newIdx];
  _tabs[newIdx] = tmp;
  if (_bar) _bar.moveTab(tabId, newIdx);
  _saveSession();
}

function duplicateTab(tabId) {
  var tab = _getTabById(tabId);
  if (!tab) return;
  createTab(tab.path);
}
