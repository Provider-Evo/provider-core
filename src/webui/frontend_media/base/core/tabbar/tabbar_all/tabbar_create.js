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
 * Implementation note: method groups are defined in sibling files
 * (tabbar_preview.js, tabbar_render.js, tabbar_crud.js) as attach functions
 * registered on window.__tabbarAttach. Those files must load before this
 * one so create() can mount their methods onto each new instance.
 */
/**
 * Mount all method groups from the registered attach functions onto the
 * instance. Each group lives in its own file and registers itself under
 * window.__tabbarAttach before this file runs.
 */
function _attachAllTabBarMethods(instance) {
  var attach = window.__tabbarAttach || {};
  if (attach.preview) attach.preview(instance);
  if (attach.render) attach.render(instance);
  if (attach.crud) attach.crud(instance);
}

/**
 * Create a TabBar instance.
 *
 * @param {HTMLElement} container - The outer container (e.g., #terminalContainer).
 *   Used for applying layout classes (tabbar-horizontal, tabbar-vertical, etc.)
 *   that affect the flex direction of the container itself.
 * @param {Object} options
 *   @param {HTMLElement} options.tabBarEl - The tab bar element to render tabs into
 *   @param {HTMLElement} options.bodyEl - The content/body area (stored for reference)
 *   @param {string} options.layout - 'horizontal' | 'vertical' (default 'horizontal')
 *   @param {boolean} options.collapsed - Initial collapsed state for vertical (default false)
 *   @param {number} options.closeAllThreshold - Min tab count to show close-all button (default 6)
 *   @param {Function} options.onSwitch - Callback(tabId) when a tab is clicked
 *   @param {Function} options.onClose - Callback(tabId) when a tab close button is clicked
 *   @param {Function} options.onContextMenu - Callback(tabId, event) on right-click
 *   @param {Function} options.onAdd - Callback(event) when the "+" button is clicked
 *   @param {Function} options.onCloseAll - Callback() when close-all button is clicked
 *   @param {Function} options.onToggleCollapsed - Callback(collapsed) when sidebar toggle is clicked
 *   @param {string} options.emptyMessage - Message shown when no tabs exist
 * @returns {Object} TabBar instance with public methods
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

    _attachAllTabBarMethods(instance);

    instance.render();

    return instance;
  }

  return { create: create };
})();
