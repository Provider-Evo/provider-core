/**
 * TabBar layout switching, getters, and dispose. Depends on tabbar_core.js /
 * tabbar_preview.js.
 */
'use strict';

function _removeTabBarButtons(instance) {
  if (instance._toggleBtn && instance._toggleBtn.parentNode) {
    instance._toggleBtn.parentNode.removeChild(instance._toggleBtn);
  }
  if (instance._closeAllBtn && instance._closeAllBtn.parentNode) {
    instance._closeAllBtn.parentNode.removeChild(instance._closeAllBtn);
  }
}

function _attachLayoutGetters(instance) {
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

  _attachLayoutSettersAndDispose(instance);
}

function _attachLayoutSettersAndDispose(instance) {
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

  /**
   * Destroy this TabBar instance. Removes all DOM elements and clears references.
   */
  instance.dispose = function () {
    _removeTabBarButtons(this);
    this._disposePreview();
    if (this._tabBarEl) {
      this._tabBarEl.innerHTML = '';
    }
    this._tabs = [];
    this._activeId = null;
    this._toggleBtn = null;
    this._closeAllBtn = null;
    this._thumbnails = {};
  };
}

/**
 * 共享折叠传播逻辑：更新 _tabLayoutConfig、同步所有 TabBar 折叠状态、持久化。
 * terminal 和 files 的 onToggleCollapsed 回调均调用此函数以消除重复代码。
 * @param {object|null} sourceBar - 触发折叠的 TabBar 实例（跳过自身同步）
 * @param {boolean} collapsed
 */
function propagateTabBarCollapsed(sourceBar, collapsed) {
  if (typeof _tabLayoutConfig !== 'undefined') {
    _tabLayoutConfig.sidebarCompressed = collapsed;
  }
  var bars = window._tabBars || {};
  var keys = Object.keys(bars);
  for (var i = 0; i < keys.length; i++) {
    if (bars[keys[i]] !== sourceBar && bars[keys[i]] && typeof bars[keys[i]].setCollapsed === 'function') {
      bars[keys[i]].setCollapsed(collapsed);
    }
  }
  if (typeof _persistTabLayoutPatch === 'function') {
    _persistTabLayoutPatch({ sidebarCompressed: collapsed });
  }
}
