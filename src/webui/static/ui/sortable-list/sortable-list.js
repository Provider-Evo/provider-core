/**
 * SortableList — 可排序列表组件（带上下箭头 + 删除按钮）
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
(function(global) {
  'use strict';

  function SortableList(container, opts) {
    if (typeof container === 'string') container = document.querySelector(container);
    if (!container) throw new Error('SortableList: container not found');
    this._container = container;
    this._opts = opts || {};
    this._items = (opts && opts.items) ? opts.items.slice() : [];
    this._renderItem = (opts && opts.renderItem) || function(v) { return '<span>' + String(v) + '</span>'; };
    this._getItemValue = (opts && opts.getItemValue) || null;
    this._onChange = (opts && opts.onChange) || null;
    this._placeholder = (opts && opts.placeholder) || 'No items';
    this._render();
  }

  SortableList.prototype.setItems = function(items) {
    this._items = items.slice();
    this._render();
  };

  SortableList.prototype.getItems = function() {
    if (this._getItemValue) {
      var els = this._container.querySelectorAll('.sl-item');
      var result = [];
      for (var i = 0; i < els.length; i++) {
        var val = this._getItemValue(els[i], i);
        if (val !== null && val !== undefined) result.push(val);
      }
      return result;
    }
    return this._items.slice();
  };

  SortableList.prototype._render = function() {
    var self = this;
    var list = this._container;
    if (!this._items.length) {
      list.innerHTML = '<div class="sl-empty">' + this._placeholder + '</div>';
      return;
    }
    var html = '';
    for (var i = 0; i < this._items.length; i++) {
      var isFirst = (i === 0);
      var isLast = (i === this._items.length - 1);
      html += '<div class="sl-item" data-index="' + i + '" draggable="true">';
      html += '<div class="sl-drag-handle" title="Drag to reorder">&#x2630;</div>';
      html += '<div class="sl-controls">';
      html += '<button type="button" class="sl-btn sl-up' + (isFirst ? ' sl-disabled' : '') + '" data-action="up" data-index="' + i + '" title="上移"' + (isFirst ? ' disabled' : '') + '>&#9650;</button>';
      html += '<button type="button" class="sl-btn sl-down' + (isLast ? ' sl-disabled' : '') + '" data-action="down" data-index="' + i + '" title="下移"' + (isLast ? ' disabled' : '') + '>&#9660;</button>';
      html += '</div>';
      html += '<div class="sl-content">' + this._renderItem(this._items[i], i) + '</div>';
      html += '<button type="button" class="sl-btn sl-remove" data-action="remove" data-index="' + i + '" title="删除">&times;</button>';
      html += '</div>';
    }
    list.innerHTML = html;

    // Bind click events via delegation
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

    // Bind drag-and-drop events
    var dragSrcIndex = null;

    list.addEventListener('dragstart', function(e) {
      var item = e.target.closest('.sl-item');
      if (!item) return;
      dragSrcIndex = parseInt(item.dataset.index);
      item.classList.add('sl-dragging');
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', String(dragSrcIndex));
    });

    list.addEventListener('dragover', function(e) {
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
    });

    list.addEventListener('dragleave', function(e) {
      var item = e.target.closest('.sl-item');
      if (item) {
        item.classList.remove('sl-drag-over-top', 'sl-drag-over-bottom');
      }
    });

    list.addEventListener('drop', function(e) {
      e.preventDefault();
      e.stopPropagation();
      var item = e.target.closest('.sl-item');
      if (!item || dragSrcIndex === null) return;
      var targetIndex = parseInt(item.dataset.index);
      var rect = item.getBoundingClientRect();
      var midY = rect.top + rect.height / 2;
      // Determine insertion position
      var insertIndex = e.clientY < midY ? targetIndex : targetIndex + 1;
      // Adjust if dragging downward (source item shifts target indices)
      if (dragSrcIndex < insertIndex) insertIndex--;
      if (dragSrcIndex !== insertIndex) {
        // Remove item from source and insert at new position
        var movedItem = self._items.splice(dragSrcIndex, 1)[0];
        self._items.splice(insertIndex, 0, movedItem);
        self._render();
        self._fireChange();
      }
      // Clean up
      var allItems = list.querySelectorAll('.sl-item');
      for (var k = 0; k < allItems.length; k++) {
        allItems[k].classList.remove('sl-drag-over-top', 'sl-drag-over-bottom', 'sl-dragging');
      }
      dragSrcIndex = null;
    });

    list.addEventListener('dragend', function(e) {
      var allItems = list.querySelectorAll('.sl-item');
      for (var k = 0; k < allItems.length; k++) {
        allItems[k].classList.remove('sl-drag-over-top', 'sl-drag-over-bottom', 'sl-dragging');
      }
      dragSrcIndex = null;
    });
  };

  SortableList.prototype._swap = function(a, b) {
    var tmp = this._items[a];
    this._items[a] = this._items[b];
    this._items[b] = tmp;
    this._render();
    this._fireChange();
  };

  SortableList.prototype._fireChange = function() {
    if (this._onChange) this._onChange(this.getItems());
  };

  global.SortableList = SortableList;
})(typeof window !== 'undefined' ? window : this);
