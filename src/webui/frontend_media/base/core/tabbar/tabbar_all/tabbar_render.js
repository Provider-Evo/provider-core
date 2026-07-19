/**
 * TabBar full render, tab element creation, toggle button, and close-all
 * button logic. Depends on tabbar_core.js / tabbar_status.js / tabbar_preview.js.
 */
'use strict';

function _attachRenderMethods(instance) {
  _attachRenderCoreMethods(instance);
  _attachTabElementMethods(instance);
  _attachToggleAndCloseAllMethods(instance);
}

/**
 * Attach the top-level render() plus its small structural helpers
 * (toggle detach, layout classes, add button, empty message).
 * Split out of _attachRenderMethods to keep it under the line cap.
 */
function _attachRenderCoreMethods(instance) {
  _attachRenderCoreSubMainMethods(instance);
  _attachRenderCoreSubHelperMethods(instance);
}

/**
 * Attach render() and its toggle-button detach helper.
 * Split out of _attachRenderCoreMethods to keep it under the line cap.
 */
function _attachRenderCoreSubMainMethods(instance) {
  /**
   * Full re-render of the tab bar.
   * Detaches persistent elements (toggle button) before clearing innerHTML,
   * then reattaches them after.
   */
  instance.render = function () {
    if (!this._tabBarEl) return;

    var toggleBtn = this._detachToggleBtn();

    this._tabBarEl.innerHTML = '';
    this._applyLayoutClasses();

    for (var i = 0; i < this._tabs.length; i++) {
      this._tabBarEl.appendChild(this._createTabElement(this._tabs[i]));
    }

    this._renderAddButton();
    this._renderEmptyMessage();

    // Re-attach or create toggle button (vertical mode only)
    if (toggleBtn) {
      this._toggleBtn = toggleBtn;
    }
    this._renderToggleBtn();

    // Update close-all button visibility
    this._updateCloseAll();
  };

  /**
   * Detach the persistent toggle button before an innerHTML clear so it
   * survives the full re-render. Split out of render() to keep it under
   * the line cap.
   */
  instance._detachToggleBtn = function () {
    var toggleBtn = this._toggleBtn;
    if (toggleBtn && toggleBtn.parentNode) {
      toggleBtn.parentNode.removeChild(toggleBtn);
    }
    return toggleBtn;
  };
}

/**
 * Attach the layout-class, add-button, and empty-message render helpers.
 * Split out of _attachRenderCoreMethods to keep it under the line cap.
 */
function _attachRenderCoreSubHelperMethods(instance) {
  /**
   * Apply layout classes to the tab bar element and its container.
   * Split out of render() to keep it under the line cap.
   */
  instance._applyLayoutClasses = function () {
    this._tabBarEl.className = 'unified-tabbar ' + this._layout;
    if (this._layout === 'vertical' && this._collapsed) {
      this._tabBarEl.className += ' collapsed tabbar-compressed';
    }

    // Apply layout classes to the container (for flex-direction control in CSS)
    if (this._container) {
      this._container.classList.toggle('tabbar-horizontal', this._layout === 'horizontal');
      this._container.classList.toggle('tabbar-vertical', this._layout === 'vertical');
    }
  };

  /**
   * Render the "+" add-tab button. Split out of render() to keep it under
   * the line cap.
   */
  instance._renderAddButton = function () {
    var addBtn = document.createElement('div');
    addBtn.className = 'unified-tabbar-add';
    addBtn.textContent = '+';
    addBtn.title = t('tabbar.addTab');
    var self = this;
    addBtn.addEventListener('click', function (e) {
      e.stopPropagation();
      if (self._opts.onAdd) self._opts.onAdd(e);
    });
    this._tabBarEl.appendChild(addBtn);
  };

  /**
   * Show the empty-state message when no tabs exist. Split out of render()
   * to keep it under the line cap.
   */
  instance._renderEmptyMessage = function () {
    if (this._tabs.length === 0 && this._opts.emptyMessage) {
      var emptyEl = document.createElement('div');
      emptyEl.className = 'unified-tabbar-empty';
      emptyEl.textContent = this._opts.emptyMessage;
      this._tabBarEl.appendChild(emptyEl);
    }
  };

}

/**
 * Attach tab-element creation/sync helpers: event binding, DOM building,
 * and icon-slot syncing. Split out of _attachRenderMethods to keep it
 * under the line cap.
 */
function _attachTabElementMethods(instance) {
  _attachTabElementEventMethods(instance);
  _attachTabElementDomMethods(instance);
  _attachTabElementIconSyncMethods(instance);
}

/**
 * Attach the click/context-menu/hover-preview event binding helper.
 * Split out of _attachTabElementMethods to keep it under the line cap.
 */
function _attachTabElementEventMethods(instance) {
  /**
   * Attach click/context-menu/hover-preview listeners for a tab element.
   * Split out of _createTabElement to keep that function under the line cap.
   */
  instance._bindTabElementEvents = function (el, tab) {
    var self = this;

    // Close button (only if tab is closable)
    if (tab.closable !== false) {
      var closeEl = document.createElement('span');
      closeEl.className = 'unified-tab-close';
      closeEl.innerHTML = '&times;';
      closeEl.addEventListener('click', function (e) {
        e.stopPropagation();
        self._hidePreview();
        if (self._opts.onClose) self._opts.onClose(tab.id);
      });
      el.appendChild(closeEl);
    }

    // Tab click -> switch (left-click only); status slots handle their own clicks.
    el.addEventListener('click', function (e) {
      if (e.button !== 0) return;
      if (e.target.closest('.unified-tab-status-slot')) return;
      if (self._opts.onSwitch) self._opts.onSwitch(tab.id);
    });

    // Right-click -> context menu
    el.addEventListener('contextmenu', function (e) {
      e.preventDefault();
      if (self._opts.onContextMenu) self._opts.onContextMenu(tab.id, e);
    });

    // Preview tooltip on hover (compressed mode, non-active tabs)
    el.addEventListener('mouseenter', function (e) {
      if (self._collapsed && tab.id !== self._activeId) {
        if (self._opts.onPreviewRequest) self._opts.onPreviewRequest(tab.id);
        self._showPreview(tab, e.clientX, e.clientY);
      }
    });
    el.addEventListener('mousemove', function (e) {
      if (self._collapsed && tab.id !== self._activeId) {
        self._movePreview(e.clientX, e.clientY);
      }
    });
    el.addEventListener('mouseleave', function () {
      self._hidePreview();
    });
  };
}

/**
 * Attach the tab element creation and icon-sync DOM helpers.
 * Split out of _attachTabElementMethods to keep it under the line cap.
 */
function _attachTabElementDomMethods(instance) {
  /**
   * Create a DOM element for a single tab.
   * Structure: icon + status + title + close
   */
  instance._createTabElement = function (tab) {
    var el = document.createElement('div');
    el.className = 'unified-tab' + (tab.id === this._activeId ? ' active' : '');
    el.setAttribute('data-tab-id', tab.id);
    el.setAttribute('data-tooltip', tab.title || '');

    // Status area -- either a single dot (status) or, for split tabs, a
    // paired group of two dots (status + splitStatus) that acts as one
    // unit since it carries no click handler of its own and bubbles up
    // to the tab's own click/switch behavior.
    var statusNode = this._buildStatusNode(tab);
    if (statusNode) el.appendChild(statusNode);
    this._syncSplitTabClass(el, tab);
    if (statusNode && statusNode.classList.contains('unified-tab-status-group')) {
      this._bindTabStatusEvents(el, tab);
      this._syncActivePaneDots(el, tab.activePane || 'primary');
    }

    // Icon slot -- skip when status dot is present and icon is empty
    if ((tab.status || tab.splitStatus) && !tab.icon) {
      // no icon element needed
    } else {
      var iconEl = document.createElement('span');
      iconEl.className = 'unified-tab-icon';
      // icon is trusted HTML from calling code (terminal/file modules), not user input
      iconEl.innerHTML = tab.icon || '';
      el.appendChild(iconEl);
    }

    // Title text
    var titleEl = document.createElement('span');
    titleEl.className = 'unified-tab-title';
    titleEl.textContent = tab.title || '';
    el.appendChild(titleEl);

    this._bindTabElementEvents(el, tab);

    return el;
  };
}

/**
 * Attach the icon-slot sync helper used to keep tab DOM in sync with the
 * tab model without a full re-render. Split out of _attachTabElementMethods
 * to keep it under the line cap.
 */
function _attachTabElementIconSyncMethods(instance) {
  /**
   * Keep the icon slot in sync with tab model (matches _createTabElement).
   * When status is set and icon is empty, remove the icon element so the
   * status dot sits next to the title without a hidden 18px gap.
   */
  instance._syncTabIconEl = function (el, tab) {
    var iconEl = el.querySelector('.unified-tab-icon');
    var statusNode = el.querySelector('.unified-tab-status-group, .unified-tab-status');
    var titleEl = el.querySelector('.unified-tab-title');
    var hasStatus = tab.status || (tab.splitStatus !== undefined && tab.splitStatus !== null);

    if (hasStatus && !tab.icon) {
      if (iconEl && iconEl.parentNode) {
        iconEl.parentNode.removeChild(iconEl);
      }
      return;
    }

    if (!iconEl) {
      iconEl = document.createElement('span');
      iconEl.className = 'unified-tab-icon';
      if (statusNode) {
        if (statusNode.nextSibling) {
          el.insertBefore(iconEl, statusNode.nextSibling);
        } else if (titleEl) {
          el.insertBefore(iconEl, titleEl);
        } else {
          el.appendChild(iconEl);
        }
      } else if (titleEl) {
        el.insertBefore(iconEl, titleEl);
      } else {
        el.appendChild(iconEl);
      }
    }
    iconEl.innerHTML = tab.icon || '';
  };
}

/**
 * Attach the sidebar toggle button and close-all button lifecycle methods.
 * Split out of _attachRenderMethods to keep it under the line cap.
 */
function _attachToggleAndCloseAllMethods(instance) {
  _attachToggleBtnMethods(instance);
  _attachCloseAllBtnMethods(instance);
}

/**
 * Attach the sidebar collapse/expand toggle button lifecycle method.
 * Split out of _attachToggleAndCloseAllMethods to keep it under the line cap.
 */
function _attachToggleBtnMethods(instance) {
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
    this._toggleBtn.textContent = this._collapsed ? '▶' : '◀'; // ▶ or ◀
    this._toggleBtn.title = this._collapsed
      ? t('tabbar.expandSidebar')
      : t('tabbar.compressSidebar');

    // Insert at the START of the tab bar (matching original _ensureSidebarToggle)
    this._tabBarEl.insertBefore(this._toggleBtn, this._tabBarEl.firstChild);
  };
}

/**
 * Attach the close-all floating button lifecycle method.
 * Split out of _attachToggleAndCloseAllMethods to keep it under the line cap.
 */
function _ensureCloseAllBtn(instance) {
  if (instance._closeAllBtn) return;
  instance._closeAllBtn = document.createElement('div');
  instance._closeAllBtn.className = 'unified-close-all-btn';
  instance._closeAllBtn.textContent = t('tabbar.closeAllShort');
  var self = instance;
  instance._closeAllBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    if (self._opts.onCloseAll) self._opts.onCloseAll();
  });
}

function _attachCloseAllBtnMethods(instance) {
  /**
   * Show or hide the close-all floating button based on tab count.
   * Reuses existing button element when possible to avoid DOM churn.
   */
  instance._updateCloseAll = function () {
    var shouldShow = this._tabs.length >= this._closeAllThreshold;

    if (!shouldShow) {
      if (this._closeAllBtn && this._closeAllBtn.parentNode) {
        this._closeAllBtn.parentNode.removeChild(this._closeAllBtn);
      }
      this._closeAllBtn = null;
      return;
    }
    _ensureCloseAllBtn(this);
    if (!this._closeAllBtn.parentNode) {
      this._tabBarEl.appendChild(this._closeAllBtn);
    }
    this._closeAllBtn.style.display = '';
  };
}
