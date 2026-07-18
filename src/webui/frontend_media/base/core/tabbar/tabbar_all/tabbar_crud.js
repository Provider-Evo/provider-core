/**
 * TabBar CRUD methods (add/remove tabs, per-tab setters). Depends on
 * tabbar_core.js / tabbar_status.js / tabbar_render.js.
 */
'use strict';

function _attachTabCrudMethods(instance) {
  _attachTabAdd(instance);
  _attachTabRemove(instance);
  _attachTabActive(instance);
  _attachTabStatusMethods(instance);
  _attachTabSplitStatusMethods(instance);
  _attachTabTitleColorMethods(instance);
  _attachTabMoveIconMethods(instance);
}

function _attachTabAdd(instance) {
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
}

function _attachTabRemove(instance) {
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
    delete this._thumbnails[id];
    this._hidePreview();
    this.render();
  };
}

function _attachTabActive(instance) {
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
}

function _attachTabStatusMethods(instance) {
  /**
   * Update a tab's status dot.
   * Updates the DOM in-place without full re-render.
   * @param {string} id - Tab ID
   * @param {string} status - 'connecting' | 'connected' | 'disconnected' | ''
   */
  instance.setStatus = function (id, status) {
    var tab = null;
    for (var i = 0; i < this._tabs.length; i++) {
      if (this._tabs[i].id === id) {
        this._tabs[i].status = status || '';
        tab = this._tabs[i];
        break;
      }
    }
    if (!this._tabBarEl || !tab) return;

    var el = this._findTabEl(id);
    if (!el) return;

    this._refreshStatusNode(el, tab);
    this._syncTabIconEl(el, tab);
  };
}

function _attachTabSplitStatusMethods(instance) {
  /**
   * Set (or clear) the secondary status dot for a tab's split pane.
   * Passing a non-null/undefined value (including '') switches the tab
   * into paired-dot rendering; passing null/undefined reverts it to a
   * single dot. Updates the DOM in-place without full re-render.
   * @param {string} id - Tab ID
   * @param {string|null} splitStatus - 'connecting' | 'connected' | 'disconnected' | '' | null
   */
  instance.setSplitStatus = function (id, splitStatus) {
    var tab = null;
    for (var i = 0; i < this._tabs.length; i++) {
      if (this._tabs[i].id === id) {
        tab = this._tabs[i];
        break;
      }
    }
    if (!tab) return;
    tab.splitStatus = (splitStatus === null || splitStatus === undefined) ? null : (splitStatus || '');
    if (!this._tabBarEl) return;

    var el = this._findTabEl(id);
    if (!el) return;

    this._refreshStatusNode(el, tab);
    this._syncTabIconEl(el, tab);
  };
}

function _attachTabTitleColorMethods(instance) {
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

    var el = this._findTabEl(id);
    if (el) {
      var titleEl = el.querySelector('.unified-tab-title');
      if (titleEl) titleEl.textContent = title;
      el.setAttribute('data-tooltip', title);
    }
  };

  /**
   * Set (or clear) a tab's color indicator.
   * Applies the color as a CSS custom property consumed by tabbar.css
   * for a left-edge accent bar; passing a falsy color clears it.
   */
  instance.setColor = function (id, color) {
    for (var i = 0; i < this._tabs.length; i++) {
      if (this._tabs[i].id === id) {
        this._tabs[i].color = color || '';
        break;
      }
    }
    var el = this._findTabEl(id);
    if (!el) return;
    if (color) {
      el.style.setProperty('--tab-color', color);
      el.classList.add('has-tab-color');
    } else {
      el.style.removeProperty('--tab-color');
      el.classList.remove('has-tab-color');
    }
  };
}

function _attachTabMoveIconMethods(instance) {
  /**
   * Move a tab to a new index within the tab order and re-render.
   * Used by "move left" / "move right" context menu actions.
   */
  instance.moveTab = function (id, newIndex) {
    var oldIndex = -1;
    for (var i = 0; i < this._tabs.length; i++) {
      if (this._tabs[i].id === id) { oldIndex = i; break; }
    }
    if (oldIndex === -1) return;
    if (newIndex < 0 || newIndex >= this._tabs.length) return;
    var tab = this._tabs.splice(oldIndex, 1)[0];
    this._tabs.splice(newIndex, 0, tab);
    this.render();
  };

  /**
   * Update a tab's icon.
   * Updates the DOM in-place without full re-render.
   */
  instance.setIcon = function (id, icon) {
    var tab = null;
    for (var i = 0; i < this._tabs.length; i++) {
      if (this._tabs[i].id === id) {
        this._tabs[i].icon = icon || '';
        tab = this._tabs[i];
        break;
      }
    }
    if (!this._tabBarEl || !tab) return;

    var el = this._findTabEl(id);
    if (!el) return;

    this._syncTabIconEl(el, tab);
  };
}
