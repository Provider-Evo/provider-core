/**
 * File Manager -- cross-module integration helpers and right-click context menus.
 *
 * Part of the files.js split. Depends on state.js. Calls into
 * dirlist.js (_navigateTo), preview.js/files-editor-load.js
 * (_previewFile), ops.js (clipboard/rename/delete/new-folder),
 * upload.js (_triggerFilePicker), table.js (_downloadFile is
 * defined in ops.js).
 */

// ========================= Cross-Module Integration =========================

function _openInTerminal(dirPath) {
  if (typeof switchTab !== 'function') return;
  switchTab('terminal');
  setTimeout(function () {
    if (typeof TerminalManager === 'undefined') return;
    var parts = String(dirPath || '').split(/[\/\\]/).filter(Boolean);
    var label = parts.length ? parts[parts.length - 1] : dirPath;
    TerminalManager.createTab('local', { cwd: dirPath, name: label });
  }, 100);
}

function _copyPathToClipboard(path) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(path).then(function () {
      if (typeof toast === 'function') toast(t('files.pathCopied', { path: path }), 'ok');
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
    if (typeof toast === 'function') toast(t('files.pathCopied', { path: text }), 'ok');
  } catch (e) {
    if (typeof toast === 'function') toast(t('files.copyFailedShort'), 'error');
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
    items.push({ label: t('files.open'), action: function () { _navigateTo(tab, entry.path); } });
    items.push({ label: t('files.openInTerminal'), action: function () { _openInTerminal(entry.path); } });
  } else {
    items.push({ label: t('files.preview'), action: function () { _previewFile(entry); } });
    items.push({ label: t('files.edit'), action: function () { _previewFile(entry, true); } });
    items.push({ label: t('files.download'), action: function () { _downloadFile(entry.path); } });
  }

  items.push({ separator: true });
  items.push({ label: t('files.copyPath'), action: function () { _copyPathToClipboard(entry.path); } });
  items.push({ label: t('files.copy'), action: function () { _clipboardCopy([entry.path]); _renderContent(); } });
  items.push({ label: t('files.cut'), action: function () { _clipboardCut([entry.path]); _renderContent(); } });
  if (_clipboard.paths.length > 0) {
    items.push({ label: t('files.paste'), action: function () { _clipboardPaste(tab); } });
  }
  items.push({ separator: true });
  items.push({ label: t('files.rename'), action: function () { _showRenameDialog(tab, entry); } });
  items.push({ label: t('files.delete'), danger: true, action: function () { _deleteEntries(tab, [entry.path]); } });
  items.push({ separator: true });
  items.push({ label: t('files.newFolder'), action: function () { _promptNewFolder(tab); } });

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

  var tabIdx = -1;
  for (var i = 0; i < _tabs.length; i++) {
    if (_tabs[i].id === tabId) { tabIdx = i; break; }
  }
  var canMoveLeft = tabIdx > 0;
  var canMoveRight = tabIdx >= 0 && tabIdx < _tabs.length - 1;

  var items = [
    { label: t('files.renameTab'), action: function () { renameTab(tabId); } },
    { label: t('files.changeColor'), action: function () {
      var btn = _contextMenu.querySelector('[data-action="changeColor"]');
      var rect = btn ? btn.getBoundingClientRect() : { right: event.clientX, top: event.clientY };
      _showFileTabColorPicker(tabId, rect.right + 4, rect.top);
    }, attr: 'changeColor' },
    { label: t('files.duplicate'), action: function () { duplicateTab(tabId); } },
    { separator: true },
    { label: t('files.moveTab'), hasSubmenu: true, submenuItems: [
      { label: t('files.moveTabLeft'), disabled: !canMoveLeft, action: function () { moveTab(tabId, 'left'); } },
      { label: t('files.moveTabRight'), disabled: !canMoveRight, action: function () { moveTab(tabId, 'right'); } },
    ]},
    { separator: true },
    { label: t('files.close'), action: function () { closeTab(tabId); } },
    { label: t('files.closeOthers'), action: function () { _closeOtherTabs(tabId); } },
    { label: t('files.closeAll'), danger: true, action: function () { _closeAllTabs(); } },
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

  var canWrite = _canWriteToTab(tab);
  var items = [];
  if (canWrite) {
    items.push({ label: t('files.uploadFiles'), action: function () { _triggerFilePicker(); } });
    items.push({ separator: true });
    items.push({ label: t('files.newFolder'), action: function () { _promptNewFolder(tab); } });
  }
  items.push(
    { label: t('files.refresh'), action: function () { _loadDirectory(tab, tab.path); } },
    { separator: true },
    { label: t('files.openInTerminal'), action: function () { _openInTerminal(tab.path); } }
  );

  if (_clipboard.paths.length > 0) {
    items.push({ separator: true });
    items.push({ label: t('files.paste'), action: function () { _clipboardPaste(tab); } });
  }

  _populateMenu(_contextMenu, items);
  document.body.appendChild(_contextMenu);
  _adjustMenuPosition(_contextMenu);
}

function _populateMenu(menu, items) {
  for (var i = 0; i < items.length; i++) {
    var def = items[i];
    if (def.separator) {
      var sep = document.createElement('div');
      sep.className = 'files-context-menu-separator';
      menu.appendChild(sep);
    } else if (def.hasSubmenu) {
      _appendSubmenuItem(menu, def);
    } else {
      var item = document.createElement('div');
      item.className = 'files-context-menu-item';
      if (def.danger) item.className += ' danger';
      if (def.disabled) item.className += ' disabled';
      if (def.attr) item.dataset.action = def.attr;
      item.textContent = def.label;
      if (!def.disabled) {
        (function (action) {
          item.addEventListener('click', function (e) {
            e.stopPropagation();
            _hideContextMenu();
            action();
          });
        })(def.action);
      }
      menu.appendChild(item);
    }
  }
}

/**
 * Append a menu item that reveals a child submenu on hover.
 * The submenu is appended to document.body as a fixed panel so
 * it is never clipped by overflow:hidden parents.
 */
function _appendSubmenuItem(menu, def) {
  var item = document.createElement('div');
  item.className = 'files-context-menu-item has-submenu';
  item.textContent = def.label;

  var submenuEl = null;

  item.addEventListener('mouseenter', function () {
    if (submenuEl) return;
    submenuEl = document.createElement('div');
    submenuEl.className = 'files-context-menu-submenu';
    _populateMenu(submenuEl, def.submenuItems);

    var rect = item.getBoundingClientRect();
    submenuEl.style.left = rect.right + 'px';
    submenuEl.style.top = rect.top + 'px';
    document.body.appendChild(submenuEl);

    // Adjust if overflows viewport
    var sr = submenuEl.getBoundingClientRect();
    if (sr.right > window.innerWidth) {
      submenuEl.style.left = (rect.left - sr.width) + 'px';
    }
    if (sr.bottom > window.innerHeight) {
      submenuEl.style.top = (window.innerHeight - sr.height - 8) + 'px';
    }
  });

  item.addEventListener('mouseleave', function (e) {
    if (submenuEl && !submenuEl.contains(e.relatedTarget)) {
      submenuEl.remove();
      submenuEl = null;
    }
  });

  // Keep submenu alive while mouse is inside it
  item.addEventListener('mouseenter', function () {
    if (submenuEl) {
      submenuEl.addEventListener('mouseleave', function () {
        submenuEl.remove();
        submenuEl = null;
      }, { once: true });
    }
  });

  menu.appendChild(item);
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
