/**
 * TabBar status dot methods. Depends on tabbar_core.js.
 */
'use strict';

/**
 * Build the status area for a tab: a single dot normally, or a paired
 * group of two dots when the tab has a split pane (tab.splitStatus is
 * set, even to ''). The group's layout (row vs column) follows the
 * current tabbar layout so it always reads as one visual unit, and the
 * whole group is treated as a single clickable/hoverable region -- it
 * has no listeners of its own, so clicks/hovers fall through to the
 * tab element exactly like a single dot would.
 */
function _buildTabStatusNode(tab) {
  if (tab.splitStatus !== undefined && tab.splitStatus !== null) {
    var group = document.createElement('span');
    group.className = 'unified-tab-status-group';
    var primary = document.createElement('span');
    primary.className = 'unified-tab-status unified-tab-status-split-a' + (tab.status ? ' ' + tab.status : '');
    var secondary = document.createElement('span');
    secondary.className = 'unified-tab-status unified-tab-status-split-b' + (tab.splitStatus ? ' ' + tab.splitStatus : '');
    group.appendChild(primary);
    group.appendChild(secondary);
    return group;
  }
  if (tab.status) {
    var statusEl = document.createElement('span');
    statusEl.className = 'unified-tab-status ' + tab.status;
    return statusEl;
  }
  return null;
}

/**
 * Refresh the status area for an already-rendered tab element in place,
 * replacing whatever status node exists (single dot or split group).
 */
function _refreshTabStatusNode(el, tab) {
  var existing = el.querySelector('.unified-tab-status-group, .unified-tab-status');
  var node = _buildTabStatusNode(tab);
  if (existing) {
    if (node) {
      existing.parentNode.replaceChild(node, existing);
    } else {
      existing.parentNode.removeChild(existing);
    }
  } else if (node) {
    var iconEl = el.querySelector('.unified-tab-icon');
    var titleEl = el.querySelector('.unified-tab-title');
    if (iconEl) {
      el.insertBefore(node, iconEl);
    } else if (titleEl) {
      el.insertBefore(node, titleEl);
    } else {
      el.insertBefore(node, el.firstChild);
    }
  }
}

function _attachStatusMethods(instance) {
  /**
   * Safely find a tab element by ID, escaping CSS selector special chars.
   */
  instance._findTabEl = function (id) {
    if (!this._tabBarEl) return null;
    var safeId = String(id).replace(/["\\]/g, '\\$&');
    return this._tabBarEl.querySelector('[data-tab-id="' + safeId + '"]');
  };

  instance._buildStatusNode = _buildTabStatusNode;
  instance._refreshStatusNode = _refreshTabStatusNode;
}
