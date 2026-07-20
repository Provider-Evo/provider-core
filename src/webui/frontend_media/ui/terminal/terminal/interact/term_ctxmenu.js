// ========================= Terminal: Right-Click Context Menu =========================
// Split from terminal.js. Builds and manages the per-tab right-click context
// menu, including the "move tab" submenu.

function _attachContextMenuMethods(ctx) {
  var m = {};

  _attachContextMenuMethodsSubBuildItems(ctx, m);
  _attachContextMenuMethodsSubShow(ctx, m);
  _attachContextMenuMethodsSubSubmenu(ctx, m);
  _attachContextMenuMethodsSubRename(ctx, m);

  ctx.showContextMenu = m._showContextMenu;
  ctx.hideContextMenu = m._hideContextMenu;
  ctx.promptRename = m._promptRename;
}

