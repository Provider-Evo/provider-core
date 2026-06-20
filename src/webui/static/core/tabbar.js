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
 */
var TabBar = (function () {

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
    };

    // ========================= Rendering =========================

    /**
     * Full re-render of the tab bar.
     * Detaches persistent elements (toggle button) before clearing innerHTML,
     * then reattaches them after.
     */
    instance.render = function () {
      if (!this._tabBarEl) return;

      // Detach toggle button to survive innerHTML clear
      var toggleBtn = this._toggleBtn;
      if (toggleBtn && toggleBtn.parentNode) {
        toggleBtn.parentNode.removeChild(toggleBtn);
      }

      // Clear tab bar content
      this._tabBarEl.innerHTML = '';

      // Apply layout classes to the tab bar element
      this._tabBarEl.className = 'unified-tabbar ' + this._layout;
      if (this._layout === 'vertical' && this._collapsed) {
        this._tabBarEl.className += ' collapsed tabbar-compressed';
      }

      // Apply layout classes to the container (for flex-direction control in CSS)
      if (this._container) {
        this._container.classList.toggle('tabbar-horizontal', this._layout === 'horizontal');
        this._container.classList.toggle('tabbar-vertical', this._layout === 'vertical');
      }

      // Render each tab element
      for (var i = 0; i < this._tabs.length; i++) {
        this._tabBarEl.appendChild(this._createTabElement(this._tabs[i]));
      }

      // Render "+" add button
      var addBtn = document.createElement('div');
      addBtn.className = 'unified-tabbar-add';
      addBtn.textContent = '+';
      addBtn.title = '\u65B0\u5EFA\u6807\u7B7E'; // 新建标签
      var self = this;
      addBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (self._opts.onAdd) self._opts.onAdd(e);
      });
      this._tabBarEl.appendChild(addBtn);

      // Show empty message when no tabs exist
      if (this._tabs.length === 0 && this._opts.emptyMessage) {
        var emptyEl = document.createElement('div');
        emptyEl.className = 'unified-tabbar-empty';
        emptyEl.textContent = this._opts.emptyMessage;
        this._tabBarEl.appendChild(emptyEl);
      }

      // Re-attach or create toggle button (vertical mode only)
      if (toggleBtn) {
        this._toggleBtn = toggleBtn;
      }
      this._renderToggleBtn();

      // Update close-all button visibility
      this._updateCloseAll();
    };

    /**
     * Create a DOM element for a single tab.
     * Structure: icon + status + title + close
     */
    instance._createTabElement = function (tab) {
      var el = document.createElement('div');
      el.className = 'unified-tab' + (tab.id === this._activeId ? ' active' : '');
      el.setAttribute('data-tab-id', tab.id);
      el.setAttribute('data-tooltip', tab.title || '');

      var self = this;

      // Icon slot -- ALWAYS present for every tab type
      var iconEl = document.createElement('span');
      iconEl.className = 'unified-tab-icon';
      iconEl.innerHTML = tab.icon || '';
      el.appendChild(iconEl);

      // Status dot -- shown only when status is set (connecting/connected/disconnected)
      if (tab.status) {
        var statusEl = document.createElement('span');
        statusEl.className = 'unified-tab-status ' + tab.status;
        el.appendChild(statusEl);
      }

      // Title text
      var titleEl = document.createElement('span');
      titleEl.className = 'unified-tab-title';
      titleEl.textContent = tab.title || '';
      el.appendChild(titleEl);

      // Close button (only if tab is closable)
      if (tab.closable !== false) {
        var closeEl = document.createElement('span');
        closeEl.className = 'unified-tab-close';
        closeEl.innerHTML = '&times;';
        closeEl.addEventListener('click', function (e) {
          e.stopPropagation();
          if (self._opts.onClose) self._opts.onClose(tab.id);
        });
        el.appendChild(closeEl);
      }

      // Tab click -> switch (left-click only)
      el.addEventListener('click', function (e) {
        if (e.button !== 0) return;
        if (self._opts.onSwitch) self._opts.onSwitch(tab.id);
      });

      // Right-click -> context menu
      el.addEventListener('contextmenu', function (e) {
        e.preventDefault();
        if (self._opts.onContextMenu) self._opts.onContextMenu(tab.id, e);
      });

      return el;
    };

    // ========================= Toggle Button =========================

    /**
     * Create or update the sidebar collapse/expand toggle button.
     * Only visible in vertical mode. Inserted at the TOP of the tab bar (first child),
     * matching the pre-migration original design.
     */
    instance._renderToggleBtn = function () {
      if (this._layout !== 'vertical') {
        // Remove toggle button if switching away from vertical
        if (this._toggleBtn && this._toggleBtn.parentNode) {
          this._toggleBtn.parentNode.removeChild(this._toggleBtn);
        }
        this._toggleBtn = null;
        return;
      }

      // Create if not yet existing -- use <button> to match original
      if (!this._toggleBtn) {
        this._toggleBtn = document.createElement('button');
        this._toggleBtn.type = 'button';
        this._toggleBtn.className = 'tab-sidebar-toggle';
        var self = this;
        this._toggleBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          self._collapsed = !self._collapsed;
          self.render();
          if (self._opts.onToggleCollapsed) {
            self._opts.onToggleCollapsed(self._collapsed);
          }
        });
      }

      // Update icon based on collapsed state (textContent, matching original)
      this._toggleBtn.textContent = this._collapsed ? '\u25B6' : '\u25C0'; // ▶ or ◀
      this._toggleBtn.title = this._collapsed
        ? '\u5C55\u5F00\u4FA7\u8FB9\u680F'  // 展开侧边栏
        : '\u538B\u7F29\u4FA7\u8FB9\u680F';  // 压缩侧边栏

      // Insert at the START of the tab bar (matching original _ensureSidebarToggle)
      this._tabBarEl.insertBefore(this._toggleBtn, this._tabBarEl.firstChild);
    };

    // ========================= Close-All Button =========================

    /**
     * Show or hide the close-all floating button based on tab count.
     * Reuses existing button element when possible to avoid DOM churn.
     */
    instance._updateCloseAll = function () {
      var shouldShow = this._tabs.length >= this._closeAllThreshold;

      if (shouldShow) {
        if (!this._closeAllBtn) {
          this._closeAllBtn = document.createElement('div');
          this._closeAllBtn.className = 'unified-close-all-btn';
          this._closeAllBtn.textContent = '\u5173\u95ED\u5168\u90E8'; // 关闭全部
          var self = this;
          this._closeAllBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            if (self._opts.onCloseAll) self._opts.onCloseAll();
          });
        }
        if (!this._closeAllBtn.parentNode) {
          this._tabBarEl.appendChild(this._closeAllBtn);
        }
        this._closeAllBtn.style.display = '';
      } else {
        if (this._closeAllBtn && this._closeAllBtn.parentNode) {
          this._closeAllBtn.parentNode.removeChild(this._closeAllBtn);
        }
        this._closeAllBtn = null;
      }
    };

    // ========================= Tab CRUD =========================

    /**
     * Add a new tab.
     * @param {Object} tabDef
     *   @param {string} tabDef.id - Unique tab ID
     *   @param {string} tabDef.type - 'terminal' | 'file' | string
     *   @param {string} tabDef.icon - HTML string for the icon (e.g., '&#9002;_')
     *   @param {string} tabDef.title - Display title
     *   @param {boolean} tabDef.closable - Show close button (default true)
     *   @param {string} tabDef.status - 'connecting' | 'connected' | 'disconnected' | ''
     *   @param {boolean} tabDef.pinned - Pinned state (Phase 3 stub)
     */
    instance.addTab = function (tabDef) {
      // Prevent duplicate IDs
      for (var i = 0; i < this._tabs.length; i++) {
        if (this._tabs[i].id === tabDef.id) return;
      }
      this._tabs.push({
        id: tabDef.id,
        type: tabDef.type || 'generic',
        icon: tabDef.icon || '',
        title: tabDef.title || '',
        closable: tabDef.closable !== false,
        status: tabDef.status || '',
        pinned: !!tabDef.pinned,
      });
      this.render();
    };

    /**
     * Remove a tab by ID.
     */
    instance.removeTab = function (id) {
      for (var i = 0; i < this._tabs.length; i++) {
        if (this._tabs[i].id === id) {
          this._tabs.splice(i, 1);
          break;
        }
      }
      if (this._activeId === id) {
        this._activeId = null;
      }
      this.render();
    };

    /**
     * Set the active tab. Updates CSS classes in-place for efficiency
     * (avoids full re-render when only the active state changes).
     */
    instance.setActive = function (id) {
      if (this._activeId === id) return;
      this._activeId = id;
      if (!this._tabBarEl) return;

      var tabEls = this._tabBarEl.querySelectorAll('.unified-tab');
      for (var i = 0; i < tabEls.length; i++) {
        var isActive = tabEls[i].getAttribute('data-tab-id') === id;
        tabEls[i].classList.toggle('active', isActive);
      }
    };

    /**
     * Update a tab's status dot.
     * Updates the DOM in-place without full re-render.
     * @param {string} id - Tab ID
     * @param {string} status - 'connecting' | 'connected' | 'disconnected' | ''
     */
    instance.setStatus = function (id, status) {
      for (var i = 0; i < this._tabs.length; i++) {
        if (this._tabs[i].id === id) {
          this._tabs[i].status = status || '';
          break;
        }
      }
      if (!this._tabBarEl) return;

      var el = this._tabBarEl.querySelector('[data-tab-id="' + id + '"]');
      if (!el) return;

      var statusEl = el.querySelector('.unified-tab-status');
      if (status) {
        if (!statusEl) {
          // Create status dot -- insert after icon
          statusEl = document.createElement('span');
          var iconEl = el.querySelector('.unified-tab-icon');
          if (iconEl && iconEl.nextSibling) {
            el.insertBefore(statusEl, iconEl.nextSibling);
          } else {
            el.appendChild(statusEl);
          }
        }
        statusEl.className = 'unified-tab-status ' + status;
      } else if (statusEl) {
        statusEl.parentNode.removeChild(statusEl);
      }
    };

    /**
     * Update a tab's display title.
     * Updates the DOM in-place without full re-render.
     */
    instance.setTitle = function (id, title) {
      for (var i = 0; i < this._tabs.length; i++) {
        if (this._tabs[i].id === id) {
          this._tabs[i].title = title;
          break;
        }
      }
      if (!this._tabBarEl) return;

      var el = this._tabBarEl.querySelector('[data-tab-id="' + id + '"]');
      if (el) {
        var titleEl = el.querySelector('.unified-tab-title');
        if (titleEl) titleEl.textContent = title;
        el.setAttribute('data-tooltip', title);
      }
    };

    /**
     * Update a tab's icon.
     * Updates the DOM in-place without full re-render.
     */
    instance.setIcon = function (id, icon) {
      for (var i = 0; i < this._tabs.length; i++) {
        if (this._tabs[i].id === id) {
          this._tabs[i].icon = icon;
          break;
        }
      }
      if (!this._tabBarEl) return;

      var el = this._tabBarEl.querySelector('[data-tab-id="' + id + '"]');
      if (el) {
        var iconEl = el.querySelector('.unified-tab-icon');
        if (iconEl) iconEl.innerHTML = icon;
      }
    };

    // ========================= Layout =========================

    /**
     * Switch layout mode and collapsed state.
     * @param {string} layout - 'horizontal' | 'vertical'
     * @param {boolean} collapsed - Whether the sidebar is compressed (vertical only)
     */
    instance.setLayout = function (layout, collapsed) {
      this._layout = layout || 'horizontal';
      this._collapsed = !!collapsed;
      this.render();
    };

    /**
     * Set the collapsed state independently (vertical mode only).
     * @param {boolean} collapsed
     */
    instance.setCollapsed = function (collapsed) {
      this._collapsed = !!collapsed;
      this.render();
    };

    // ========================= Getters =========================

    /**
     * Get the active tab ID.
     * @returns {string|null}
     */
    instance.getActive = function () {
      return this._activeId;
    };

    /**
     * Get all tab definitions (shallow copy).
     * @returns {Array}
     */
    instance.getAll = function () {
      return this._tabs.slice();
    };

    // ========================= Cleanup =========================

    /**
     * Destroy this TabBar instance. Removes all DOM elements and clears references.
     */
    instance.dispose = function () {
      if (this._toggleBtn && this._toggleBtn.parentNode) {
        this._toggleBtn.parentNode.removeChild(this._toggleBtn);
      }
      if (this._closeAllBtn && this._closeAllBtn.parentNode) {
        this._closeAllBtn.parentNode.removeChild(this._closeAllBtn);
      }
      if (this._tabBarEl) {
        this._tabBarEl.innerHTML = '';
      }
      this._tabs = [];
      this._activeId = null;
      this._toggleBtn = null;
      this._closeAllBtn = null;
    };

    // ========================= Initial Render =========================

    instance.render();

    return instance;
  }

  return { create: create };
})();
