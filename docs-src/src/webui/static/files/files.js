/**
 * File Manager Tab — directory browsing with tab management.
 *
 * Features:
 * - Horizontal tab bar (create/switch/close)
 * - Directory listing with sortable columns
 * - Breadcrumb navigation and back/forward history
 * - Editable address bar
 * - Right-click context menu (open, download, rename, delete, new folder)
 * - File preview modal (text with line numbers, images inline)
 * - Download files
 * - Session persistence via persist API
 */
var FileManager = (function () {
  var _tabs = [];
  var _activeTabId = null;
  var _tabCounter = 0;
  var _contextMenu = null;
  var _clipboard = { action: null, paths: [] }; // action: 'copy' or 'cut'
  var _lastSelectedPath = null; // last right-clicked entry path for keyboard shortcuts
  var _closedTabs = []; // history of closed tabs for Ctrl+Shift+T reopen
  var _selectedIndex = -1; // keyboard-selected row index in sorted entries
  var _restoringSession = false; // flag to suppress _saveSession during restoration

  // Search state
  var _searchInput = null;
  var _searchResults = null;
  var _searchDebounceTimer = null;
  var _searchActiveIdx = -1;
  var _searchAbortCtrl = null;

  // Filesystem root state (drives on Windows, ["/"] on Linux)
  var _drives = null;       // cached from GET /v1/webui/files/drives
  var _projectRoot = null;  // cached from GET /v1/webui/files/project-root

  // DOM references
  var _container = null;
  var _tabBar = null;
  var _body = null;

  // TabBar instance
  var _bar = null;

  // ========================= Initialization =========================

  async function _fetchDrives() {
    try {
      var data = await Api.fetchJson('/v1/webui/files/drives');
      _drives = data.drives || ['/'];
    } catch (e) {
      _drives = ['/'];
    }
  }

  async function _fetchProjectRoot() {
    try {
      var data = await Api.fetchJson('/v1/webui/files/project-root');
      _projectRoot = data.path || '/';
    } catch (e) {
      _projectRoot = '/';
    }
  }

  /**
   * Return true when *path* represents the OS "root" view
   * (the drives list on Windows, or "/" on Linux).
   */
  function _isRootView(path) {
    if (!path || path === '/') return true;
    return false;
  }

  /**
   * Return the parent of *path*, or "/" if already at the root.
   * Works with both Unix (/home/user) and Windows (C:\Users) paths.
   */
  function _parentPath(path) {
    if (!path || path === '/') return '/';

    // Normalise separators
    var norm = path.replace(/\\/g, '/');

    // Windows drive root: "C:/" → "/"  (drives view)
    if (/^[a-zA-Z]:\/?$/.test(norm)) return '/';

    // Strip trailing separator
    norm = norm.replace(/[\/\\]+$/, '');

    var lastSlash = norm.lastIndexOf('/');
    if (lastSlash <= 0) {
      // Check if it's a Windows path like "C:" (no slash at all after norm)
      if (/^[a-zA-Z]:$/.test(norm)) return '/';
      // Plain Unix path like "/foo" → parent is "/"
      return '/';
    }

    var parent = norm.substring(0, lastSlash);

    // Windows: "C:/Users" → "C:\"
    var winMatch = parent.match(/^([a-zA-Z]:)$/);
    if (winMatch) return winMatch[1] + '\\';

    // Windows: "C:/Users" parent might be "C:" → that's the drive root
    // Already handled above by the regex test

    return parent;
  }

  /**
   * Join a directory path with a child name, cross-platform.
   */
  function _pathJoin(basePath, name) {
    if (!basePath || basePath === '/') return '/' + name;
    var norm = basePath.replace(/\\/g, '/');
    if (norm.endsWith('/')) return norm + name;
    // Windows drive root: "C:\" → "C:\name"
    if (/^[a-zA-Z]:\\$/.test(basePath)) return basePath + name;
    return basePath.replace(/[\/\\]+$/, '') + '/' + name;
  }

  async function init() {
    _container = document.getElementById('filesContainer');
    _tabBar = document.getElementById('filesTabBar');
    _body = document.getElementById('filesBody');
    if (!_container || !_tabBar || !_body) return;

    // Create the unified TabBar instance
    if (typeof TabBar !== 'undefined') {
      _bar = TabBar.create(_container, {
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
        onToggleCollapsed: function (collapsed) {
          if (typeof _tabLayoutConfig !== 'undefined') {
            _tabLayoutConfig.sidebarCompressed = collapsed;
            // Propagate collapsed state to ALL registered TabBar instances
            // so both terminal and files sidebars expand/compress together.
            var bars = window._tabBars || {};
            var keys = Object.keys(bars);
            for (var i = 0; i < keys.length; i++) {
              if (bars[keys[i]] !== _bar && bars[keys[i]] && typeof bars[keys[i]].setCollapsed === 'function') {
                bars[keys[i]].setCollapsed(collapsed);
              }
            }
            (async function () {
              var existing = await persistLoad('config.toml') || {};
              existing.layout = _tabLayoutConfig.layout;
              existing.sidebarCompressed = collapsed;
              persistSave('config.toml', existing);
            })();
          }
        },
      });

      // Register in global registry for bootstrap.js layout toggle
      if (window._tabBars) {
        window._tabBars.files = _bar;
      }

      // Apply current layout from _tabLayoutConfig (may have been loaded from persist)
      if (typeof _tabLayoutConfig !== 'undefined') {
        _bar.setLayout(_tabLayoutConfig.layout || 'horizontal', _tabLayoutConfig.sidebarCompressed || false);
      }
    }

    document.addEventListener('click', function () { _hideContextMenu(); });

    // Keyboard shortcuts for clipboard operations
    document.addEventListener('keydown', function (e) {
      if (!e.ctrlKey && !e.metaKey) return;
      // Skip when focus is in an input, textarea, or editable element
      var tag = (e.target.tagName || '').toLowerCase();
      if (tag === 'input' || tag === 'textarea' || e.target.isContentEditable) return;
      // Only handle when files tab is active
      if (typeof switchTab === 'function' && typeof getActiveTab === 'function') {
        if (getActiveTab() !== 'files') return;
      }
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
    });

    // Hidden file input for uploads
    if (!document.getElementById('filesUploadInput')) {
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

    // Search keyboard shortcuts
    document.addEventListener('keydown', function (e) {
      // Only handle when files tab is active
      if (typeof switchTab === 'function' && typeof getActiveTab === 'function') {
        if (getActiveTab() !== 'files') return;
      }

      // Ctrl+F or F3: focus search input
      if ((e.key === 'f' && (e.ctrlKey || e.metaKey)) || e.key === 'F3') {
        e.preventDefault();
        _focusSearch();
        return;
      }

      // Escape: clear and close search
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
          return;
        }
      }
    });

    // Keyboard shortcuts for file manager actions
    document.addEventListener('keydown', function (e) {
      // Only when files tab is active
      var panel = document.getElementById('tab-files');
      if (!panel || panel.classList.contains('hidden')) return;
      if (typeof getActiveTab === 'function' && getActiveTab() !== 'files') return;

      // Skip if focus is on input/textarea/select
      var active = document.activeElement;
      if (active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.tagName === 'SELECT')) return;

      var tab = _getActiveTab();

      // Ctrl+T: New tab
      if ((e.key === 't' || e.key === 'T') && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
        e.preventDefault();
        createTab(_projectRoot || '/');
        return;
      }

      // Ctrl+W: Close current tab
      if ((e.key === 'w' || e.key === 'W') && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        if (tab) closeTab(tab.id);
        return;
      }

      // Ctrl+Shift+T: Reopen last closed tab
      if ((e.key === 't' || e.key === 'T') && (e.ctrlKey || e.metaKey) && e.shiftKey) {
        e.preventDefault();
        _reopenLastTab();
        return;
      }

      // F5: Refresh
      if (e.key === 'F5') {
        e.preventDefault();
        if (tab) _loadDirectory(tab, tab.path);
        return;
      }

      // Delete: Delete selected file(s)
      if (e.key === 'Delete' && tab && _lastSelectedPath) {
        e.preventDefault();
        _deleteEntries(tab, [_lastSelectedPath]);
        return;
      }

      // F2: Rename selected file
      if (e.key === 'F2' && tab && _lastSelectedPath) {
        e.preventDefault();
        var entries = _sortEntries(tab);
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].path === _lastSelectedPath) {
            _showRenameDialog(tab, entries[i]);
            break;
          }
        }
        return;
      }

      // Enter: Open selected file/directory
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
        return;
      }

      // Backspace or Alt+Up: Navigate to parent directory
      if (e.key === 'Backspace' || (e.altKey && e.key === 'ArrowUp')) {
        e.preventDefault();
        if (tab) _goUp(tab);
        return;
      }

      // ArrowUp / ArrowDown: Navigate entries
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        if (!tab) return;
        e.preventDefault();
        var sorted2 = _sortEntries(tab);
        if (sorted2.length === 0) return;
        if (e.key === 'ArrowDown') {
          _selectedIndex = Math.min(_selectedIndex + 1, sorted2.length - 1);
        } else {
          _selectedIndex = Math.max(_selectedIndex - 1, 0);
        }
        _lastSelectedPath = sorted2[_selectedIndex].path;
        _renderContent();
        return;
      }
    }, true);

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

  function createTab(path) {
    if (typeof switchTab === 'function') switchTab('files');

    _tabCounter++;
    var tabId = 'file-' + _tabCounter + '-' + Date.now();
    path = path || _projectRoot || '/';
    var name = _pathDisplayName(path);

    var tab = {
      id: tabId,
      name: name,
      path: path,
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
    };

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
    _saveSession();
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

  // ========================= Directory Loading =========================

  async function _loadDirectory(tab, path) {
    tab.loading = true;
    tab._lazyOffset = 0;
    tab._lazyLoadingMore = false;
    tab._lazyAllLoaded = false;
    _renderContent();

    try {
      var url = '/v1/webui/files/list?path=' + encodeURIComponent(path) +
        '&offset=0&limit=' + tab._lazyLimit;
      var data = await Api.fetchJson(url);
      tab.entries = data.entries || [];
      tab.path = data.path || path;
      tab.name = _pathDisplayName(tab.path);
      tab.loading = false;
      tab._lazyOffset = tab.entries.length;
      tab._lazyTotal = (data.total != null) ? data.total : tab.entries.length;
      tab._lazyLimit = (data.limit != null) ? data.limit : 200;
      tab._lazyAllLoaded = (tab._lazyOffset >= tab._lazyTotal);
      if (_bar) _bar.setTitle(tab.id, tab.name);
      _renderContent();
    } catch (e) {
      tab.loading = false;
      tab.entries = [];
      tab._lazyAllLoaded = true;
      tab._lazyTotal = 0;
      _renderContent();
      if (typeof toast === 'function') toast('加载目录失败: ' + e.message, 'error');
    }
  }

  /**
   * Load the next batch of entries for lazy-loading large directories.
   * Appends to tab.entries and updates the virtual scroll incrementally.
   */
  async function _loadMore(tab) {
    if (tab._lazyLoadingMore || tab._lazyAllLoaded) return;
    if (tab._lazyOffset >= tab._lazyTotal) {
      tab._lazyAllLoaded = true;
      return;
    }

    tab._lazyLoadingMore = true;
    _showLazyLoadingIndicator(tab);

    try {
      var url = '/v1/webui/files/list?path=' + encodeURIComponent(tab.path) +
        '&offset=' + tab._lazyOffset + '&limit=' + tab._lazyLimit;
      var data = await Api.fetchJson(url);
      var newEntries = data.entries || [];
      tab.entries = tab.entries.concat(newEntries);
      tab._lazyOffset += newEntries.length;
      tab._lazyTotal = (data.total != null) ? data.total : tab._lazyOffset;
      tab._lazyAllLoaded = (tab._lazyOffset >= tab._lazyTotal);
      tab._lazyLoadingMore = false;
      _hideLazyLoadingIndicator(tab);
      _updateAfterLoadMore(tab);
    } catch (e) {
      tab._lazyLoadingMore = false;
      _hideLazyLoadingIndicator(tab);
      if (typeof toast === 'function') toast('加载更多失败: ' + e.message, 'error');
    }
  }

  /**
   * Update the DOM after new entries have been appended via lazy loading.
   * Preserves scroll position. Switches to virtual scroll if the entry
   * count has crossed the virtual-scroll threshold.
   */
  function _updateAfterLoadMore(tab) {
    var listArea = _body ? _body.querySelector('.files-list-area') : null;
    if (!listArea) {
      _renderContent();
      return;
    }

    var wasVirtual = tab.entries.length - (tab._lazyLimit || 200) > _VS_THRESHOLD;
    var nowVirtual = tab.entries.length > _VS_THRESHOLD;

    if (wasVirtual !== nowVirtual) {
      // Rendering mode changed — full re-render preserving scroll position
      var savedScroll = listArea.scrollTop;
      _renderContent();
      var newListArea = _body ? _body.querySelector('.files-list-area') : null;
      if (newListArea) newListArea.scrollTop = savedScroll;
    } else if (nowVirtual && tab._scrollContainer) {
      // Incremental update for virtual scroll — no full re-render needed
      var entries = _sortEntries(tab);
      var totalHeight = entries.length * _VS_ROW_HEIGHT;
      var inner = tab._scrollContainer.querySelector('.files-virtual-scroll-inner');
      if (inner) inner.style.height = totalHeight + 'px';
      // Re-render visible rows to include new entries
      var scrollTop = tab._scrollContainer.scrollTop;
      var containerHeight = tab._scrollContainer.clientHeight || 500;
      var startIndex = Math.max(0, Math.floor(scrollTop / _VS_ROW_HEIGHT) - _VS_BUFFER);
      var visibleCount = Math.ceil(containerHeight / _VS_ROW_HEIGHT) + _VS_BUFFER * 2;
      var endIndex = Math.min(entries.length, startIndex + visibleCount);
      var tbody = tab._scrollContainer.querySelector('.files-table tbody');
      if (tbody) {
        tbody.innerHTML = '';
        for (var i = startIndex; i < endIndex; i++) {
          var tr = _buildRow(entries[i], i, tab);
          tr.className = (tr.className ? tr.className + ' ' : '') + 'files-virtual-row';
          tr.style.top = (i * _VS_ROW_HEIGHT) + 'px';
          tr.style.height = _VS_ROW_HEIGHT + 'px';
          tbody.appendChild(tr);
        }
      }
    } else {
      // Normal table mode — full re-render (fast for <200 entries)
      var savedScroll2 = listArea.scrollTop;
      _renderContent();
      var newListArea2 = _body ? _body.querySelector('.files-list-area') : null;
      if (newListArea2) newListArea2.scrollTop = savedScroll2;
    }
  }

  /**
   * Show a small loading indicator at the bottom of the file list area.
   */
  function _showLazyLoadingIndicator(tab) {
    if (!_body) return;
    var existing = _body.querySelector('.files-lazy-loading');
    if (existing) return;
    var listArea = _body.querySelector('.files-list-area');
    if (!listArea) return;
    var indicator = document.createElement('div');
    indicator.className = 'files-lazy-loading';
    indicator.textContent = '加载更多...';
    listArea.appendChild(indicator);
  }

  /**
   * Remove the lazy-loading indicator from the file list area.
   */
  function _hideLazyLoadingIndicator(tab) {
    if (!_body) return;
    var indicator = _body.querySelector('.files-lazy-loading');
    if (indicator) indicator.remove();
  }

  function _navigateTo(tab, path, pushHistory) {
    if (pushHistory !== false) {
      // Trim forward history and push
      tab.history = tab.history.slice(0, tab.historyIdx + 1);
      tab.history.push(path);
      tab.historyIdx = tab.history.length - 1;
    }
    _loadDirectory(tab, path);
    _saveSession();
  }

  function _goBack(tab) {
    if (tab.historyIdx > 0) {
      tab.historyIdx--;
      _loadDirectory(tab, tab.history[tab.historyIdx]);
    }
  }

  function _goForward(tab) {
    if (tab.historyIdx < tab.history.length - 1) {
      tab.historyIdx++;
      _loadDirectory(tab, tab.history[tab.historyIdx]);
    }
  }

  function _goUp(tab) {
    var parent = _parentPath(tab.path);
    if (parent === tab.path) return; // already at root, nowhere to go
    _navigateTo(tab, parent);
  }

  // ========================= Content Rendering =========================

  function _renderContent() {
    if (!_body) return;
    _body.innerHTML = '';

    var tab = _getActiveTab();
    if (!tab) {
      _body.innerHTML =
        '<div class="files-empty">' +
        '<div class="files-empty-icon">&#128193;</div>' +
        '<div class="files-empty-text">无打开的标签。点击 + 浏览文件。</div>' +
        '</div>';
      return;
    }

    // Toolbar
    var toolbar = _buildToolbar(tab);
    _body.appendChild(toolbar);

    // File list area
    var listArea = document.createElement('div');
    listArea.className = 'files-list-area';
    listArea.style.cssText = 'flex:1;overflow-y:auto;';

    if (tab.loading) {
      listArea.innerHTML = '<div class="files-loading">加载中...</div>';
      tab._scrollContainer = null;
    } else if (tab.entries.length === 0) {
      listArea.innerHTML = '<div class="files-empty"><div class="files-empty-text">空目录</div></div>';
      tab._scrollContainer = null;
    } else {
      if (tab.entries.length > _VS_THRESHOLD) {
        var vsWrapper = _buildVirtualScroll(tab);
        listArea.appendChild(vsWrapper);
      } else {
        tab._scrollContainer = null; // no virtual scroll — use full re-render on load-more
        var table = _buildTable(tab);
        listArea.appendChild(table);

        // Lazy-load scroll trigger for normal (non-virtual) table mode
        if (!tab._lazyAllLoaded && tab._lazyTotal > tab.entries.length) {
          listArea.addEventListener('scroll', function () {
            if (tab._lazyLoadingMore || tab._lazyAllLoaded) return;
            var scrollBottom = listArea.scrollTop + listArea.clientHeight;
            if (scrollBottom >= listArea.scrollHeight - 200) {
              _loadMore(tab);
            }
          });
        }
      }
    }

    _body.appendChild(listArea);

    // Drag-and-drop upload support on the list area
    _setupDragDrop(listArea, tab);

    _body.style.display = 'flex';
    _body.style.flexDirection = 'column';
  }

  function _buildToolbar(tab) {
    var toolbar = document.createElement('div');
    toolbar.className = 'files-toolbar';

    // Back button
    var backBtn = document.createElement('button');
    backBtn.className = 'files-nav-btn';
    backBtn.innerHTML = '&#9664;';
    backBtn.title = '后退';
    backBtn.disabled = tab.historyIdx <= 0;
    backBtn.addEventListener('click', function () { _goBack(tab); });
    toolbar.appendChild(backBtn);

    // Forward button
    var fwdBtn = document.createElement('button');
    fwdBtn.className = 'files-nav-btn';
    fwdBtn.innerHTML = '&#9654;';
    fwdBtn.title = '前进';
    fwdBtn.disabled = tab.historyIdx >= tab.history.length - 1;
    fwdBtn.addEventListener('click', function () { _goForward(tab); });
    toolbar.appendChild(fwdBtn);

    // Up button
    var upBtn = document.createElement('button');
    upBtn.className = 'files-nav-btn';
    upBtn.innerHTML = '&#9650;';
    upBtn.title = '上级目录';
    upBtn.disabled = _isRootView(tab.path);
    upBtn.addEventListener('click', function () { _goUp(tab); });
    toolbar.appendChild(upBtn);

    // Breadcrumb
    var breadcrumb = document.createElement('div');
    breadcrumb.className = 'files-breadcrumb';

    // Parse the current path into segments for the breadcrumb
    var normPath = (tab.path || '/').replace(/\\/g, '/');
    var isWinDrive = /^[a-zA-Z]:/.test(normPath);

    // Root segment — clicking navigates to the drives/root view
    var rootSeg = document.createElement('span');
    rootSeg.className = 'files-breadcrumb-seg' + (_isRootView(tab.path) ? ' current' : '');
    rootSeg.textContent = '/';
    rootSeg.addEventListener('click', function () { _navigateTo(tab, '/'); });
    breadcrumb.appendChild(rootSeg);

    if (isWinDrive) {
      // Windows path: show drive letter as first segment, then sub-dirs
      var driveLetter = normPath.substring(0, 2); // e.g. "C:"
      var rest = normPath.substring(2); // e.g. "/Users/Foo" or "" or "/"
      var segments = rest.split('/').filter(Boolean);

      // Drive segment
      var sep0 = document.createElement('span');
      sep0.className = 'files-breadcrumb-sep';
      sep0.textContent = '/';
      breadcrumb.appendChild(sep0);

      var driveSeg = document.createElement('span');
      driveSeg.className = 'files-breadcrumb-seg' + (segments.length === 0 ? ' current' : '');
      driveSeg.textContent = driveLetter;
      (function (dl) {
        driveSeg.addEventListener('click', function () {
          _navigateTo(tab, dl + '\\');
        });
      })(driveLetter);
      breadcrumb.appendChild(driveSeg);

      // Sub-directory segments
      for (var wi = 0; wi < segments.length; wi++) {
        var wsep = document.createElement('span');
        wsep.className = 'files-breadcrumb-sep';
        wsep.textContent = '/';
        breadcrumb.appendChild(wsep);

        var wseg = document.createElement('span');
        wseg.className = 'files-breadcrumb-seg' + (wi === segments.length - 1 ? ' current' : '');
        wseg.textContent = segments[wi];
        (function (dl, segs, idx) {
          wseg.addEventListener('click', function () {
            var p = dl + '\\' + segs.slice(0, idx + 1).join('\\');
            _navigateTo(tab, p);
          });
        })(driveLetter, segments, wi);
        breadcrumb.appendChild(wseg);
      }
    } else {
      // Unix-style path
      var segments = normPath.split('/').filter(Boolean);
      for (var i = 0; i < segments.length; i++) {
        var sep = document.createElement('span');
        sep.className = 'files-breadcrumb-sep';
        sep.textContent = '/';
        breadcrumb.appendChild(sep);

        var seg = document.createElement('span');
        seg.className = 'files-breadcrumb-seg' + (i === segments.length - 1 ? ' current' : '');
        seg.textContent = segments[i];
        (function (idx) {
          seg.addEventListener('click', function () {
            var p = '/' + segments.slice(0, idx + 1).join('/');
            _navigateTo(tab, p);
          });
        })(i);
        breadcrumb.appendChild(seg);
      }
    }

    breadcrumb.addEventListener('dblclick', function (e) {
      e.stopPropagation();
      _showPathInput(tab, toolbar, breadcrumb);
    });

    toolbar.appendChild(breadcrumb);

    // Project root shortcut button
    if (_projectRoot) {
      var projBtn = document.createElement('button');
      projBtn.className = 'files-nav-btn files-project-btn';
      projBtn.innerHTML = '&#128193;';
      projBtn.title = '项目根目录';
      projBtn.addEventListener('click', function () { _navigateTo(tab, _projectRoot); });
      toolbar.appendChild(projBtn);
    }

    // Search input
    var searchWrapper = document.createElement('div');
    searchWrapper.className = 'files-search-wrapper';

    _searchInput = document.createElement('input');
    _searchInput.type = 'text';
    _searchInput.className = 'files-search-input';
    _searchInput.placeholder = '\u641C\u7D22\u6587\u4EF6...';
    _searchInput.autocomplete = 'off';
    _searchInput.spellcheck = false;

    _searchInput.addEventListener('input', function () {
      var val = _searchInput.value.trim();
      if (val.length > 0) {
        searchWrapper.classList.add('has-query');
      } else {
        searchWrapper.classList.remove('has-query');
      }
      _debounceSearch(val, tab);
    });

    _searchInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        // Navigate to first result or active result
        var items = _searchResults ? _searchResults.querySelectorAll('.files-search-result') : [];
        var idx = _searchActiveIdx >= 0 ? _searchActiveIdx : 0;
        if (items.length > idx) {
          items[idx].click();
        }
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        _navigateSearchResults(1);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        _navigateSearchResults(-1);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        _clearSearch();
        _searchInput.blur();
      }
    });

    _searchInput.addEventListener('focus', function () {
      var val = _searchInput.value.trim();
      if (val.length > 0 && _searchResults && _searchResults.children.length > 0) {
        _searchResults.classList.add('visible');
      }
    });

    var clearBtn = document.createElement('button');
    clearBtn.className = 'files-search-clear';
    clearBtn.type = 'button';
    clearBtn.innerHTML = '&times;';
    clearBtn.title = '清除搜索';
    clearBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      _clearSearch();
      _searchInput.focus();
    });

    _searchResults = document.createElement('div');
    _searchResults.className = 'files-search-results';

    searchWrapper.appendChild(_searchInput);
    searchWrapper.appendChild(clearBtn);
    searchWrapper.appendChild(_searchResults);
    toolbar.appendChild(searchWrapper);

    // Close search results when clicking outside
    document.addEventListener('click', function (e) {
      if (!searchWrapper.contains(e.target)) {
        _hideSearchResults();
      }
    });

    // Clipboard indicator
    if (_clipboard.paths.length > 0) {
      var clipIndicator = document.createElement('span');
      clipIndicator.className = 'files-clipboard-indicator';
      var clipLabel = _clipboard.action === 'cut' ? '\u5DF2\u526A\u5207' : '\u5DF2\u590D\u5236';
      clipIndicator.textContent = clipLabel + ' ' + _clipboard.paths.length + ' \u9879';
      clipIndicator.title = _clipboard.action === 'cut' ? '已剪切到剪贴板' : '已复制到剪贴板';
      var clipClearBtn = document.createElement('span');
      clipClearBtn.className = 'files-clipboard-clear';
      clipClearBtn.textContent = '\u00D7';
      clipClearBtn.title = '清除剪贴板';
      clipClearBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        _clipboard = { action: null, paths: [] };
        _renderContent();
      });
      clipIndicator.appendChild(clipClearBtn);
      toolbar.appendChild(clipIndicator);
    }

    // Actions
    var actions = document.createElement('div');
    actions.className = 'files-toolbar-actions';

    var uploadBtn = document.createElement('button');
    uploadBtn.className = 'files-toolbar-btn files-upload-btn';
    uploadBtn.textContent = '上传';
    uploadBtn.title = '上传文件到当前目录';
    uploadBtn.addEventListener('click', function () { _triggerFilePicker(); });
    actions.appendChild(uploadBtn);

    var newFolderBtn = document.createElement('button');
    newFolderBtn.className = 'files-toolbar-btn';
    newFolderBtn.textContent = '+ 文件夹';
    newFolderBtn.addEventListener('click', function () { _promptNewFolder(tab); });
    actions.appendChild(newFolderBtn);

    var refreshBtn = document.createElement('button');
    refreshBtn.className = 'files-toolbar-btn';
    refreshBtn.textContent = '刷新';
    refreshBtn.addEventListener('click', function () { _loadDirectory(tab, tab.path); });
    actions.appendChild(refreshBtn);

    toolbar.appendChild(actions);
    return toolbar;
  }

  function _showPathInput(tab, toolbar, breadcrumb) {
    breadcrumb.style.display = 'none';
    var input = document.createElement('input');
    input.type = 'text';
    input.className = 'files-path-input';
    input.style.display = 'block';
    input.value = tab.path;

    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        var val = input.value.trim();
        if (val) _navigateTo(tab, val);
        input.remove();
        breadcrumb.style.display = '';
      } else if (e.key === 'Escape') {
        input.remove();
        breadcrumb.style.display = '';
      }
    });

    input.addEventListener('blur', function () {
      input.remove();
      breadcrumb.style.display = '';
    });

    // Insert after nav buttons
    var navBtns = toolbar.querySelectorAll('.files-nav-btn');
    var lastNav = navBtns[navBtns.length - 1];
    if (lastNav && lastNav.nextSibling) {
      toolbar.insertBefore(input, lastNav.nextSibling);
    } else {
      toolbar.appendChild(input);
    }
    input.focus();
    input.select();
  }

  // ========================= File Table =========================

  function _buildTable(tab) {
    var entries = _sortEntries(tab);

    var wrapper = document.createElement('table');
    wrapper.className = 'files-table';

    // Header
    var thead = document.createElement('thead');
    var headerRow = document.createElement('tr');

    var cols = [
      { key: 'name', label: '名称', cls: '' },
      { key: 'size', label: '大小', cls: 'file-size' },
      { key: 'modified', label: '修改时间', cls: 'file-modified' },
    ];

    for (var c = 0; c < cols.length; c++) {
      var th = document.createElement('th');
      th.className = cols[c].cls;
      th.textContent = cols[c].label;

      if (tab.sortCol === cols[c].key) {
        var arrow = document.createElement('span');
        arrow.className = 'sort-arrow';
        arrow.textContent = tab.sortAsc ? '\u25B2' : '\u25BC';
        th.appendChild(arrow);
      }

      (function (colKey) {
        th.addEventListener('click', function () {
          if (tab.sortCol === colKey) {
            tab.sortAsc = !tab.sortAsc;
          } else {
            tab.sortCol = colKey;
            tab.sortAsc = true;
          }
          _renderContent();
        });
      })(cols[c].key);

      headerRow.appendChild(th);
    }
    thead.appendChild(headerRow);
    wrapper.appendChild(thead);

    // Body
    var tbody = document.createElement('tbody');

    for (var i = 0; i < entries.length; i++) {
      var entry = entries[i];
      var tr = document.createElement('tr');
      tr.dataset.path = entry.path;
      tr.dataset.type = entry.type;

      // Mark cut items with reduced opacity
      if (_clipboard.action === 'cut' && _clipboard.paths.indexOf(entry.path) !== -1) {
        tr.className = 'files-row-cut';
      }

      // Name cell
      var tdName = document.createElement('td');
      var nameCell = document.createElement('div');
      nameCell.className = 'file-name-cell';

      var icon = document.createElement('span');
      icon.className = 'file-icon';
      icon.textContent = entry.type === 'dir' ? '\uD83D\uDCC1' : _fileIcon(entry.name);
      nameCell.appendChild(icon);

      var nameSpan = document.createElement('span');
      nameSpan.className = 'file-name' + (entry.type === 'dir' ? ' dir-name' : '');
      nameSpan.textContent = entry.name;
      nameCell.appendChild(nameSpan);

      tdName.appendChild(nameCell);
      tr.appendChild(tdName);

      // Size cell
      var tdSize = document.createElement('td');
      tdSize.className = 'file-size';
      tdSize.textContent = entry.type === 'file' ? _formatSize(entry.size) : '-';
      tr.appendChild(tdSize);

      // Modified cell
      var tdMod = document.createElement('td');
      tdMod.className = 'file-modified';
      tdMod.textContent = _formatDate(entry.modified);
      tr.appendChild(tdMod);

      // Click handler
      (function (e, idx) {
        tr.addEventListener('click', function () {
          _selectedIndex = idx;
          _lastSelectedPath = e.path;
          if (e.type === 'dir') {
            _navigateTo(tab, e.path);
          } else {
            _previewFile(e);
          }
        });
        tr.addEventListener('contextmenu', function (ev) {
          ev.preventDefault();
          _showEntryContextMenu(ev, tab, e);
        });
      })(entry, i);

      tbody.appendChild(tr);
    }

    wrapper.appendChild(tbody);
    return wrapper;
  }

  function _sortEntries(tab) {
    var entries = tab.entries.slice();
    var col = tab.sortCol;
    var asc = tab.sortAsc;

    entries.sort(function (a, b) {
      // Dirs always first
      if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;

      var va, vb;
      if (col === 'size') {
        va = a.size || 0; vb = b.size || 0;
      } else if (col === 'modified') {
        va = a.modified || 0; vb = b.modified || 0;
      } else {
        va = a.name.toLowerCase(); vb = b.name.toLowerCase();
      }

      if (va < vb) return asc ? -1 : 1;
      if (va > vb) return asc ? 1 : -1;
      return 0;
    });

    return entries;
  }

  // ========================= Virtual Scrolling =========================

  var _VS_ROW_HEIGHT = 36;
  var _VS_THRESHOLD = 200;
  var _VS_BUFFER = 10;

  function _buildRow(entry, idx, tab) {
    var tr = document.createElement('tr');
    tr.dataset.path = entry.path;
    tr.dataset.type = entry.type;

    if (_clipboard.action === 'cut' && _clipboard.paths.indexOf(entry.path) !== -1) {
      tr.className = 'files-row-cut';
    }
    if (idx === _selectedIndex) {
      tr.className = (tr.className ? tr.className + ' ' : '') + 'files-row-selected';
    }

    var tdName = document.createElement('td');
    var nameCell = document.createElement('div');
    nameCell.className = 'file-name-cell';

    var icon = document.createElement('span');
    icon.className = 'file-icon';
    icon.textContent = entry.type === 'dir' ? '\uD83D\uDCC1' : _fileIcon(entry.name);
    nameCell.appendChild(icon);

    var nameSpan = document.createElement('span');
    nameSpan.className = 'file-name' + (entry.type === 'dir' ? ' dir-name' : '');
    nameSpan.textContent = entry.name;
    nameCell.appendChild(nameSpan);

    tdName.appendChild(nameCell);
    tr.appendChild(tdName);

    var tdSize = document.createElement('td');
    tdSize.className = 'file-size';
    tdSize.textContent = entry.type === 'file' ? _formatSize(entry.size) : '-';
    tr.appendChild(tdSize);

    var tdMod = document.createElement('td');
    tdMod.className = 'file-modified';
    tdMod.textContent = _formatDate(entry.modified);
    tr.appendChild(tdMod);

    (function (e, i) {
      tr.addEventListener('click', function () {
        _selectedIndex = i;
        _lastSelectedPath = e.path;
        if (e.type === 'dir') {
          _navigateTo(tab, e.path);
        } else {
          _previewFile(e);
        }
      });
      tr.addEventListener('contextmenu', function (ev) {
        ev.preventDefault();
        _showEntryContextMenu(ev, tab, e);
      });
    })(entry, idx);

    return tr;
  }

  function _buildVirtualScroll(tab) {
    var entries = _sortEntries(tab);
    var totalHeight = entries.length * _VS_ROW_HEIGHT;

    var wrapper = document.createElement('div');
    wrapper.className = 'files-virtual-wrap';

    // Static header table
    var headerTable = document.createElement('table');
    headerTable.className = 'files-table';

    var thead = document.createElement('thead');
    var headerRow = document.createElement('tr');
    var cols = [
      { key: 'name', label: '名称', cls: '' },
      { key: 'size', label: '大小', cls: 'file-size' },
      { key: 'modified', label: '修改时间', cls: 'file-modified' },
    ];

    for (var c = 0; c < cols.length; c++) {
      var th = document.createElement('th');
      th.className = cols[c].cls;
      th.textContent = cols[c].label;

      if (tab.sortCol === cols[c].key) {
        var arrow = document.createElement('span');
        arrow.className = 'sort-arrow';
        arrow.textContent = tab.sortAsc ? '\u25B2' : '\u25BC';
        th.appendChild(arrow);
      }

      (function (colKey) {
        th.addEventListener('click', function () {
          if (tab.sortCol === colKey) {
            tab.sortAsc = !tab.sortAsc;
          } else {
            tab.sortCol = colKey;
            tab.sortAsc = true;
          }
          _selectedIndex = -1;
          _renderContent();
        });
      })(cols[c].key);

      headerRow.appendChild(th);
    }
    thead.appendChild(headerRow);
    headerTable.appendChild(thead);
    wrapper.appendChild(headerTable);

    // Scrollable container for virtual rows
    var scrollContainer = document.createElement('div');
    scrollContainer.className = 'files-virtual-scroll';
    tab._scrollContainer = scrollContainer; // saved for incremental lazy-load updates

    var inner = document.createElement('div');
    inner.className = 'files-virtual-scroll-inner';
    inner.style.height = totalHeight + 'px';

    var bodyTable = document.createElement('table');
    bodyTable.className = 'files-table';
    var tbody = document.createElement('tbody');
    bodyTable.appendChild(tbody);
    inner.appendChild(bodyTable);
    scrollContainer.appendChild(inner);
    wrapper.appendChild(scrollContainer);

    var _rafPending = false;

    function renderVisibleRows() {
      var scrollTop = scrollContainer.scrollTop;
      var containerHeight = scrollContainer.clientHeight || 500;
      var startIndex = Math.max(0, Math.floor(scrollTop / _VS_ROW_HEIGHT) - _VS_BUFFER);
      var visibleCount = Math.ceil(containerHeight / _VS_ROW_HEIGHT) + _VS_BUFFER * 2;
      var endIndex = Math.min(entries.length, startIndex + visibleCount);

      tbody.innerHTML = '';

      for (var i = startIndex; i < endIndex; i++) {
        var tr = _buildRow(entries[i], i, tab);
        tr.className = (tr.className ? tr.className + ' ' : '') + 'files-virtual-row';
        tr.style.top = (i * _VS_ROW_HEIGHT) + 'px';
        tr.style.height = _VS_ROW_HEIGHT + 'px';
        tbody.appendChild(tr);
      }
    }

    scrollContainer.addEventListener('scroll', function () {
      if (!_rafPending) {
        _rafPending = true;
        requestAnimationFrame(function () {
          _rafPending = false;
          renderVisibleRows();
        });
      }

      // Lazy-load trigger: when scrolling near the bottom of the scrollable area
      if (!tab._lazyAllLoaded && !tab._lazyLoadingMore) {
        var scrollBottom = scrollContainer.scrollTop + scrollContainer.clientHeight;
        var totalScrollHeight = scrollContainer.scrollHeight;
        if (scrollBottom >= totalScrollHeight - 500) {
          _loadMore(tab);
        }
      }
    });

    // Initial render after the container is in the DOM and has dimensions
    requestAnimationFrame(function () {
      renderVisibleRows();
    });

    return wrapper;
  }

  // ========================= Cross-Module Integration =========================

  function _openInTerminal(dirPath) {
    if (typeof switchTab !== 'function') return;
    switchTab('terminal');
    setTimeout(function () {
      if (typeof TerminalManager === 'undefined') return;
      var tab = TerminalManager.createTab('local');
      // Wait for WebSocket connection, then send cd command
      var attempts = 0;
      var maxAttempts = 30;
      var pollInterval = setInterval(function () {
        attempts++;
        if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
          clearInterval(pollInterval);
          tab.ws.send(JSON.stringify({ type: 'input', data: 'cd "' + dirPath + '"\r\n' }));
        } else if (attempts >= maxAttempts) {
          clearInterval(pollInterval);
        }
      }, 100);
    }, 500);
  }

  function _copyPathToClipboard(path) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(path).then(function () {
        if (typeof toast === 'function') toast('路径已复制: ' + path, 'ok');
      }).catch(function () {
        _fallbackCopyText(path);
      });
    } else {
      _fallbackCopyText(path);
    }
  }

  function _fallbackCopyText(text) {
    var ta = document.createElement('textarea');
    ta.value = text;
    ta.style.cssText = 'position:fixed;left:-9999px;top:-9999px;';
    document.body.appendChild(ta);
    ta.select();
    try {
      document.execCommand('copy');
      if (typeof toast === 'function') toast('路径已复制: ' + text, 'ok');
    } catch (e) {
      if (typeof toast === 'function') toast('复制失败', 'error');
    }
    document.body.removeChild(ta);
  }

  // ========================= Context Menus =========================

  function _hideContextMenu() {
    if (_contextMenu) { _contextMenu.remove(); _contextMenu = null; }
  }

  function _showEntryContextMenu(event, tab, entry) {
    _hideContextMenu();
    _lastSelectedPath = entry.path;
    _contextMenu = document.createElement('div');
    _contextMenu.className = 'files-context-menu';
    _contextMenu.style.left = event.clientX + 'px';
    _contextMenu.style.top = event.clientY + 'px';

    var items = [];

    if (entry.type === 'dir') {
      items.push({ label: '打开', action: function () { _navigateTo(tab, entry.path); } });
      items.push({ label: '\u5728\u7EC8\u7AEF\u4E2D\u6253\u5F00', action: function () { _openInTerminal(entry.path); } });
    } else {
      items.push({ label: '预览', action: function () { _previewFile(entry); } });
      items.push({ label: '编辑', action: function () { _previewFile(entry, true); } });
      items.push({ label: '下载', action: function () { _downloadFile(entry.path); } });
    }

    items.push({ separator: true });
    items.push({ label: '\u590D\u5236\u8DEF\u5F84', action: function () { _copyPathToClipboard(entry.path); } });
    items.push({ label: '\u590D\u5236', action: function () { _clipboardCopy([entry.path]); _renderContent(); } });
    items.push({ label: '\u526A\u5207', action: function () { _clipboardCut([entry.path]); _renderContent(); } });
    if (_clipboard.paths.length > 0) {
      items.push({ label: '\u7C98\u8D34', action: function () { _clipboardPaste(tab); } });
    }
    items.push({ separator: true });
    items.push({ label: '重命名', action: function () { _showRenameDialog(tab, entry); } });
    items.push({ label: '删除', danger: true, action: function () { _deleteEntries(tab, [entry.path]); } });
    items.push({ separator: true });
    items.push({ label: '新建文件夹', action: function () { _promptNewFolder(tab); } });

    _populateMenu(_contextMenu, items);
    document.body.appendChild(_contextMenu);
    _adjustMenuPosition(_contextMenu);
  }

  function _showTabContextMenu(event, tabId) {
    _hideContextMenu();
    _contextMenu = document.createElement('div');
    _contextMenu.className = 'files-context-menu';
    _contextMenu.style.left = event.clientX + 'px';
    _contextMenu.style.top = event.clientY + 'px';

    var items = [
      { label: '关闭', action: function () { closeTab(tabId); } },
      { label: '关闭其他', action: function () { _closeOtherTabs(tabId); } },
      { label: '全部关闭', danger: true, action: function () { _closeAllTabs(); } },
    ];

    _populateMenu(_contextMenu, items);
    document.body.appendChild(_contextMenu);
    _adjustMenuPosition(_contextMenu);
  }

  function _showBgContextMenu(event, tab) {
    _hideContextMenu();
    _contextMenu = document.createElement('div');
    _contextMenu.className = 'files-context-menu';
    _contextMenu.style.left = event.clientX + 'px';
    _contextMenu.style.top = event.clientY + 'px';

    var items = [
      { label: '上传文件', action: function () { _triggerFilePicker(); } },
      { separator: true },
      { label: '新建文件夹', action: function () { _promptNewFolder(tab); } },
      { label: '刷新', action: function () { _loadDirectory(tab, tab.path); } },
      { separator: true },
      { label: '\u5728\u7EC8\u7AEF\u4E2D\u6253\u5F00', action: function () { _openInTerminal(tab.path); } },
    ];

    if (_clipboard.paths.length > 0) {
      items.push({ separator: true });
      items.push({ label: '\u7C98\u8D34', action: function () { _clipboardPaste(tab); } });
    }

    _populateMenu(_contextMenu, items);
    document.body.appendChild(_contextMenu);
    _adjustMenuPosition(_contextMenu);
  }

  function _populateMenu(menu, items) {
    for (var i = 0; i < items.length; i++) {
      if (items[i].separator) {
        var sep = document.createElement('div');
        sep.className = 'files-context-menu-separator';
        menu.appendChild(sep);
      } else {
        var item = document.createElement('div');
        item.className = 'files-context-menu-item';
        if (items[i].danger) item.className += ' danger';
        if (items[i].disabled) item.className += ' disabled';
        item.textContent = items[i].label;
        (function (action) {
          item.addEventListener('click', function (e) {
            e.stopPropagation();
            _hideContextMenu();
            action();
          });
        })(items[i].action);
        menu.appendChild(item);
      }
    }
  }

  function _adjustMenuPosition(menu) {
    var rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      menu.style.left = (window.innerWidth - rect.width - 8) + 'px';
    }
    if (rect.bottom > window.innerHeight) {
      menu.style.top = (window.innerHeight - rect.height - 8) + 'px';
    }
  }

  // ========================= File Operations =========================

  function _clipboardCopy(paths) {
    _clipboard = { action: 'copy', paths: paths.slice() };
    if (typeof toast === 'function') toast('\u5DF2\u590D\u5236 ' + paths.length + ' \u9879', 'ok');
  }

  function _clipboardCut(paths) {
    _clipboard = { action: 'cut', paths: paths.slice() };
    if (typeof toast === 'function') toast('\u5DF2\u526A\u5207 ' + paths.length + ' \u9879', 'ok');
  }

  async function _clipboardPaste(tab) {
    if (!_clipboard.action || _clipboard.paths.length === 0) return;

    var destDir = tab.path || '/';
    var endpoint = _clipboard.action === 'cut' ? '/v1/webui/files/move' : '/v1/webui/files/copy';
    var actionLabel = _clipboard.action === 'cut' ? '\u79FB\u52A8' : '\u590D\u5236';

    // Process each path sequentially
    var successCount = 0;
    for (var i = 0; i < _clipboard.paths.length; i++) {
      var srcPath = _clipboard.paths[i];
      try {
        await Api.post(endpoint, { source: srcPath, dest: destDir });
        successCount++;
      } catch (e) {
        if (typeof toast === 'function') toast(actionLabel + ' \u5931\u8D25: ' + e.message, 'error');
      }
    }

    if (successCount > 0) {
      if (typeof toast === 'function') toast(actionLabel + ' ' + successCount + ' \u9879', 'ok');
    }

    // Clear clipboard after cut, keep for copy
    if (_clipboard.action === 'cut') {
      _clipboard = { action: null, paths: [] };
    }

    _loadDirectory(tab, tab.path);
  }

  function _downloadFile(path) {
    var a = document.createElement('a');
    a.href = '/v1/webui/files/download?path=' + encodeURIComponent(path);
    a.download = '';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  async function _deleteEntries(tab, paths) {
    var msg = paths.length === 1 ?
      '删除 "' + paths[0].split(/[\/\\]/).pop() + '"?' :
      '删除 ' + paths.length + ' 项?';
    var confirmed = await showConfirmDialog(msg, { title: '确认删除', confirmText: '删除' });
    if (!confirmed) return;

    try {
      var resp = await Api.post('/v1/webui/files/delete', { paths: paths });
      var ok = (resp.results || []).every(function (r) { return r.ok; });
      if (ok) {
        if (typeof toast === 'function') toast('删除成功', 'ok');
        _loadDirectory(tab, tab.path);
      } else {
        var errs = (resp.results || []).filter(function (r) { return !r.ok; });
        if (typeof toast === 'function') toast('删除失败: ' + errs[0].error, 'error');
      }
    } catch (e) {
      if (typeof toast === 'function') toast('删除失败: ' + e.message, 'error');
    }
  }

  function _showRenameDialog(tab, entry) {
    var overlay = document.createElement('div');
    overlay.className = 'files-rename-overlay';

    overlay.innerHTML =
      '<div class="files-rename-dialog">' +
      '<h3>重命名</h3>' +
      '<input type="text" id="filesRenameInput" value="' + _escapeAttr(entry.name) + '">' +
      '<div class="files-rename-actions">' +
      '<button class="files-rename-cancel" type="button">取消</button>' +
      '<button class="files-rename-confirm" type="button">重命名</button>' +
      '</div></div>';

    document.body.appendChild(overlay);

    var input = overlay.querySelector('#filesRenameInput');
    // Select name without extension for files
    if (entry.type === 'file') {
      var dotIdx = entry.name.lastIndexOf('.');
      if (dotIdx > 0) input.setSelectionRange(0, dotIdx);
      else input.select();
    } else {
      input.select();
    }
    input.focus();

    overlay.querySelector('.files-rename-cancel').addEventListener('click', function () {
      overlay.remove();
    });

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) overlay.remove();
    });

    function doRename() {
      var newName = input.value.trim();
      if (!newName || newName === entry.name) { overlay.remove(); return; }

      var parentPath = entry.path.replace(/[\/\\][^\/\\]+[\/\\]?$/, '') || '/';
      var newPath = _pathJoin(parentPath, newName);

      Api.post('/v1/webui/files/rename', {
        old_path: entry.path,
        new_path: newPath,
      }).then(function () {
        if (typeof toast === 'function') toast('已重命名', 'ok');
        _loadDirectory(tab, tab.path);
      }).catch(function (e) {
        if (typeof toast === 'function') toast('重命名失败: ' + e.message, 'error');
      });

      overlay.remove();
    }

    overlay.querySelector('.files-rename-confirm').addEventListener('click', doRename);
    input.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') { e.preventDefault(); doRename(); }
      if (e.key === 'Escape') overlay.remove();
    });
  }

  function _promptNewFolder(tab) {
    var name = prompt('新文件夹名称:');
    if (!name || !name.trim()) return;

    var newPath = _pathJoin(tab.path, name.trim());

    Api.post('/v1/webui/files/mkdir', { path: newPath }).then(function () {
      if (typeof toast === 'function') toast('文件夹已创建', 'ok');
      _loadDirectory(tab, tab.path);
    }).catch(function (e) {
      if (typeof toast === 'function') toast('失败: ' + e.message, 'error');
    });
  }

  // ========================= Upload =========================

  function _triggerFilePicker() {
    var input = document.getElementById('filesUploadInput');
    if (input) input.click();
  }

  async function _uploadFiles(tab, dirPath, fileList) {
    if (!fileList || fileList.length === 0) return;

    var formData = new FormData();
    formData.append('dir', dirPath);
    for (var i = 0; i < fileList.length; i++) {
      formData.append('files', fileList[i]);
    }

    // Show a brief upload indicator via toast
    var count = fileList.length;
    if (typeof toast === 'function') toast('正在上传 ' + count + ' 个文件...', 'ok');

    try {
      var resp = await fetch('/v1/webui/files/upload', {
        method: 'POST',
        body: formData,
      });

      var data;
      try {
        data = await resp.json();
      } catch (_e) {
        data = null;
      }

      if (!resp.ok) {
        var errMsg = (data && data.error) ? data.error : ('HTTP ' + resp.status);
        if (typeof toast === 'function') toast('上传失败: ' + errMsg, 'error');
        return;
      }

      var uploaded = (data && data.uploaded) || [];
      if (typeof toast === 'function') toast('已上传 ' + uploaded.length + ' 个文件', 'ok');
      _loadDirectory(tab, tab.path);
    } catch (e) {
      if (typeof toast === 'function') toast('上传失败: ' + e.message, 'error');
    }
  }

  function _setupDragDrop(listArea, tab) {
    var overlay = null;
    var dragCounter = 0;

    function showOverlay() {
      if (overlay) return;
      overlay = document.createElement('div');
      overlay.className = 'files-drop-overlay';
      overlay.textContent = '拖放文件以上传';
      listArea.style.position = 'relative';
      listArea.appendChild(overlay);
    }

    function hideOverlay() {
      if (overlay) {
        overlay.remove();
        overlay = null;
      }
      dragCounter = 0;
    }

    listArea.addEventListener('dragenter', function (e) {
      e.preventDefault();
      e.stopPropagation();
      dragCounter++;
      if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.indexOf('Files') !== -1) {
        showOverlay();
      }
    });

    listArea.addEventListener('dragover', function (e) {
      e.preventDefault();
      e.stopPropagation();
      if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
    });

    listArea.addEventListener('dragleave', function (e) {
      e.preventDefault();
      e.stopPropagation();
      dragCounter--;
      if (dragCounter <= 0) {
        hideOverlay();
      }
    });

    listArea.addEventListener('drop', function (e) {
      e.preventDefault();
      e.stopPropagation();
      hideOverlay();
      if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
        _uploadFiles(tab, tab.path, e.dataTransfer.files);
      }
    });
  }

  // ========================= File Preview =========================

  async function _previewFile(entry, editMode) {
    var overlay = document.createElement('div');
    overlay.className = 'files-preview-overlay';

    overlay.innerHTML =
      '<div class="files-preview-dialog">' +
      '<div class="files-preview-header">' +
      '<div class="files-preview-title">' + _escapeHtml(entry.name) + '</div>' +
      '<div class="files-preview-actions">' +
      '<button class="files-preview-btn" id="filesPreviewEdit">编辑</button>' +
      '<button class="files-preview-btn" id="filesPreviewDownload">下载</button>' +
      '<button class="files-preview-btn" id="filesPreviewClose">关闭</button>' +
      '</div></div>' +
      '<div class="files-preview-body"><div class="files-loading">加载中...</div></div>' +
      '</div>';

    document.body.appendChild(overlay);

    var dialog = overlay.querySelector('.files-preview-dialog');
    var titleEl = overlay.querySelector('.files-preview-title');
    var actionsEl = overlay.querySelector('.files-preview-actions');
    var bodyEl = overlay.querySelector('.files-preview-body');

    // State for edit mode
    var editState = {
      active: false,
      dirty: false,
      originalContent: '',
    };

    // Close overlay
    function closeOverlay() {
      overlay.remove();
      document.removeEventListener('keydown', onKey);
    }

    overlay.querySelector('#filesPreviewClose').addEventListener('click', closeOverlay);
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) closeOverlay();
    });
    overlay.querySelector('#filesPreviewDownload').addEventListener('click', function () {
      _downloadFile(entry.path);
    });

    // Edit button: enter edit mode (only shown for text files after load)
    overlay.querySelector('#filesPreviewEdit').addEventListener('click', function () {
      if (editState.active) return;
      _enterEditMode();
    });

    // Unified Escape key handler
    function onKey(e) {
      if (editState.active) {
        if (e.key === 'Escape') {
          e.preventDefault();
          e.stopPropagation();
          _cancelEdit();
        }
        return;
      }
      if (e.key === 'Escape') {
        closeOverlay();
      }
    }
    document.addEventListener('keydown', onKey);

    // Switch to preview mode: restore header buttons, show body, remove editor
    function _exitEditMode() {
      editState.active = false;
      editState.dirty = false;
      dialog.classList.remove('files-edit-mode');
      titleEl.textContent = entry.name;

      actionsEl.innerHTML =
        '<button class="files-preview-btn" id="filesPreviewEdit">编辑</button>' +
        '<button class="files-preview-btn" id="filesPreviewDownload">下载</button>' +
        '<button class="files-preview-btn" id="filesPreviewClose">关闭</button>';

      actionsEl.querySelector('#filesPreviewEdit').addEventListener('click', function () {
        if (editState.active) return;
        _enterEditMode();
      });
      actionsEl.querySelector('#filesPreviewDownload').addEventListener('click', function () {
        _downloadFile(entry.path);
      });
      actionsEl.querySelector('#filesPreviewClose').addEventListener('click', closeOverlay);

      var editor = dialog.querySelector('.files-editor');
      if (editor) editor.remove();
      bodyEl.style.display = '';
    }

    // Switch to edit mode: change header buttons, hide body, show editor
    function _enterEditMode() {
      editState.active = true;
      editState.dirty = false;
      dialog.classList.add('files-edit-mode');
      titleEl.textContent = entry.name + ' - 编辑中';

      actionsEl.innerHTML =
        '<button class="files-preview-btn files-preview-btn-save" id="filesEditorSave">保存</button>' +
        '<button class="files-preview-btn" id="filesEditorCancel">取消</button>';

      actionsEl.querySelector('#filesEditorSave').addEventListener('click', _saveEditedFile);
      actionsEl.querySelector('#filesEditorCancel').addEventListener('click', _cancelEdit);

      bodyEl.style.display = 'none';
      _showEditor();
    }

    // Create editor DOM (line numbers gutter + textarea) and append to dialog
    function _showEditor() {
      var existing = dialog.querySelector('.files-editor');
      if (existing) existing.remove();

      var editorDiv = document.createElement('div');
      editorDiv.className = 'files-editor';

      var linesDiv = document.createElement('div');
      linesDiv.className = 'files-editor-lines';

      var textarea = document.createElement('textarea');
      textarea.className = 'files-editor-textarea';
      textarea.spellcheck = false;
      textarea.value = editState.originalContent;

      editorDiv.appendChild(linesDiv);
      editorDiv.appendChild(textarea);
      dialog.appendChild(editorDiv);

      function updateLineNumbers() {
        var count = (textarea.value.match(/\n/g) || []).length + 1;
        var nums = [];
        for (var i = 1; i <= count; i++) nums.push(i);
        linesDiv.textContent = nums.join('\n');
      }

      // Sync scroll between textarea and line numbers
      textarea.addEventListener('scroll', function () {
        linesDiv.scrollTop = textarea.scrollTop;
      });

      // Keyboard shortcuts inside textarea
      textarea.addEventListener('keydown', function (e) {
        // Tab inserts spaces
        if (e.key === 'Tab') {
          e.preventDefault();
          var start = textarea.selectionStart;
          var end = textarea.selectionEnd;
          textarea.value =
            textarea.value.substring(0, start) + '    ' + textarea.value.substring(end);
          textarea.selectionStart = textarea.selectionEnd = start + 4;
          _markDirty();
          updateLineNumbers();
        }
        // Ctrl+S saves
        if (e.key === 's' && (e.ctrlKey || e.metaKey)) {
          e.preventDefault();
          _saveEditedFile();
        }
      });

      textarea.addEventListener('input', function () {
        _markDirty();
        updateLineNumbers();
      });

      updateLineNumbers();
      textarea.focus();
    }

    function _markDirty() {
      if (!editState.dirty) {
        editState.dirty = true;
        titleEl.textContent = entry.name + ' - 编辑中 *';
      }
    }

    // Save edited content via API
    async function _saveEditedFile() {
      var textarea = dialog.querySelector('.files-editor-textarea');
      if (!textarea) return;

      var saveBtn = actionsEl.querySelector('#filesEditorSave');
      if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = '保存中...';
      }

      try {
        await Api.post('/v1/webui/files/write', {
          path: entry.path,
          content: textarea.value,
        });
        editState.originalContent = textarea.value;
        if (typeof toast === 'function') toast('文件已保存', 'ok');
        // Refresh the read-only preview with updated content
        _renderTextPreview(editState.originalContent);
        _exitEditMode();
      } catch (e) {
        if (typeof toast === 'function') toast('保存失败: ' + e.message, 'error');
        if (saveBtn) {
          saveBtn.disabled = false;
          saveBtn.textContent = '保存';
        }
      }
    }

    // Cancel editing with dirty-state confirmation
    async function _cancelEdit() {
      if (editState.dirty) {
        var confirmed = await showConfirmDialog('放弃未保存的更改?', { title: '放弃更改', confirmText: '放弃' });
        if (!confirmed) return;
      }
      _exitEditMode();
      // Restore preview body from original content
      bodyEl.innerHTML = '';
      _renderTextPreview(editState.originalContent);
      bodyEl.style.display = '';
    }

    // Render text content with line numbers into the preview body
    function _renderTextPreview(content) {
      var pre = document.createElement('pre');
      pre.className = 'files-preview-code';

      var codeEl = document.createElement('code');
      codeEl.className = 'language-' + _detectLanguage(entry.name);

      var lines = (content || '').split('\n');
      if (lines.length > 0 && lines[lines.length - 1] === '') lines.pop();

      for (var i = 0; i < lines.length; i++) {
        var lineEl = document.createElement('span');
        lineEl.className = 'line';
        lineEl.textContent = lines[i] || ' ';
        codeEl.appendChild(lineEl);
      }

      pre.appendChild(codeEl);
      bodyEl.innerHTML = '';
      bodyEl.appendChild(pre);

      // Apply syntax highlighting if highlight.js is available
      if (typeof hljs !== 'undefined') {
        hljs.highlightElement(codeEl);
      }
    }

    // Load file content from API
    try {
      var data = await Api.fetchJson('/v1/webui/files/read?path=' + encodeURIComponent(entry.path));

      if (data.encoding === 'base64' && data.content) {
        // Image preview -- hide edit button
        overlay.querySelector('#filesPreviewEdit').style.display = 'none';
        bodyEl.innerHTML =
          '<div class="files-preview-image">' +
          '<img src="' + data.content + '" alt="' + _escapeAttr(entry.name) + '">' +
          '</div>';
      } else if (data.encoding === 'binary') {
        // Binary preview -- hide edit button
        overlay.querySelector('#filesPreviewEdit').style.display = 'none';
        bodyEl.innerHTML =
          '<div class="files-preview-binary">' +
          '<div style="font-size:48px;opacity:0.5;">&#128196;</div>' +
          '<div>二进制文件 (' + _formatSize(data.total_size) + ')</div>' +
          '<button class="files-preview-btn" onclick="FileManager.download(\'' +
          _escapeAttr(entry.path) + '\')">下载</button>' +
          '</div>';
      } else {
        // Text preview with line numbers
        editState.originalContent = data.content || '';
        _renderTextPreview(editState.originalContent);
        // Auto-enter edit mode when opened via context menu "Edit"
        if (editMode) _enterEditMode();
      }
    } catch (e) {
      overlay.querySelector('#filesPreviewEdit').style.display = 'none';
      bodyEl.innerHTML = '<div class="files-preview-binary"><div>加载文件失败: ' + _escapeHtml(e.message) + '</div></div>';
    }
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
        return { path: t.path, name: t.name };
      }),
      activeTabId: _activeTabId,
      activeTabIndex: activeIdx,
    };
    if (typeof persistSave === 'function') {
      await persistSave('files.json', data);
    }
  }

  async function _restoreSession() {
    try {
      if (typeof persistLoad === 'function') {
        var data = await persistLoad('files.json');
        if (data && data.tabs && data.tabs.length > 0) {
          // Suppress _saveSession during batch creation to avoid
          // overwriting the saved state with partial data.
          _restoringSession = true;
          for (var i = 0; i < data.tabs.length; i++) {
            createTab(data.tabs[i].path);
          }
          _restoringSession = false;

          // Restore active tab by saved index (IDs change on recreation)
          var restoreIdx = data.activeTabIndex;
          if (restoreIdx == null || restoreIdx < 0 || restoreIdx >= _tabs.length) {
            // Fallback: try matching by saved ID, then default to last tab
            restoreIdx = _tabs.length - 1;
            if (data.activeTabId) {
              for (var j = 0; j < _tabs.length; j++) {
                if (_tabs[j].id === data.activeTabId) { restoreIdx = j; break; }
              }
            }
          }
          if (restoreIdx >= 0 && restoreIdx < _tabs.length) {
            _switchToTab(_tabs[restoreIdx].id);
          }

          // Persist the now-complete restored state
          _saveSession();
          return;
        }
      }
    } catch (e) { /* ignore */ }

    // No saved session — open at project root
    _restoringSession = false;
    createTab(_projectRoot || '/');
  }

  // ========================= Utilities =========================

  function _pathDisplayName(path) {
    if (!path || path === '/') return 'Root';
    // Windows drive letter: "C:\", "C:\Users", etc.
    var winMatch = path.match(/^([a-zA-Z]:\\?)(.*)/);
    if (winMatch) {
      var rest = winMatch[2];
      if (!rest || rest === '\\') return winMatch[1].replace(/\\$/, '');
      var parts = rest.split(/[\/\\]/).filter(Boolean);
      return parts[parts.length - 1] || winMatch[1].replace(/\\$/, '');
    }
    // Unix paths
    var parts = path.replace(/[\/\\]+$/, '').split(/[\/\\]/).filter(Boolean);
    return parts[parts.length - 1] || 'Root';
  }

  function _formatSize(bytes) {
    if (bytes == null) return '-';
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
    return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
  }

  function _formatDate(ts) {
    if (!ts) return '-';
    var d = new Date(ts * 1000);
    var y = d.getFullYear();
    var m = String(d.getMonth() + 1).padStart(2, '0');
    var day = String(d.getDate()).padStart(2, '0');
    var h = String(d.getHours()).padStart(2, '0');
    var min = String(d.getMinutes()).padStart(2, '0');
    return y + '-' + m + '-' + day + ' ' + h + ':' + min;
  }

  function _fileIcon(name) {
    var ext = (name || '').split('.').pop().toLowerCase();
    var map = {
      'js': '\uD83D\uDFE8', 'ts': '\uD83D\uDD35', 'py': '\uD83D\uDC0D',
      'json': '{}', 'html': '\uD83C\uDF10', 'css': '\uD83C\uDFA8',
      'md': '\uD83D\uDCDD', 'txt': '\uD83D\uDCC4', 'yml': '\u2699',
      'yaml': '\u2699', 'toml': '\u2699', 'sh': '\uD83D\uDCBB',
      'png': '\uD83D\uDDBC', 'jpg': '\uD83D\uDDBC', 'jpeg': '\uD83D\uDDBC',
      'gif': '\uD83D\uDDBC', 'svg': '\uD83D\uDDBC',
    };
    return map[ext] || '\uD83D\uDCC4';
  }

  function _detectLanguage(filename) {
    var ext = (filename || '').split('.').pop().toLowerCase();
    var map = {
      'py': 'python', 'js': 'javascript', 'ts': 'typescript',
      'html': 'html', 'css': 'css', 'json': 'json',
      'toml': 'ini', 'yaml': 'yaml', 'yml': 'yaml',
      'md': 'markdown', 'sh': 'bash', 'bash': 'bash',
      'sql': 'sql', 'xml': 'xml', 'java': 'java',
      'go': 'go', 'rs': 'rust', 'rb': 'ruby',
      'php': 'php', 'c': 'c', 'cpp': 'cpp', 'h': 'c',
      'cs': 'csharp', 'swift': 'swift', 'kt': 'kotlin',
    };
    return map[ext] || 'plaintext';
  }

  function _escapeHtml(text) {
    var d = document.createElement('div');
    d.textContent = String(text);
    return d.innerHTML;
  }

  function _escapeAttr(text) {
    return String(text).replace(/&/g, '&amp;').replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // ========================= File Search =========================

  function _focusSearch() {
    if (_searchInput) {
      _searchInput.focus();
      _searchInput.select();
    }
  }

  function _clearSearch() {
    if (_searchInput) {
      _searchInput.value = '';
    }
    _hideSearchResults();
    if (_searchDebounceTimer) {
      clearTimeout(_searchDebounceTimer);
      _searchDebounceTimer = null;
    }
    if (_searchAbortCtrl) {
      _searchAbortCtrl.abort();
      _searchAbortCtrl = null;
    }
    // Remove has-query class from wrapper
    if (_searchInput && _searchInput.parentElement) {
      _searchInput.parentElement.classList.remove('has-query');
    }
  }

  function _hideSearchResults() {
    if (_searchResults) {
      _searchResults.classList.remove('visible');
    }
    _searchActiveIdx = -1;
  }

  function _debounceSearch(query, tab) {
    if (_searchDebounceTimer) {
      clearTimeout(_searchDebounceTimer);
      _searchDebounceTimer = null;
    }
    if (_searchAbortCtrl) {
      _searchAbortCtrl.abort();
      _searchAbortCtrl = null;
    }
    if (!query || query.length === 0) {
      _hideSearchResults();
      if (_searchResults) _searchResults.innerHTML = '';
      return;
    }
    _searchDebounceTimer = setTimeout(function () {
      _performSearch(query, tab);
    }, 300);
  }

  async function _performSearch(query, tab) {
    if (!_searchResults) return;

    // Show loading state
    _searchResults.innerHTML = '<div class="files-search-loading">Searching...</div>';
    _searchResults.classList.add('visible');
    _searchActiveIdx = -1;

    _searchAbortCtrl = new AbortController();
    var dirPath = tab.path || '/';

    try {
      var url = '/v1/webui/files/search?dir=' + encodeURIComponent(dirPath) +
        '&query=' + encodeURIComponent(query) + '&recursive=true&max_results=100';

      var resp = await fetch(url, { signal: _searchAbortCtrl.signal });
      var data = await resp.json();

      if (!resp.ok) {
        _searchResults.innerHTML = '<div class="files-search-empty">' + _escapeHtml(data.error || '搜索失败') + '</div>';
        return;
      }

      var results = data.results || [];
      _renderSearchResults(results, dirPath);
    } catch (e) {
      if (e.name === 'AbortError') return;
      _searchResults.innerHTML = '<div class="files-search-empty">搜索出错: ' + _escapeHtml(e.message) + '</div>';
    }
  }

  function _renderSearchResults(results, searchDir) {
    if (!_searchResults) return;
    _searchResults.innerHTML = '';
    _searchActiveIdx = -1;

    if (results.length === 0) {
      _searchResults.innerHTML = '<div class="files-search-empty">未找到结果</div>';
      _searchResults.classList.add('visible');
      return;
    }

    for (var i = 0; i < results.length; i++) {
      var entry = results[i];
      var item = document.createElement('div');
      item.className = 'files-search-result';
      item.dataset.path = entry.path;
      item.dataset.isDir = entry.is_dir ? '1' : '0';

      var icon = document.createElement('span');
      icon.className = 'files-search-result-icon';
      icon.textContent = entry.is_dir ? '\uD83D\uDCC1' : _fileIcon(entry.name);
      item.appendChild(icon);

      var info = document.createElement('div');
      info.className = 'files-search-result-info';

      var nameEl = document.createElement('div');
      nameEl.className = 'files-search-result-name';
      nameEl.textContent = entry.name;
      info.appendChild(nameEl);

      // Show relative path from search directory
      var relPath = _searchRelativePath(entry.path, searchDir);
      if (relPath) {
        var pathEl = document.createElement('div');
        pathEl.className = 'files-search-result-path';
        pathEl.textContent = relPath;
        info.appendChild(pathEl);
      }

      item.appendChild(info);

      (function (e) {
        item.addEventListener('click', function (ev) {
          ev.stopPropagation();
          _handleSearchResultClick(e);
        });
      })(entry);

      _searchResults.appendChild(item);
    }

    _searchResults.classList.add('visible');
  }

  function _searchRelativePath(filePath, searchDir) {
    // Normalise both paths to use forward slashes for comparison
    var normDir = (searchDir || '/').replace(/\\/g, '/').replace(/\/$/, '') || '/';
    var normPath = (filePath || '').replace(/\\/g, '/').replace(/\/$/, '');

    // Get parent directory of the result
    var lastSlash = normPath.lastIndexOf('/');
    var parentDir = lastSlash > 0 ? normPath.substring(0, lastSlash) : '/';

    if (parentDir === normDir || parentDir === searchDir) return null;

    // If parent starts with search dir, show relative
    var dirPrefix = normDir === '/' ? '/' : normDir + '/';
    if (normDir === '/' && parentDir !== '/') {
      return parentDir;
    }
    if (parentDir.indexOf(dirPrefix) === 0) {
      return parentDir.substring(dirPrefix.length);
    }

    return parentDir;
  }

  function _handleSearchResultClick(entry) {
    var tab = _getActiveTab();
    if (!tab) return;

    _hideSearchResults();

    if (entry.is_dir) {
      // Navigate into the directory
      _navigateTo(tab, entry.path);
    } else {
      // Navigate to parent directory, then highlight the file
      var parentDir = _parentPath(entry.path);
      if (!parentDir) parentDir = '/';

      _navigateTo(tab, parentDir);

      // Highlight the file after directory loads (wait for render)
      setTimeout(function () {
        var rows = _body ? _body.querySelectorAll('.files-table tbody tr') : [];
        for (var i = 0; i < rows.length; i++) {
          if (rows[i].dataset.path === entry.path) {
            rows[i].classList.add('selected');
            rows[i].scrollIntoView({ block: 'nearest' });
            break;
          }
        }
      }, 200);
    }

    // Clear search after navigation
    _clearSearch();
  }

  function _navigateSearchResults(direction) {
    if (!_searchResults || !_searchResults.classList.contains('visible')) return;

    var items = _searchResults.querySelectorAll('.files-search-result');
    if (items.length === 0) return;

    // Remove active from current
    if (_searchActiveIdx >= 0 && _searchActiveIdx < items.length) {
      items[_searchActiveIdx].classList.remove('active');
    }

    _searchActiveIdx += direction;
    if (_searchActiveIdx < 0) _searchActiveIdx = items.length - 1;
    if (_searchActiveIdx >= items.length) _searchActiveIdx = 0;

    items[_searchActiveIdx].classList.add('active');
    items[_searchActiveIdx].scrollIntoView({ block: 'nearest' });
  }

  return {
    init: init,
    createTab: createTab,
    closeTab: closeTab,
    download: _downloadFile,
  };
})();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function () { FileManager.init(); });
} else {
  FileManager.init();
}