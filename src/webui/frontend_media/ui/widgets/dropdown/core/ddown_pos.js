// ddown_pos.js — 拆分自 ddown.js（4/5）：打开/定位/关闭
// 依赖 ddown_core.js 中定义的全局 CustomDropdown、_dropdownActive、
// DROPDOWN_SEARCH_THRESHOLD。open() 原本约67行，拆出 _prepareSearchOnOpen /
// _highlightSelectedOnOpen / _bindSearchInputOnce 三个内部 helper 以满足单函数<=50行。

CustomDropdown.prototype._prepareSearchOnOpen = function (list) {
  var showSearch = this._options.length > DROPDOWN_SEARCH_THRESHOLD;
  if (showSearch) {
    this._createSearchInput();
    if (this._searchInput.parentNode !== list) {
      list.insertBefore(this._searchInput, list.firstChild);
    }
    this._searchInput.value = '';
    this._searchInput.style.display = '';
  } else if (this._searchInput) {
    this._searchInput.style.display = 'none';
  }
  return showSearch;
};

CustomDropdown.prototype._highlightSelectedOnOpen = function (list) {
  var options = list.querySelectorAll('.custom-dropdown-option');
  var selectedOption = null;
  for (var i = 0; i < options.length; i++) {
    options[i].removeAttribute('data-highlighted');
    if (options[i].getAttribute('data-value') === this._selectedValue) {
      options[i].setAttribute('data-highlighted', 'true');
      selectedOption = options[i];
    }
  }
  if (selectedOption) {
    setTimeout(function () { selectedOption.scrollIntoView({ block: 'nearest' }); }, 30);
  }
};

CustomDropdown.prototype._bindSearchInputOnce = function (list, trigger) {
  if (!this._searchInput || this._searchInput._bound) return;
  var self = this;
  this._searchInput.addEventListener('input', function () {
    self._applyFilter(this.value);
    self._positionList(list, trigger);
  });
  this._searchInput.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      self.close();
      trigger.focus();
    }
    e.stopPropagation();
  });
  this._searchInput._bound = true;
};

CustomDropdown.prototype.open = function () {
  if (_dropdownActive && _dropdownActive !== this) _dropdownActive.close();

  var list = this._listEl;
  var trigger = this.el.querySelector('.custom-dropdown-trigger');
  if (!list || !trigger) return;

  var showSearch = this._prepareSearchOnOpen(list);

  this._applyFilter('');
  list.classList.add('is-open');
  list.setAttribute('aria-hidden', 'false');
  trigger.setAttribute('aria-expanded', 'true');
  this.el.classList.add('is-open');
  _dropdownActive = this;

  this._positionList(list, trigger);
  this._highlightSelectedOnOpen(list);

  if (showSearch && this._searchInput) {
    var self = this;
    setTimeout(function () { self._searchInput.focus(); }, 50);
  }

  this._bindSearchInputOnce(list, trigger);

  var self2 = this;
  this._repositionOnScroll = function () { self2._positionList(list, trigger); };
  window.addEventListener('scroll', this._repositionOnScroll, true);
  window.addEventListener('resize', this._repositionOnScroll);
};

CustomDropdown.prototype._positionList = function (list, trigger) {
  var rect = trigger.getBoundingClientRect();
  var viewportW = window.innerWidth;
  var viewportH = window.innerHeight;
  var width = Math.max(rect.width, 120);
  var left = rect.left;

  if (left + width > viewportW - 8) {
    left = Math.max(8, viewportW - width - 8);
  }
  if (left < 8) left = 8;

  list.style.width = width + 'px';
  list.style.left = left + 'px';
  list.style.right = 'auto';

  this._updateListHeight();
  var listHeight = list.offsetHeight || 200;
  var spaceBelow = viewportH - rect.bottom - 8;
  var spaceAbove = rect.top - 8;
  this._opensUp = spaceBelow < listHeight && spaceAbove > spaceBelow;

  list.classList.toggle('opens-up', this._opensUp);
  if (this._opensUp) {
    list.style.top = 'auto';
    list.style.bottom = (viewportH - rect.top + 4) + 'px';
  } else {
    list.style.bottom = 'auto';
    list.style.top = (rect.bottom + 4) + 'px';
  }
};

CustomDropdown.prototype.close = function () {
  var list = this._listEl;
  var trigger = this.el.querySelector('.custom-dropdown-trigger');
  if (!list || !trigger) return;

  if (this._searchInput) this._searchInput.value = '';
  this._applyFilter('');

  list.classList.remove('is-open');
  list.setAttribute('aria-hidden', 'true');
  trigger.setAttribute('aria-expanded', 'false');
  this.el.classList.remove('is-open');

  if (this._repositionOnScroll) {
    window.removeEventListener('scroll', this._repositionOnScroll, true);
    window.removeEventListener('resize', this._repositionOnScroll);
  }

  var options = list.querySelectorAll('.custom-dropdown-option');
  for (var i = 0; i < options.length; i++) {
    options[i].removeAttribute('data-highlighted');
  }

  if (_dropdownActive === this) _dropdownActive = null;
};
