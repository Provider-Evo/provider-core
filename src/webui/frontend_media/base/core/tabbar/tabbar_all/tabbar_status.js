/**
 * TabBar status dot methods. Depends on tabbar_core.js.
 */
'use strict';

function _buildSplitStatusSlot(tab, pane, statusClass) {
  var slot = document.createElement('span');
  slot.className = 'unified-tab-status-slot';
  slot.setAttribute('data-pane', pane);

  var dot = document.createElement('span');
  dot.className = 'unified-tab-status unified-tab-status-split-' + (pane === 'primary' ? 'a' : 'b');
  if (statusClass) dot.className += ' ' + statusClass;
  slot.appendChild(dot);

  var closeEl = document.createElement('span');
  closeEl.className = 'unified-tab-status-close';
  closeEl.innerHTML = '&times;';
  slot.appendChild(closeEl);

  return slot;
}

/**
 * Build the status area for a tab: a single dot normally, or two independently
 * interactive slots when the tab has a split pane.
 */
function _buildTabStatusNode(tab) {
  if (tab.splitStatus !== undefined && tab.splitStatus !== null) {
    var group = document.createElement('span');
    group.className = 'unified-tab-status-group';
    group.appendChild(_buildSplitStatusSlot(tab, 'primary', tab.status || ''));
    group.appendChild(_buildSplitStatusSlot(tab, 'split', tab.splitStatus || ''));
    return group;
  }
  if (tab.status) {
    var statusEl = document.createElement('span');
    statusEl.className = 'unified-tab-status ' + tab.status;
    return statusEl;
  }
  return null;
}

function _syncSplitTabClass(el, tab) {
  var hasSplit = tab.splitStatus !== undefined && tab.splitStatus !== null;
  el.classList.toggle('has-split-status', hasSplit);
}

function _bindSplitStatusSlotEvents(instance, el, tab, slot) {
  var pane = slot.getAttribute('data-pane');
  if (!pane) return;

  slot.addEventListener('click', function (e) {
    e.stopPropagation();
    if (e.target.closest('.unified-tab-status-close')) return;
    if (instance._opts.onSplitPaneSelect) {
      instance._opts.onSplitPaneSelect(tab.id, pane);
    }
  });

  var closeEl = slot.querySelector('.unified-tab-status-close');
  if (!closeEl) return;
  closeEl.addEventListener('click', function (e) {
    e.stopPropagation();
    if (instance._opts.onPaneClose) {
      instance._opts.onPaneClose(tab.id, pane);
    }
  });
}

function _bindTabStatusEvents(instance, el, tab) {
  var slots = el.querySelectorAll('.unified-tab-status-slot');
  for (var i = 0; i < slots.length; i++) {
    _bindSplitStatusSlotEvents(instance, el, tab, slots[i]);
  }
}

/**
 * Refresh the status area for an already-rendered tab element in place,
 * replacing whatever status node exists (single dot or split group).
 */
function _refreshTabStatusNode(instance, el, tab) {
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
  _syncSplitTabClass(el, tab);
  if (node && node.classList.contains('unified-tab-status-group')) {
    _bindTabStatusEvents(instance, el, tab);
    _syncActivePaneDots(el, tab.activePane || 'primary');
  }
}

function _syncActivePaneDots(el, pane) {
  var slots = el.querySelectorAll('.unified-tab-status-slot');
  for (var i = 0; i < slots.length; i++) {
    var isActive = slots[i].getAttribute('data-pane') === pane;
    slots[i].classList.toggle('is-pane-active', isActive);
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
  instance._refreshStatusNode = function (el, tab) {
    _refreshTabStatusNode(this, el, tab);
  };
  instance._bindTabStatusEvents = function (el, tab) {
    _bindTabStatusEvents(this, el, tab);
  };
  instance._syncSplitTabClass = _syncSplitTabClass;
  instance._syncActivePaneDots = _syncActivePaneDots;
}
