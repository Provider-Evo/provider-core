/**
 * TabBar -- unified tab bar component for terminal and files modules.
 *
 * Provides horizontal top bar, vertical sidebar, and compressed sidebar layouts.
 * Each module creates its own TabBar instance and feeds it tab data.
 * TabBar fires events (onSwitch, onClose, onReorder, etc.) that the module handles.
 *
 * Usage:
 *   var bar = TabBar.create(container, {
 *     tabBarEl: element,
 *     bodyEl: element,
 *     layout: 'horizontal',
 *     collapsed: false,
 *     closeAllThreshold: 6,
 *     onSwitch: function(id) {},
 *     onClose: function(id) {},
 *     onContextMenu: function(id, event) {},
 *     onAdd: function(event) {},
 *     onCloseAll: function() {},
 *     onToggleCollapsed: function(collapsed) {},
 *   });
 *
 *   bar.addTab({ id, type, icon, title, closable, status });
 *   bar.setActive(id);
 *   bar.setStatus(id, 'connected');
 *   bar.setTitle(id, 'New Title');
 *   bar.setLayout('vertical', false);
 *   bar.removeTab(id);
 *   bar.dispose();
 *
 * ES5 compatible -- no let/const/arrow functions.
 *
 * Split across tabbar_core.js / tabbar_status.js / tabbar_preview.js /
 * tabbar_render.js / tabbar_crud.js / tabbar_layout.js. The _attachXxxMethods
 * helper functions are defined as top-level globals in the other files and
 * are only invoked from inside create(), after all scripts have loaded, so
 * script load order between them does not matter.
 *
 * create(container, options) creates a TabBar instance.
 *   container: the outer container (e.g., #terminalContainer), used for
 *     applying layout classes (tabbar-horizontal, tabbar-vertical, etc.)
 *     that affect the flex direction of the container itself.
 *   options.tabBarEl - the tab bar element to render tabs into
 *   options.bodyEl - the content/body area (stored for reference)
 *   options.layout - 'horizontal' | 'vertical' (default 'horizontal')
 *   options.collapsed - initial collapsed state for vertical (default false)
 *   options.closeAllThreshold - min tab count to show close-all button (default 6)
 *   options.onSwitch(tabId) - called when a tab is clicked
 *   options.onClose(tabId) - called when a tab close button is clicked
 *   options.onContextMenu(tabId, event) - called on right-click
 *   options.onAdd(event) - called when the "+" button is clicked
 *   options.onCloseAll() - called when close-all button is clicked
 *   options.onToggleCollapsed(collapsed) - called when sidebar toggle is clicked
 *   options.emptyMessage - message shown when no tabs exist
 *   returns a TabBar instance with public methods.
 */
var TabBar = (function () {

  function create(container, options) {
    options = options || {};

    var instance = {
      _container: container,
      _tabBarEl: options.tabBarEl,
      _bodyEl: options.bodyEl || null,
      _tabs: [],
      _activeId: null,
      _layout: options.layout || 'horizontal',
      _collapsed: !!options.collapsed,
      _opts: options,
      _closeAllThreshold: options.closeAllThreshold || 6,
      _toggleBtn: null,
      _closeAllBtn: null,
      _previewEl: null,
      _previewRaf: null,
      _thumbnails: {},
    };

    _attachStatusMethods(instance);
    _attachPreviewMethods(instance);
    _attachRenderMethods(instance);
    _attachTabCrudMethods(instance);
    _attachLayoutGetters(instance);

    instance.render();

    return instance;
  }

  return { create: create };
})();
