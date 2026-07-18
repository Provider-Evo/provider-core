/**
 * File Manager -- editor window construction and chrome event wiring
 * (window state object, layout persistence, toolbar/win-control clicks).
 *
 * Part of the files.js split. Depends on editor.js (_editorWin,
 * _editorRenderTabbar, _editorGlobalKeydown and the various tab-action
 * functions it dispatches to) and editor_tmpl.js
 * (_editorWindowTemplate).
 */

function _editorBuildWinState(overlay) {
  return {
    overlay: overlay,
    dialog: overlay.querySelector('#filesEditorWindow'),
    tabbarEl: overlay.querySelector('#filesEditorTabbar'),
    toolbarEl: overlay.querySelector('#filesEditorToolbar'),
    bodyEl: overlay.querySelector('#filesEditorBody'),
    statusbarEl: overlay.querySelector('#filesEditorStatusbar'),
    searchPanel: overlay.querySelector('#filesEditorSearchPanel'),
    settingsPanel: overlay.querySelector('#filesEditorSettingsPanel'),
    shortcutsPanel: overlay.querySelector('#filesEditorShortcutsPanel'),
    sidebarEl: overlay.querySelector('#filesEditorSidebar'),
    treeEl: overlay.querySelector('#filesEditorTree'),
    treeCache: {},
    tabs: [],
    activeId: null,
    fontSize: 13,
    wrap: false,
    theme: 'dark',
    maximized: false,
    layout: 'horizontal',
    collapsed: false,
  };
}

function _editorWireLayout(win) {
  win.setCollapsed = function (collapsed) {
    win.collapsed = !!collapsed;
    win.dialog.classList.toggle('files-editor2-tabs-collapsed', win.layout === 'vertical' && win.collapsed);
    _editorRenderTabbar();
  };
  win.setLayout = function (layout, collapsed) {
    win.layout = layout || 'horizontal';
    win.dialog.classList.toggle('files-editor2-tabs-vertical', win.layout === 'vertical');
    win.setCollapsed(collapsed);
  };
  if (typeof window !== 'undefined' && window._tabLayoutConfig) {
    win.setLayout(window._tabLayoutConfig.layout, window._tabLayoutConfig.sidebarCompressed);
  }
  if (typeof window !== 'undefined') {
    window._tabBars = window._tabBars || {};
    window._tabBars.filesEditor2 = win;
  }
}

function _editorHandleToolClick(win, act) {
  // Dispatch table instead of an if/else-if chain to keep nesting depth low.
  var handlers = {
    save: _editorSaveActive,
    saveAll: _editorSaveAll,
    refresh: _editorRefreshActive,
    search: function () { _editorToggleSearchPanel(false); },
    replace: function () { _editorToggleSearchPanel(true); },
    goto: _editorGotoLine,
    fontDec: function () { _editorAdjustFontSize(-1); },
    fontInc: function () { _editorAdjustFontSize(1); },
    theme: _editorToggleTheme,
    settings: function () { _editorTogglePanel(win.settingsPanel); },
    shortcuts: function () { _editorTogglePanel(win.shortcutsPanel); },
  };
  if (handlers[act]) handlers[act]();
}

function _editorHandleSearchBtnClick(sact) {
  var handlers = {
    prev: function () { _editorSearchStep(-1); },
    next: function () { _editorSearchStep(1); },
    replaceOne: _editorReplaceOne,
    replaceAll: _editorReplaceAll,
    closeSearch: _editorCloseSearchPanel,
  };
  if (handlers[sact]) handlers[sact]();
}

function _editorWireToolbarClicks(win) {
  win.toolbarEl.addEventListener('click', function (e) {
    var btn = e.target.closest('.files-editor2-tool');
    if (btn) {
      _editorHandleToolClick(win, btn.getAttribute('data-act'));
      return;
    }
    var searchBtn = e.target.closest('.files-editor2-search-btn');
    if (searchBtn) {
      _editorHandleSearchBtnClick(searchBtn.getAttribute('data-act'));
    }
  });
}

function _editorWireWinEvents(win) {
  win.dialog.querySelector('.files-editor2-winctrls').addEventListener('click', function (e) {
    var btn = e.target.closest('.files-editor2-winbtn');
    if (!btn) return;
    var act = btn.getAttribute('data-act');
    if (act === 'close') _editorCloseWindow();
    else if (act === 'max') _editorToggleMaximize();
    else if (act === 'min') _editorMinimize();
  });

  _editorWireToolbarClicks(win);

  win.overlay.querySelector('#filesEditorSearchInput').addEventListener('input', function () {
    _editorSearchRefresh();
  });
  win.overlay.querySelector('#filesEditorWrapToggle').addEventListener('change', function (e) {
    win.wrap = e.target.checked;
    _editorApplyWrap();
  });

  document.addEventListener('keydown', _editorGlobalKeydown);
}

function _ensureEditorWindow() {
  if (_editorWin) return _editorWin;

  var overlay = document.createElement('div');
  overlay.className = 'files-editor2-overlay';
  overlay.innerHTML = _editorWindowTemplate();
  document.body.appendChild(overlay);

  var win = _editorBuildWinState(overlay);
  _editorWin = win;

  _editorWireLayout(win);
  _editorWireWinEvents(win);

  return win;
}
