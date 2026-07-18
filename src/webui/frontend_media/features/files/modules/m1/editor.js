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

function _editorTabbarHtml(win, showCollapsed) {
  var html = '';
  if (win.layout === 'vertical') {
    html += '<button type="button" class="files-editor2-tabbar-toggle" title="' +
      _escapeHtml(t(showCollapsed ? 'files.expandSidebar' : 'files.compressSidebar')) + '">' +
      (showCollapsed ? '&#9654;' : '&#9664;') + '</button>';
  }
  for (var i = 0; i < win.tabs.length; i++) {
    var tab = win.tabs[i];
    html += '<div class="files-editor2-tab' + (tab.id === win.activeId ? ' is-active' : '') + '" data-id="' + tab.id + '" title="' + _escapeHtml(tab.entry.name) + '">';
    if (!showCollapsed) {
      html += '<span class="files-editor2-tab-name">' + _escapeHtml(tab.entry.name) + (tab.dirty ? ' &#9679;' : '') + '</span>' +
        '<span class="files-editor2-tab-close" data-id="' + tab.id + '">&#10005;</span>';
    } else {
      html += '<span class="files-editor2-tab-icon">' + (tab.dirty ? '&#9679;' : '&#128196;') + '</span>';
    }
    html += '</div>';
  }
  if (!showCollapsed) {
    html += '<div class="files-editor2-tabbar-add" title="' + _escapeHtml(t('tabbar.addTab')) + '">+</div>';
  }
  return html;
}

function _editorWireTabbarEvents(win) {
  var toggleBtn = win.tabbarEl.querySelector('.files-editor2-tabbar-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      win.setCollapsed(!win.collapsed);
    });
  }
  var addBtn = win.tabbarEl.querySelector('.files-editor2-tabbar-add');
  if (addBtn) {
    addBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      _editorPromptNewFile();
    });
  }
  win.tabbarEl.querySelectorAll('.files-editor2-tab').forEach(function (el) {
    el.addEventListener('click', function (e) {
      if (e.target.classList.contains('files-editor2-tab-close')) return;
      _editorActivateTab(el.getAttribute('data-id'));
    });
  });
  win.tabbarEl.querySelectorAll('.files-editor2-tab-close').forEach(function (el) {
    el.addEventListener('click', function (e) {
      e.stopPropagation();
      _editorCloseTab(el.getAttribute('data-id'));
    });
  });
}

function _editorRenderTabbar() {
  var win = _editorWin;
  var showCollapsed = win.layout === 'vertical' && win.collapsed;
  win.tabbarEl.innerHTML = _editorTabbarHtml(win, showCollapsed);
  _editorWireTabbarEvents(win);
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

function _editorActivateTab(id) {
  _editorWin.activeId = id;
  _editorRenderTabbar();
  _editorRenderBody();
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
  if (win.activeId === id) {
    if (win.tabs.length > 0) {
      var next = win.tabs[Math.min(idx, win.tabs.length - 1)];
      win.activeId = next.id;
    } else {
      win.activeId = null;
    }
  }
  _editorRenderTabbar();
  _editorRenderBody();
}

function _editorMarkDirty(tab) {
  if (!tab.dirty) {
    tab.dirty = true;
    _editorRenderTabbar();
  }
}

async function _editorSaveTab(tab) {
  try {
    await Api.post('/v1/webui/files/write', { path: tab.entry.path, content: tab.content });
    tab.originalContent = tab.content;
    tab.dirty = false;
    _editorRenderTabbar();
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
