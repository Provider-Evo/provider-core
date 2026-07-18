/**
 * SortableList prototype method builders -- split out of sort.js to keep
 * the registering IIFE under the line cap. Attaches methods onto the
 * SortableList prototype via _attachSortableListMethods(SortableList).
 */
function _attachSortableListMethodsSubData(SortableList) {
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

  SortableList.prototype._onLocaleChange = function() {
    if (!this._customPlaceholder) {
      this._placeholder = _slT('sortable.empty');
    }
    this._render();
  };
}

function _attachSortableListMethodsSubRender(SortableList) {
  SortableList.prototype._render = function() {
    var self = this;
    var list = this._container;
    if (!this._items.length) {
      list.innerHTML = '<div class="sl-empty">' + this._placeholder + '</div>';
      return;
    }
    var html = '';
    for (var i = 0; i < this._items.length; i++) {
      html += _slBuildItemHtml(self, this._items[i], i);
    }
    list.innerHTML = html;

    _slBindClickDelegation(self, list);
    _slBindDragEvents(self, list);
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
}

function _attachSortableListMethods(SortableList) {
  _attachSortableListMethodsSubData(SortableList);
  _attachSortableListMethodsSubRender(SortableList);
}
