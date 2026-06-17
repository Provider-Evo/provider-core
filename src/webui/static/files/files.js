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

  // DOM references
  var _container = null;
  var _tabBar = null;
  var _body = null;

  // ========================= Initialization =========================

  function init() {
    _container = document.getElementById('filesContainer');
    _tabBar = document.getElementById('filesTabBar');
    _body = document.getElementById('filesBody');
    if (!_container || !_tabBar || !_body) return;

    document.addEventListener('click', function () { _hideContextMenu(); });

    // Register with Router
    if (typeof Router !== 'undefined') {
      Router.register('files', {
        activate: function () { _onActivate(); },
        deactivate: function () { _onDeactivate(); },
      });
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

  function createTab(path) {
    if (typeof switchTab === 'function') switchTab('files');

    _tabCounter++;
    var tabId = 'file-' + _tabCounter + '-' + Date.now();
    path = path || '/';
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
    };

    _tabs.push(tab);
    _renderTabBar();
    _switchToTab(tabId);
    _loadDirectory(tab, path);
    _saveSession();
    return tab;
  }

  function _switchToTab(tabId) {
    _activeTabId = tabId;
    _renderTabBar();
    _renderContent();
  }

  function closeTab(tabId) {
    var idx = -1;
    for (var i = 0; i < _tabs.length; i++) {
      if (_tabs[i].id === tabId) { idx = i; break; }
    }
    if (idx === -1) return;

    _tabs.splice(idx, 1);

    if (_activeTabId === tabId) {
      if (_tabs.length > 0) {
        var newIdx = Math.min(idx, _tabs.length - 1);
        _switchToTab(_tabs[newIdx].id);
      } else {
        _activeTabId = null;
        _renderTabBar();
        _renderContent();
      }
    } else {
      _renderTabBar();
    }
    _saveSession();
  }

  function _getActiveTab() {
    for (var i = 0; i < _tabs.length; i++) {
      if (_tabs[i].id === _activeTabId) return _tabs[i];
    }
    return null;
  }

  // ========================= Tab Bar Rendering =========================

  function _renderTabBar() {
    if (!_tabBar) return;

    // Save sidebar toggle button before clearing
    var sidebarToggle = _tabBar.querySelector('.tab-sidebar-toggle');
    _tabBar.innerHTML = '';

    for (var i = 0; i < _tabs.length; i++) {
      var tab = _tabs[i];
      var el = document.createElement('div');
      el.className = 'files-tab' + (tab.id === _activeTabId ? ' active' : '');
      el.dataset.tabId = tab.id;

      el.innerHTML =
        '<span class="files-tab-name">' + _escapeHtml(tab.name) + '</span>' +
        '<span class="files-tab-close">&times;</span>';

      (function (tid) {
        el.addEventListener('click', function (e) {
          if (e.target.classList.contains('files-tab-close')) {
            closeTab(tid);
          } else {
            _switchToTab(tid);
          }
        });
        el.addEventListener('contextmenu', function (e) {
          e.preventDefault();
          _showTabContextMenu(e, tid);
        });
      })(tab.id);

      _tabBar.appendChild(el);
    }

    // Re-add sidebar toggle button
    if (sidebarToggle) {
      _tabBar.insertBefore(sidebarToggle, _tabBar.firstChild);
    }

    // Add button
    var addBtn = document.createElement('div');
    addBtn.className = 'files-tab-add';
    addBtn.innerHTML = '+';
    addBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      createTab('/');
    });
    _tabBar.appendChild(addBtn);
  }

  // ========================= Directory Loading =========================

  async function _loadDirectory(tab, path) {
    tab.loading = true;
    _renderContent();

    try {
      var data = await Api.fetchJson('/v1/webui/files/list?path=' + encodeURIComponent(path));
      tab.entries = data.entries || [];
      tab.path = data.path || path;
      tab.name = _pathDisplayName(tab.path);
      tab.loading = false;
      _renderTabBar();
      _renderContent();
    } catch (e) {
      tab.loading = false;
      tab.entries = [];
      _renderContent();
      if (typeof toast === 'function') toast('Failed to load directory: ' + e.message, 'error');
    }
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
    var path = tab.path;
    if (path === '/' || !path) return;
    var parts = path.replace(/\/$/, '').split('/').filter(Boolean);
    parts.pop();
    var parent = '/' + parts.join('/');
    if (!parent || parent === '') parent = '/';
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
        '<div class="files-empty-text">No tabs open. Click + to browse files.</div>' +
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
      listArea.innerHTML = '<div class="files-loading">Loading...</div>';
    } else if (tab.entries.length === 0) {
      listArea.innerHTML = '<div class="files-empty"><div class="files-empty-text">Empty directory</div></div>';
    } else {
      var table = _buildTable(tab);
      listArea.appendChild(table);
    }

    _body.appendChild(listArea);
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
    backBtn.title = 'Back';
    backBtn.disabled = tab.historyIdx <= 0;
    backBtn.addEventListener('click', function () { _goBack(tab); });
    toolbar.appendChild(backBtn);

    // Forward button
    var fwdBtn = document.createElement('button');
    fwdBtn.className = 'files-nav-btn';
    fwdBtn.innerHTML = '&#9654;';
    fwdBtn.title = 'Forward';
    fwdBtn.disabled = tab.historyIdx >= tab.history.length - 1;
    fwdBtn.addEventListener('click', function () { _goForward(tab); });
    toolbar.appendChild(fwdBtn);

    // Up button
    var upBtn = document.createElement('button');
    upBtn.className = 'files-nav-btn';
    upBtn.innerHTML = '&#9650;';
    upBtn.title = 'Parent directory';
    upBtn.disabled = tab.path === '/';
    upBtn.addEventListener('click', function () { _goUp(tab); });
    toolbar.appendChild(upBtn);

    // Breadcrumb
    var breadcrumb = document.createElement('div');
    breadcrumb.className = 'files-breadcrumb';
    var segments = tab.path.split('/').filter(Boolean);

    // Root segment
    var rootSeg = document.createElement('span');
    rootSeg.className = 'files-breadcrumb-seg' + (segments.length === 0 ? ' current' : '');
    rootSeg.textContent = '/';
    rootSeg.addEventListener('click', function () { _navigateTo(tab, '/'); });
    breadcrumb.appendChild(rootSeg);

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

    breadcrumb.addEventListener('dblclick', function (e) {
      e.stopPropagation();
      _showPathInput(tab, toolbar, breadcrumb);
    });

    toolbar.appendChild(breadcrumb);

    // Actions
    var actions = document.createElement('div');
    actions.className = 'files-toolbar-actions';

    var newFolderBtn = document.createElement('button');
    newFolderBtn.className = 'files-toolbar-btn';
    newFolderBtn.textContent = '+ Folder';
    newFolderBtn.addEventListener('click', function () { _promptNewFolder(tab); });
    actions.appendChild(newFolderBtn);

    var refreshBtn = document.createElement('button');
    refreshBtn.className = 'files-toolbar-btn';
    refreshBtn.textContent = 'Refresh';
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
      { key: 'name', label: 'Name', cls: '' },
      { key: 'size', label: 'Size', cls: 'file-size' },
      { key: 'modified', label: 'Modified', cls: 'file-modified' },
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
      (function (e) {
        tr.addEventListener('click', function () {
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
      })(entry);

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

  // ========================= Context Menus =========================

  function _hideContextMenu() {
    if (_contextMenu) { _contextMenu.remove(); _contextMenu = null; }
  }

  function _showEntryContextMenu(event, tab, entry) {
    _hideContextMenu();
    _contextMenu = document.createElement('div');
    _contextMenu.className = 'files-context-menu';
    _contextMenu.style.left = event.clientX + 'px';
    _contextMenu.style.top = event.clientY + 'px';

    var items = [];

    if (entry.type === 'dir') {
      items.push({ label: 'Open', action: function () { _navigateTo(tab, entry.path); } });
    } else {
      items.push({ label: 'Preview', action: function () { _previewFile(entry); } });
      items.push({ label: 'Download', action: function () { _downloadFile(entry.path); } });
    }

    items.push({ separator: true });
    items.push({ label: 'Rename', action: function () { _showRenameDialog(tab, entry); } });
    items.push({ label: 'Delete', danger: true, action: function () { _deleteEntries(tab, [entry.path]); } });
    items.push({ separator: true });
    items.push({ label: 'New Folder', action: function () { _promptNewFolder(tab); } });

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
      { label: 'Close', action: function () { closeTab(tabId); } },
      { label: 'Close Others', action: function () { _closeOtherTabs(tabId); } },
      { label: 'Close All', danger: true, action: function () { _closeAllTabs(); } },
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
      { label: 'New Folder', action: function () { _promptNewFolder(tab); } },
      { label: 'Refresh', action: function () { _loadDirectory(tab, tab.path); } },
    ];

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
      'Delete "' + paths[0].split('/').pop() + '"?' :
      'Delete ' + paths.length + ' items?';
    if (!confirm(msg)) return;

    try {
      var resp = await Api.post('/v1/webui/files/delete', { paths: paths });
      var ok = (resp.results || []).every(function (r) { return r.ok; });
      if (ok) {
        if (typeof toast === 'function') toast('Deleted successfully', 'ok');
        _loadDirectory(tab, tab.path);
      } else {
        var errs = (resp.results || []).filter(function (r) { return !r.ok; });
        if (typeof toast === 'function') toast('Delete failed: ' + errs[0].error, 'error');
      }
    } catch (e) {
      if (typeof toast === 'function') toast('Delete failed: ' + e.message, 'error');
    }
  }

  function _showRenameDialog(tab, entry) {
    var overlay = document.createElement('div');
    overlay.className = 'files-rename-overlay';

    overlay.innerHTML =
      '<div class="files-rename-dialog">' +
      '<h3>Rename</h3>' +
      '<input type="text" id="filesRenameInput" value="' + _escapeAttr(entry.name) + '">' +
      '<div class="files-rename-actions">' +
      '<button class="files-rename-cancel" type="button">Cancel</button>' +
      '<button class="files-rename-confirm" type="button">Rename</button>' +
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

      var parentPath = entry.path.replace(/\/[^/]+\/?$/, '') || '/';
      var newPath = (parentPath === '/' ? '/' : parentPath + '/') + newName;

      Api.post('/v1/webui/files/rename', {
        old_path: entry.path,
        new_path: newPath,
      }).then(function () {
        if (typeof toast === 'function') toast('Renamed', 'ok');
        _loadDirectory(tab, tab.path);
      }).catch(function (e) {
        if (typeof toast === 'function') toast('Rename failed: ' + e.message, 'error');
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
    var name = prompt('New folder name:');
    if (!name || !name.trim()) return;

    var basePath = tab.path === '/' ? '' : tab.path;
    var newPath = '/' + basePath.replace(/^\//, '') + '/' + name.trim();
    // Clean double slashes
    newPath = newPath.replace(/\/+/g, '/');

    Api.post('/v1/webui/files/mkdir', { path: newPath }).then(function () {
      if (typeof toast === 'function') toast('Folder created', 'ok');
      _loadDirectory(tab, tab.path);
    }).catch(function (e) {
      if (typeof toast === 'function') toast('Failed: ' + e.message, 'error');
    });
  }

  // ========================= File Preview =========================

  async function _previewFile(entry) {
    var overlay = document.createElement('div');
    overlay.className = 'files-preview-overlay';

    overlay.innerHTML =
      '<div class="files-preview-dialog">' +
      '<div class="files-preview-header">' +
      '<div class="files-preview-title">' + _escapeHtml(entry.name) + '</div>' +
      '<div class="files-preview-actions">' +
      '<button class="files-preview-btn" id="filesPreviewDownload">Download</button>' +
      '<button class="files-preview-btn" id="filesPreviewClose">Close</button>' +
      '</div></div>' +
      '<div class="files-preview-body"><div class="files-loading">Loading...</div></div>' +
      '</div>';

    document.body.appendChild(overlay);

    overlay.querySelector('#filesPreviewClose').addEventListener('click', function () {
      overlay.remove();
    });
    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) overlay.remove();
    });
    overlay.querySelector('#filesPreviewDownload').addEventListener('click', function () {
      _downloadFile(entry.path);
    });

    // Escape key
    function onKey(e) {
      if (e.key === 'Escape') { overlay.remove(); document.removeEventListener('keydown', onKey); }
    }
    document.addEventListener('keydown', onKey);

    try {
      var data = await Api.fetchJson('/v1/webui/files/read?path=' + encodeURIComponent(entry.path));
      var body = overlay.querySelector('.files-preview-body');

      if (data.encoding === 'base64' && data.content) {
        // Image preview
        body.innerHTML =
          '<div class="files-preview-image">' +
          '<img src="' + data.content + '" alt="' + _escapeAttr(entry.name) + '">' +
          '</div>';
      } else if (data.encoding === 'binary') {
        body.innerHTML =
          '<div class="files-preview-binary">' +
          '<div style="font-size:48px;opacity:0.5;">&#128196;</div>' +
          '<div>Binary file (' + _formatSize(data.total_size) + ')</div>' +
          '<button class="files-preview-btn" onclick="FileManager.download(\'' +
          _escapeAttr(entry.path) + '\')">Download</button>' +
          '</div>';
      } else {
        // Text preview with line numbers
        var code = document.createElement('pre');
        code.className = 'files-preview-code';
        var lines = (data.content || '').split('\n');
        // Remove trailing empty line from split
        if (lines.length > 0 && lines[lines.length - 1] === '') lines.pop();

        var startLine = (data.offset || 0) + 1;
        for (var i = 0; i < lines.length; i++) {
          var lineEl = document.createElement('span');
          lineEl.className = 'line';
          lineEl.textContent = lines[i] || ' ';
          code.appendChild(lineEl);
        }
        body.innerHTML = '';
        body.appendChild(code);
      }
    } catch (e) {
      var body = overlay.querySelector('.files-preview-body');
      body.innerHTML = '<div class="files-preview-binary"><div>Error loading file: ' + _escapeHtml(e.message) + '</div></div>';
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

  function _saveSession() {
    var data = {
      tabs: _tabs.map(function (t) {
        return { path: t.path, name: t.name };
      }),
      activeTabId: _activeTabId,
    };
    if (typeof persistSave === 'function') {
      persistSave('files.json', data);
    }
  }

  async function _restoreSession() {
    try {
      if (typeof persistLoad === 'function') {
        var data = await persistLoad('files.json');
        if (data && data.tabs && data.tabs.length > 0) {
          for (var i = 0; i < data.tabs.length; i++) {
            createTab(data.tabs[i].path);
          }
          // Restore active tab
          if (data.activeTabId && _tabs.length > 0) {
            // Find matching tab by index if id changed
            var idx = Math.min(
              data.tabs.findIndex(function (t) { return t.path === (data.tabs[0] || {}).path; }),
              _tabs.length - 1
            );
            if (idx >= 0) _switchToTab(_tabs[idx].id);
          }
          return;
        }
      }
    } catch (e) { /* ignore */ }

    // No saved session — show empty state
    _renderTabBar();
    _renderContent();
  }

  // ========================= Utilities =========================

  function _pathDisplayName(path) {
    if (!path || path === '/') return 'Root';
    var parts = path.replace(/\/$/, '').split('/').filter(Boolean);
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

  function _escapeHtml(text) {
    var d = document.createElement('div');
    d.textContent = String(text);
    return d.innerHTML;
  }

  function _escapeAttr(text) {
    return String(text).replace(/&/g, '&amp;').replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
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
