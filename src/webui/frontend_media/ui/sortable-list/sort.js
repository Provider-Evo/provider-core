/**
 * SortableList — reorderable list with up/down/remove controls.
 *
 * Usage:
 *   var list = new SortableList(container, {
 *     items: ['a', 'b', 'c'],
 *     renderItem: function(value, index) { return '<input value="' + value + '">'; },
 *     getItemValue: function(el, index) { return el.querySelector('input').value; },
 *     onChange: function(items) { ... },
 *     placeholder: 'No items',
 *   });
 *   list.setItems(['x', 'y']);
 *   list.getItems(); // ['x', 'y']
 */
function _slT(key) {
  return (typeof t === 'function') ? t(key) : key;
}

function _slBuildItemHtml(self, value, index) {
  var isFirst = (index === 0);
  var isLast = (index === self._items.length - 1);
  var html = '<div class="sl-item" data-index="' + index + '" draggable="true">';
  html += '<div class="sl-drag-handle" title="' + _slT('sortable.dragHandle') + '">&#x2630;</div>';
  html += '<div class="sl-controls">';
  html += '<button type="button" class="sl-btn sl-up' + (isFirst ? ' sl-disabled' : '') + '" data-action="up" data-index="' + index + '" title="' + _slT('sortable.moveUp') + '"' + (isFirst ? ' disabled' : '') + '>&#9650;</button>';
  html += '<button type="button" class="sl-btn sl-down' + (isLast ? ' sl-disabled' : '') + '" data-action="down" data-index="' + index + '" title="' + _slT('sortable.moveDown') + '"' + (isLast ? ' disabled' : '') + '>&#9660;</button>';
  html += '</div>';
  html += '<div class="sl-content">' + self._renderItem(value, index) + '</div>';
  html += '<button type="button" class="sl-btn sl-remove" data-action="remove" data-index="' + index + '" title="' + _slT('sortable.remove') + '">&times;</button>';
  html += '</div>';
  return html;
}

function _slBindClickDelegation(self, list) {
  list.onclick = function(e) {
    var btn = e.target.closest('[data-action]');
    if (!btn) return;
    e.preventDefault();
    e.stopPropagation();
    var action = btn.dataset.action;
    var idx = parseInt(btn.dataset.index);
    if (action === 'up' && idx > 0) {
      self._swap(idx, idx - 1);
    } else if (action === 'down' && idx < self._items.length - 1) {
      self._swap(idx, idx + 1);
    } else if (action === 'remove') {
      self._items.splice(idx, 1);
      self._render();
      self._fireChange();
    }
  };
}

function _slBindDragEvents(self, list) {
  var dragState = { srcIndex: null };

  list.addEventListener('dragstart', function(e) { _slOnDragStart(e, dragState, list); });
  list.addEventListener('dragover', function(e) { _slOnDragOver(e, list); });
  list.addEventListener('dragleave', function(e) { _slOnDragLeave(e); });
  list.addEventListener('drop', function(e) { _slOnDrop(e, self, list, dragState); });
  list.addEventListener('dragend', function(e) { _slOnDragEnd(e, list, dragState); });
}

function _slOnDragStart(e, dragState, list) {
  var item = e.target.closest('.sl-item');
  if (!item) return;
  dragState.srcIndex = parseInt(item.dataset.index);
  item.classList.add('sl-dragging');
  e.dataTransfer.effectAllowed = 'move';
  e.dataTransfer.setData('text/plain', String(dragState.srcIndex));
}

function _slOnDragOver(e, list) {
  e.preventDefault();
  e.dataTransfer.dropEffect = 'move';
  var item = e.target.closest('.sl-item');
  if (!item) return;
  // Remove all drag-over classes first
  var allItems = list.querySelectorAll('.sl-item');
  for (var k = 0; k < allItems.length; k++) {
    allItems[k].classList.remove('sl-drag-over-top', 'sl-drag-over-bottom');
  }
  // Determine if mouse is in top or bottom half of the target
  var rect = item.getBoundingClientRect();
  var midY = rect.top + rect.height / 2;
  if (e.clientY < midY) {
    item.classList.add('sl-drag-over-top');
  } else {
    item.classList.add('sl-drag-over-bottom');
  }
}

function _slOnDragLeave(e) {
  var item = e.target.closest('.sl-item');
  if (item) {
    item.classList.remove('sl-drag-over-top', 'sl-drag-over-bottom');
  }
}

function _slOnDrop(e, self, list, dragState) {
  e.preventDefault();
  e.stopPropagation();
  var item = e.target.closest('.sl-item');
  if (!item || dragState.srcIndex === null) return;
  var targetIndex = parseInt(item.dataset.index);
  var rect = item.getBoundingClientRect();
  var midY = rect.top + rect.height / 2;
  // Determine insertion position
  var insertIndex = e.clientY < midY ? targetIndex : targetIndex + 1;
  // Adjust if dragging downward (source item shifts target indices)
  if (dragState.srcIndex < insertIndex) insertIndex--;
  if (dragState.srcIndex !== insertIndex) {
    // Remove item from source and insert at new position
    var movedItem = self._items.splice(dragState.srcIndex, 1)[0];
    self._items.splice(insertIndex, 0, movedItem);
    self._render();
    self._fireChange();
  }
  _slClearDragClasses(list);
  dragState.srcIndex = null;
}

function _slOnDragEnd(e, list, dragState) {
  _slClearDragClasses(list);
  dragState.srcIndex = null;
}

function _slClearDragClasses(list) {
  var allItems = list.querySelectorAll('.sl-item');
  for (var k = 0; k < allItems.length; k++) {
    allItems[k].classList.remove('sl-drag-over-top', 'sl-drag-over-bottom', 'sl-dragging');
  }
}

(function(global) {
  'use strict';

  var _registry = [];

  function SortableList(container, opts) {
    if (typeof container === 'string') container = document.querySelector(container);
    if (!container) throw new Error('SortableList: container not found');
    this._container = container;
    this._opts = opts || {};
    this._items = (opts && opts.items) ? opts.items.slice() : [];
    this._renderItem = (opts && opts.renderItem) || function(v) { return '<span>' + String(v) + '</span>'; };
    this._getItemValue = (opts && opts.getItemValue) || null;
    this._onChange = (opts && opts.onChange) || null;
    this._customPlaceholder = (opts && opts.placeholder) || null;
    this._placeholder = this._customPlaceholder || _slT('sortable.empty');
    this._render();
    _registry.push(this);
  }

  _attachSortableListMethods(SortableList);

  if (typeof i18n !== 'undefined' && i18n.onLanguageChanged) {
    i18n.onLanguageChanged(function() {
      for (var i = 0; i < _registry.length; i++) {
        _registry[i]._onLocaleChange();
      }
    });
  }

  global.SortableList = SortableList;
})(typeof window !== 'undefined' ? window : this);
