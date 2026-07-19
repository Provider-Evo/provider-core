/**
 * File Manager -- editor tab content loading and sidebar file tree
 * (BaoTa-style path panel) for the multi-tab editor window.
 *
 * Part of the files.js split. Depends on state.js and editor.js
 * (_editorWin, _ensureEditorWindow, _editorFindTabByPath, _editorActivateTab,
 * _editorAddTabToBar, _editorRenderBody, _editorTabSeq) and preview.js
 * (_isHtmlPreviewFile, _isMarkdownPreviewFile).
 */

function _editorApplyTextContent(tab, data) {
  tab.content = data.content || '';
  tab.originalContent = tab.content;
  tab.editable = true;
  if (_isHtmlPreviewFile(tab.entry.name)) { tab.kind = 'html'; tab.viewMode = tab.viewMode || 'source'; }
  else if (_isMarkdownPreviewFile(tab.entry.name)) { tab.kind = 'markdown'; tab.viewMode = tab.viewMode || 'source'; }
  else { tab.kind = 'text'; tab.viewMode = 'source'; }
}

function _editorApplyReadResponse(tab, data) {
  if (data.encoding === 'base64' && data.content) {
    tab.kind = 'image';
    tab.editable = false;
    tab.content = data.content;
    tab.totalSize = data.total_size;
  } else if (data.encoding === 'binary') {
    tab.kind = 'binary';
    tab.editable = false;
    tab.totalSize = data.total_size;
  } else {
    _editorApplyTextContent(tab, data);
  }
}

async function _editorLoadTabContent(tab) {
  tab.kind = 'text';
  tab.editable = true;
  try {
    var data = await Api.fetchJson('/v1/webui/files/read?path=' + encodeURIComponent(tab.entry.path));
    _editorApplyReadResponse(tab, data);
  } catch (e) {
    tab.kind = 'error';
    tab.errorMessage = e.message;
  }
  tab.dirty = false;
}

// ---- File tree sidebar (BaoTa-style path panel) ----

async function _editorLoadTreeDir(path) {
  if (_editorWin.treeCache[path]) return _editorWin.treeCache[path];
  try {
    var url = '/v1/webui/files/list?path=' + encodeURIComponent(path) + '&offset=0&limit=500';
    var data = await Api.fetchJson(url);
    var entries = data.entries || [];
    _editorWin.treeCache[path] = entries;
    return entries;
  } catch (e) {
    return [];
  }
}

function _editorTreeNodeHtml(entry, depth, expanded) {
  var isDir = entry.type === 'dir';
  return '<div class="files-editor2-tree-node" data-path="' + _escapeAttr(entry.path) + '" data-dir="' + (isDir ? '1' : '0') + '" style="padding-left:' + (depth * 16 + 8) + 'px;">' +
    (isDir ? '<span class="files-editor2-tree-caret">' + (expanded ? '&#9660;' : '&#9654;') + '</span>' : '<span class="files-editor2-tree-caret files-editor2-tree-caret-leaf"></span>') +
    '<span class="files-editor2-tree-icon">' + (isDir ? '&#128193;' : '&#128196;') + '</span>' +
    '<span class="files-editor2-tree-name">' + _escapeHtml(entry.name) + '</span>' +
    '</div>';
}

async function _editorRenderTree(rootPath) {
  var win = _editorWin;
  if (!win.treeRoot) win.treeRoot = rootPath;
  if (!win.treeExpanded) win.treeExpanded = {};
  win.treeExpanded[win.treeRoot] = true;

  async function renderLevel(path, depth) {
    var entries = await _editorLoadTreeDir(path);
    var html = '';
    for (var i = 0; i < entries.length; i++) {
      var entry = entries[i];
      var expanded = !!win.treeExpanded[entry.path];
      html += _editorTreeNodeHtml(entry, depth, expanded);
      if (entry.type === 'dir' && expanded) {
        html += await renderLevel(entry.path, depth + 1);
      }
    }
    return html;
  }

  var rootEntries = await _editorLoadTreeDir(win.treeRoot);
  var html = '';
  for (var i = 0; i < rootEntries.length; i++) {
    var entry = rootEntries[i];
    var expanded = !!win.treeExpanded[entry.path];
    html += _editorTreeNodeHtml(entry, 0, expanded);
    if (entry.type === 'dir' && expanded) {
      html += await renderLevel(entry.path, 1);
    }
  }
  win.treeEl.innerHTML = html;

  win.treeEl.querySelectorAll('.files-editor2-tree-node').forEach(function (node) {
    node.addEventListener('click', function () {
      var path = node.getAttribute('data-path');
      var isDir = node.getAttribute('data-dir') === '1';
      if (isDir) {
        win.treeExpanded[path] = !win.treeExpanded[path];
        _editorRenderTree(win.treeRoot);
      } else {
        var name = path.replace(/[\/\\]+$/, '').split(/[\/\\]/).pop();
        _previewFile({ path: path, name: name, is_dir: false });
      }
    });
  });
}

async function _previewFile(entry, editMode) {
  var win = _ensureEditorWindow();
  win.overlay.hidden = false;

  if (!win.treeRoot) {
    var parentDir = _parentPath(entry.path) || entry.path;
    _editorRenderTree(parentDir);
  }

  var existing = _editorFindTabByPath(entry.path);
  if (existing) {
    existing.entry = entry;
    if (editMode) existing.focusOnOpen = true;
    _editorActivateTab(existing.id);
    return;
  }

  var tab = {
    id: 'tab-' + (++_editorTabSeq),
    entry: entry,
    kind: 'text',
    viewMode: 'source',
    content: '',
    originalContent: '',
    dirty: false,
    editable: true,
    totalSize: 0,
    htmlHost: null,
    focusOnOpen: !!editMode,
    _searchMatches: [],
    _searchIdx: -1,
    _searchQuery: '',
  };
  win.tabs.push(tab);
  win.activeId = tab.id;
  _editorAddTabToBar(tab);
  win.bodyEl.innerHTML = '<div class="files-loading">' + t('files.loading') + '</div>';

  await _editorLoadTabContent(tab);

  if (win.activeId === tab.id) {
    _editorRenderBody();
  }
  _editorSyncTabTitle(tab);
}
