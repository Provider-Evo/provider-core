/**
 * File Manager -- multi-tab file editor window (BaoTa-style floating editor
 * with sidebar file tree, search/replace, and HTML/Markdown preview modes).
 *
 * Part of the files.js split. Depends on state.js (path/format helpers),
 * editor_window.js (_ensureEditorWindow, window chrome wiring), and
 * editor_body.js (_editorRenderBody, _editorSearchStep, _editorReplaceOne,
 * _editorReplaceAll, _editorUpdateStatusbar, _editorUpdateLineNumbers,
 * _editorGotoLine, _editorSearchRefresh, _editorCloseSearchPanel).
 * Calls into upload.js/_downloadFile (via ops.js) for binary
 * download and dirlist.js/_parentPath (defined in state.js).
 */

var _editorWin = null;
var _editorTabSeq = 0;

function _editorFmtLineEnding(content) {
  return /\r\n/.test(content || '') ? 'CRLF' : 'LF';
}

function _editorDetectLangLabel(name) {
  var lang = _detectLanguage(name);
  return lang ? lang.toUpperCase() : t('files.plainText');
}

function _editorTogglePanel(panel) {
  if (!panel || !_editorWin) return;
  var wasHidden = panel.hidden;
  _editorWin.searchPanel.hidden = true;
  _editorWin.settingsPanel.hidden = true;
  _editorWin.shortcutsPanel.hidden = true;
  panel.hidden = !wasHidden;
}

function _editorToggleSearchPanel(withReplace) {
  var win = _editorWin;
  win.settingsPanel.hidden = true;
  win.shortcutsPanel.hidden = true;
  win.searchPanel.hidden = false;
  win.overlay.querySelector('#filesEditorReplaceRow').hidden = !withReplace;
  win.overlay.querySelector('#filesEditorSearchInput').focus();
  _editorSearchRefresh();
}

function _editorCloseSearchPanel() {
  if (_editorWin) _editorWin.searchPanel.hidden = true;
}

function _editorGlobalKeydown(e) {
  if (!_editorWin || _editorWin.overlay.hidden) return;
  if (e.key === 'Escape') {
    if (!_editorWin.searchPanel.hidden) { _editorCloseSearchPanel(); }
    return;
  }
  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
    e.preventDefault();
    _editorSaveActive();
  } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
    e.preventDefault();
    _editorToggleSearchPanel(false);
  } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'h') {
    e.preventDefault();
    _editorToggleSearchPanel(true);
  } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'g') {
    e.preventDefault();
    _editorGotoLine();
  }
}

function _editorActiveTab() {
  if (!_editorWin) return null;
  for (var i = 0; i < _editorWin.tabs.length; i++) {
    if (_editorWin.tabs[i].id === _editorWin.activeId) return _editorWin.tabs[i];
  }
  return null;
}

function _editorFindTabByPath(path) {
  if (!_editorWin) return null;
  for (var i = 0; i < _editorWin.tabs.length; i++) {
    if (_editorWin.tabs[i].entry.path === path) return _editorWin.tabs[i];
  }
  return null;
}

function _editorTabTitle(tab) {
  return tab.entry.name + (tab.dirty ? ' \u25CF' : '');
}

function _editorSyncTabTitle(tab) {
  if (_editorWin && _editorWin.bar) {
    _editorWin.bar.setTitle(tab.id, _editorTabTitle(tab));
  }
}

function _editorAddTabToBar(tab) {
  if (!_editorWin || !_editorWin.bar) return;
  _editorWin.bar.addTab({
    id: tab.id,
    type: 'editor',
    icon: '&#128196;',
    title: _editorTabTitle(tab),
    closable: true,
  });
  _editorWin.bar.setActive(tab.id);
}

function _editorCloseAllTabs() {
  var win = _editorWin;
  if (!win) return;
  var ids = win.tabs.map(function (t) { return t.id; });
  for (var i = 0; i < ids.length; i++) {
    _editorCloseTab(ids[i]);
  }
}

function _editorFlushActiveTab() {
  var win = _editorWin;
  if (!win) return;
  var tab = _editorActiveTab();
  if (!tab || !tab.editable) return;
  var ta = win.bodyEl.querySelector('.files-editor2-textarea');
  if (!ta) return;
  tab.content = ta.value;
}

function _editorActivateTab(id) {
  var win = _editorWin;
  if (!win) return;
  var same = win.activeId === id;
  if (!same) _editorFlushActiveTab();
  win.activeId = id;
  if (!same && win.bar) win.bar.setActive(id);
  _editorRenderBody();
}
function _editorPromptNewFile() {
  var win = _editorWin;
  var baseDir = win.treeRoot || '';
  showInputDialog(t('files.newFilePrompt'), {
    title: t('files.newFile'),
    placeholder: t('files.fileNamePlaceholder')
  }).then(function (name) {
    if (!name || !name.trim()) return;
    var newPath = _pathJoin(baseDir, name.trim());
    Api.post('/v1/webui/files/write', { path: newPath, content: '' }).then(function () {
      if (win.treeRoot) _editorRenderTree(win.treeRoot);
      _previewFile({ path: newPath, name: name.trim(), is_dir: false }, true);
    }).catch(function (e) {
      if (typeof toast === 'function') toast(t('files.genericFailed', { error: e.message }), 'error');
    });
  });
}

function _editorApplyWrap() {
  var win = _editorWin;
  win.bodyEl.querySelectorAll('.files-editor2-textarea').forEach(function (ta) {
    ta.style.whiteSpace = win.wrap ? 'pre-wrap' : 'pre';
  });
}

function _editorAdjustFontSize(delta) {
  var win = _editorWin;
  win.fontSize = Math.max(10, Math.min(24, win.fontSize + delta));
  win.bodyEl.style.fontSize = win.fontSize + 'px';
}

function _editorToggleTheme() {
  var win = _editorWin;
  win.theme = win.theme === 'dark' ? 'light' : 'dark';
  win.dialog.classList.toggle('files-editor2-theme-light', win.theme === 'light');
}

function _editorToggleMaximize() {
  var win = _editorWin;
  win.maximized = !win.maximized;
  win.dialog.classList.toggle('files-editor2-maximized', win.maximized);
}

function _editorMinimize() {
  _editorWin.overlay.hidden = true;
}

async function _editorCloseWindow() {
  var dirtyTabs = _editorWin.tabs.filter(function (tb) { return tb.dirty; });
  if (dirtyTabs.length > 0) {
    var confirmed = await showConfirmDialog(t('files.discardConfirm'), {
      title: t('files.discardTitle'),
      confirmText: t('files.discardButton'),
    });
    if (!confirmed) return;
  }
  _editorWin.tabs.forEach(function (tab) {
    if (tab.htmlHost) _clearHtmlPreviewHost(tab.htmlHost);
  });
  if (_editorWin.bar) {
    _editorWin.bar.dispose();
  }
  _editorWin.overlay.remove();
  document.removeEventListener('keydown', _editorGlobalKeydown);
  if (typeof window !== 'undefined' && window._tabBars) {
    delete window._tabBars.filesEditor2;
  }
  _editorWin = null;
}

async function _editorCloseTab(id) {
  var win = _editorWin;
  var idx = -1;
  for (var i = 0; i < win.tabs.length; i++) { if (win.tabs[i].id === id) { idx = i; break; } }
  if (idx === -1) return;
  if (win.activeId === id) _editorFlushActiveTab();
  var tab = win.tabs[idx];
  if (tab.dirty) {
    var confirmed = await showConfirmDialog(t('files.discardConfirm'), {
      title: t('files.discardTitle'),
      confirmText: t('files.discardButton'),
    });
    if (!confirmed) return;
  }
  if (tab.htmlHost) _clearHtmlPreviewHost(tab.htmlHost);
  win.tabs.splice(idx, 1);
  if (win.bar) win.bar.removeTab(id);
  if (win.activeId === id) {
    if (win.tabs.length > 0) {
      var next = win.tabs[Math.min(idx, win.tabs.length - 1)];
      win.activeId = next.id;
      if (win.bar) win.bar.setActive(win.activeId);
    } else {
      win.activeId = null;
    }
  }
  _editorRenderBody();
}

function _editorMarkDirty(tab) {
  if (!tab.dirty) {
    tab.dirty = true;
    _editorSyncTabTitle(tab);
  }
}

async function _editorSaveTab(tab) {
  try {
    await Api.post('/v1/webui/files/write', { path: tab.entry.path, content: tab.content });
    tab.originalContent = tab.content;
    tab.dirty = false;
    _editorSyncTabTitle(tab);
    if (typeof toast === 'function') toast(t('files.saveOk'), 'ok');
  } catch (e) {
    if (typeof toast === 'function') toast(t('files.saveFailed', { error: e.message }), 'error');
  }
}

function _editorSaveActive() {
  var tab = _editorActiveTab();
  if (tab && tab.editable) _editorSaveTab(tab);
}

async function _editorSaveAll() {
  var win = _editorWin;
  for (var i = 0; i < win.tabs.length; i++) {
    if (win.tabs[i].dirty && win.tabs[i].editable) await _editorSaveTab(win.tabs[i]);
  }
}

async function _editorRefreshActive() {
  var tab = _editorActiveTab();
  if (!tab) return;
  await _editorLoadTabContent(tab);
  _editorRenderBody();
}

// _editorGotoLine, search/replace, statusbar, and _editorRenderBody
// (plus its content-kind helpers) have been moved to editor_body.js
// (part of the files.js split), to keep this file under the line limit.
// Tab content loading, file tree sidebar, and _previewFile entry point
// have been moved to edtree.js (part of the files.js split).
