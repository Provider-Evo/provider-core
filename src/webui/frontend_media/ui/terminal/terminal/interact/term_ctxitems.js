function _attachContextMenuMethodsSubBuildItems(ctx, m) {

  m._buildContextMenuItems = function _buildContextMenuItems(tabId) {
    var items = [
      { label: t('terminal.rename'), action: function () { ctx.promptRename(tabId); } },
      { label: t('terminal.changeColor'), action: function (e) { ctx.showColorPicker(tabId, e.clientX, e.clientY); } },
      { label: t('terminal.reconnect'), action: function () { ctx.reconnectTab(tabId); } },
      { separator: true },
      { label: t('terminal.duplicate'), action: function () { ctx.duplicateTab(tabId); } },
      { label: t('terminal.split'), action: function () { ctx.splitTab(tabId); } },
      { separator: true },
      { label: t('terminal.find'), action: function () { ctx.showSearchDialog(tabId); } },
      { label: t('terminal.exportText'), action: function () { ctx.exportText(tabId); } },
      { separator: true },
      { label: t('terminal.clearHistory'), action: function () { ctx.clearHistory(tabId); } },
      { label: t('terminal.restartTerminal'), action: function () { ctx.restartTerminal(tabId); } },
      { separator: true },
      { label: t('terminal.bgModeLabel', { mode: ctx.getBgModeLabel() }), action: function () { ctx.toggleTerminalBgMode(); } },
    ];

    // Add custom background options if in custom mode
    if (ctx.terminalBgMode === 'custom') {
      items.push({ separator: true });
      items.push({ label: t('terminal.bgImage'), action: function () { ctx.showImagePicker(); } });
      if (ctx.customBgImage) {
        items.push({ label: t('terminal.clearBgImage'), action: function () { ctx.clearCustomBgImage(); } });
        items.push({ label: t('terminal.opacityLabel', { percent: Math.round(ctx.customBgOpacity * 100) }), action: function () { ctx.cycleCustomBgOpacity(); } });
      }
    }

    items.push({ separator: true });
    items.push({
      label: t('terminal.moveTab'),
      submenu: [
        { label: t('terminal.moveLeft'), action: function () { ctx.moveTab(tabId, 'left'); } },
        { label: t('terminal.moveRight'), action: function () { ctx.moveTab(tabId, 'right'); } },
      ],
    });
    items.push({ separator: true });
    items.push({ label: t('terminal.close'), action: function () { ctx.closeTab(tabId); } });
    items.push({ label: t('terminal.closeOthers'), action: function () { ctx.closeOtherTabs(tabId); } });
    items.push({ label: t('terminal.closeToRight'), action: function () { ctx.closeTabsToRight(tabId); } });
    items.push({ label: t('terminal.closeAll'), action: function () { ctx.closeAllTabs(); }, danger: true });

    return items;
  };
}

function _appendContextMenuItem(ctx, m, items, i) {
  if (items[i].separator) {
    var sep = document.createElement('div');
    sep.className = 'terminal-context-menu-separator';
    ctx.contextMenu.appendChild(sep);
  } else if (items[i].submenu) {
    m._appendSubmenuItem(ctx.contextMenu, items[i]);
  } else {
    var item = document.createElement('div');
    item.className = 'terminal-context-menu-item' + (items[i].danger ? ' danger' : '');
    item.textContent = items[i].label;
    (function (action) {
      item.addEventListener('click', function (e) {
        e.stopPropagation();
        m._hideContextMenu();
        action(e);
      });
    })(items[i].action);
    ctx.contextMenu.appendChild(item);
  }
}

function _clampContextMenuPosition(ctx) {
  var rect = ctx.contextMenu.getBoundingClientRect();
  if (rect.right > window.innerWidth) {
    ctx.contextMenu.style.left = (window.innerWidth - rect.width - 8) + 'px';
  }
  if (rect.bottom > window.innerHeight) {
    ctx.contextMenu.style.top = (window.innerHeight - rect.height - 8) + 'px';
  }
}

function _attachContextMenuMethodsSubShow(ctx, m) {

  m._showContextMenu = function _showContextMenu(event, tabId) {
    m._hideContextMenu();

    ctx.contextMenu = document.createElement('div');
    ctx.contextMenu.className = 'terminal-context-menu';
    ctx.contextMenu.style.left = event.clientX + 'px';
    ctx.contextMenu.style.top = event.clientY + 'px';

    var items = m._buildContextMenuItems(tabId);
    for (var i = 0; i < items.length; i++) {
      _appendContextMenuItem(ctx, m, items, i);
    }

    document.body.appendChild(ctx.contextMenu);
    _clampContextMenuPosition(ctx);
  };

  m._hideContextMenu = function _hideContextMenu() {
    if (ctx.contextMenu) {
      ctx.contextMenu.remove();
      ctx.contextMenu = null;
    }
  };
}

function _attachContextMenuMethodsSubSubmenu(ctx, m) {

  /**
   * Append a context menu item that reveals a submenu on hover.
   * The submenu is positioned to the right of the parent item and
   * clamped to the viewport, matching the parent menu's clamping style.
   */
  m._appendSubmenuItem = function _appendSubmenuItem(menuEl, itemDef) {
    var item = document.createElement('div');
    item.className = 'terminal-context-menu-item has-submenu';
    item.textContent = itemDef.label;

    var submenu = document.createElement('div');
    submenu.className = 'terminal-context-menu-submenu';
    submenu.style.display = 'none';

    for (var i = 0; i < itemDef.submenu.length; i++) {
      (function (subItem) {
        var subEl = document.createElement('div');
        subEl.className = 'terminal-context-menu-item';
        subEl.textContent = subItem.label;
        subEl.addEventListener('click', function (e) {
          e.stopPropagation();
          m._hideContextMenu();
          subItem.action();
        });
        submenu.appendChild(subEl);
      })(itemDef.submenu[i]);
    }

    item.appendChild(submenu);
    item.addEventListener('mouseenter', function () {
      submenu.style.display = 'block';
      var rect = submenu.getBoundingClientRect();
      if (rect.right > window.innerWidth) {
        submenu.style.left = 'auto';
        submenu.style.right = '100%';
      }
    });
    item.addEventListener('mouseleave', function () {
      submenu.style.display = 'none';
    });

    menuEl.appendChild(item);
  };
}

function _attachContextMenuMethodsSubRename(ctx, m) {

  m._promptRename = function _promptRename(tabId) {
    var tab = ctx.getTabById(tabId);
    if (!tab) return;
    showInputDialog(t('terminal.renameTabPrompt'), {
      title: t('terminal.renameTabTitle'),
      defaultValue: tab.name,
      placeholder: t('terminal.renameTabPlaceholder')
    }).then(function(newName) {
      if (newName && newName.trim()) {
        ctx.renameTab(tabId, newName.trim());
      }
    });
  };
}
