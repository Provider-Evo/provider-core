/**
 * File Manager -- HTML template builders for the multi-tab editor window
 * chrome (titlebar, toolbar, search panel, statusbar).
 *
 * Part of the files.js split. Pure string builders; no DOM/state access.
 * Used by editor.js's _ensureEditorWindow via _editorWindowTemplate().
 */

function _editorWindowTitlebarTemplate() {
  return '' +
    '<div class="files-editor2-titlebar">' +
      '<div class="files-editor2-wintitle">' + t('files.editorTitle') + '</div>' +
      '<div class="files-editor2-winctrls">' +
        '<button type="button" class="files-editor2-winbtn" data-act="min" title="' + t('files.minimize') + '">&#8212;</button>' +
        '<button type="button" class="files-editor2-winbtn" data-act="max" title="' + t('files.maximize') + '">&#9723;</button>' +
        '<button type="button" class="files-editor2-winbtn files-editor2-winbtn-close" data-act="close" title="' + t('common.close') + '">&#10005;</button>' +
      '</div>' +
    '</div>';
}

function _editorSearchPanelTemplate() {
  return '' +
    '<div class="files-editor2-search-panel" id="filesEditorSearchPanel" hidden>' +
      '<input type="text" class="files-editor2-search-input" id="filesEditorSearchInput" placeholder="' + t('files.searchPlaceholder2') + '">' +
      '<span class="files-editor2-search-count" id="filesEditorSearchCount"></span>' +
      '<button type="button" class="files-editor2-search-btn" data-act="prev" title="' + t('files.prevMatch') + '">&#8593;</button>' +
      '<button type="button" class="files-editor2-search-btn" data-act="next" title="' + t('files.nextMatch') + '">&#8595;</button>' +
      '<div class="files-editor2-replace-row" id="filesEditorReplaceRow" hidden>' +
        '<input type="text" class="files-editor2-search-input" id="filesEditorReplaceInput" placeholder="' + t('files.replacePlaceholder') + '">' +
        '<button type="button" class="files-editor2-search-btn" data-act="replaceOne">' + t('files.replace') + '</button>' +
        '<button type="button" class="files-editor2-search-btn" data-act="replaceAll">' + t('files.replaceAll') + '</button>' +
      '</div>' +
      '<button type="button" class="files-editor2-search-btn" data-act="closeSearch" title="' + t('common.close') + '">&#10005;</button>' +
    '</div>';
}

function _editorWindowToolbarTemplate() {
  return '' +
    '<div class="files-editor2-toolbar" id="filesEditorToolbar">' +
      '<button type="button" class="files-editor2-tool" data-act="save" title="' + t('files.save') + '">' + t('files.save') + '</button>' +
      '<button type="button" class="files-editor2-tool" data-act="saveAll" title="' + t('files.saveAll') + '">' + t('files.saveAll') + '</button>' +
      '<button type="button" class="files-editor2-tool" data-act="refresh" title="' + t('files.refresh') + '">' + t('files.refresh') + '</button>' +
      '<span class="files-editor2-sep"></span>' +
      '<button type="button" class="files-editor2-tool" data-act="search" title="' + t('files.search') + '">' + t('files.search') + '</button>' +
      '<button type="button" class="files-editor2-tool" data-act="replace" title="' + t('files.replace') + '">' + t('files.replace') + '</button>' +
      '<button type="button" class="files-editor2-tool" data-act="goto" title="' + t('files.gotoLine') + '">' + t('files.gotoLine') + '</button>' +
      '<span class="files-editor2-sep"></span>' +
      '<button type="button" class="files-editor2-tool" data-act="fontDec" title="' + t('files.fontSize') + '">A-</button>' +
      '<button type="button" class="files-editor2-tool" data-act="fontInc" title="' + t('files.fontSize') + '">A+</button>' +
      '<button type="button" class="files-editor2-tool" data-act="theme" title="' + t('files.theme') + '">' + t('files.theme') + '</button>' +
      '<button type="button" class="files-editor2-tool" data-act="settings" title="' + t('files.settings') + '">' + t('files.settings') + '</button>' +
      '<button type="button" class="files-editor2-tool" data-act="shortcuts" title="' + t('files.shortcuts') + '">' + t('files.shortcuts') + '</button>' +
      _editorSearchPanelTemplate() +
      '<div class="files-editor2-settings-panel" id="filesEditorSettingsPanel" hidden>' +
        '<label><input type="checkbox" id="filesEditorWrapToggle"> ' + t('files.wordWrap') + '</label>' +
      '</div>' +
      '<div class="files-editor2-shortcuts-panel" id="filesEditorShortcutsPanel" hidden>' +
        '<div>Ctrl+S ' + t('files.save') + '</div>' +
        '<div>Ctrl+F ' + t('files.search') + '</div>' +
        '<div>Ctrl+H ' + t('files.replace') + '</div>' +
        '<div>Ctrl+G ' + t('files.gotoLine') + '</div>' +
      '</div>' +
    '</div>';
}

function _editorWindowStatusbarTemplate() {
  return '' +
    '<div class="files-editor2-statusbar" id="filesEditorStatusbar">' +
      '<span class="files-editor2-status-path" id="statusPath"></span>' +
      '<span class="files-editor2-status-sep"></span>' +
      '<span id="statusLineEnding"></span>' +
      '<span class="files-editor2-status-sep"></span>' +
      '<span id="statusChars"></span>' +
      '<span class="files-editor2-status-sep"></span>' +
      '<span id="statusEncoding">UTF-8</span>' +
      '<span class="files-editor2-status-sep"></span>' +
      '<span id="statusLanguage"></span>' +
      '<span class="files-editor2-status-sep"></span>' +
      '<span id="statusCursor">Ln 1, Col 1</span>' +
    '</div>';
}

function _editorWindowTemplate() {
  return '' +
    '<div class="files-editor2-window" id="filesEditorWindow">' +
      _editorWindowTitlebarTemplate() +
      '<div class="files-editor2-main">' +
        '<div class="files-editor2-sidebar" id="filesEditorSidebar">' +
          '<div class="files-editor2-sidebar-header">' + t('files.fileTree') + '</div>' +
          '<div class="files-editor2-tree" id="filesEditorTree"></div>' +
        '</div>' +
        '<div class="files-editor2-content-col">' +
          '<div class="files-editor2-tabbar" id="filesEditorTabbar"></div>' +
          '<div class="files-editor2-editarea">' +
            _editorWindowToolbarTemplate() +
            '<div class="files-editor2-body" id="filesEditorBody"></div>' +
            _editorWindowStatusbarTemplate() +
          '</div>' +
        '</div>' +
      '</div>' +
    '</div>';
}
