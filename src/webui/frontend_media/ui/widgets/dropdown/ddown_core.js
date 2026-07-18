// UiDropdown — 声明式 placeholder + portal 浮层调度
// 拆分自 ddown.js（1/5）：模块内部状态 + CustomDropdown 构造与构建方法
// 注意：不用 IIFE 包裹——后续 ddown_display.js / ddown_events.js /
// ddown_pos.js / ddown_api.js 需要跨文件继续挂载 prototype 方法，
// 必须共享同一个全局 CustomDropdown 函数引用。

var _dropdownActive = null;
var _dropdownRegistry = [];
var _dropdownPortal = null;

var DROPDOWN_SEARCH_THRESHOLD = 5;
var DROPDOWN_MAX_VISIBLE = 6;
var DROPDOWN_OPTION_HEIGHT = 36;

function _ddT(key) {
  return typeof t === 'function' ? t(key) : key;
}

function _ddEscapeHtml(text) {
  var div = document.createElement('div');
  div.textContent = text || '';
  return div.innerHTML;
}

function _ddEnsurePortal() {
  if (_dropdownPortal && _dropdownPortal.parentNode) return _dropdownPortal;
  _dropdownPortal = document.getElementById('ui-dropdown-portal');
  if (!_dropdownPortal) {
    _dropdownPortal = document.createElement('div');
    _dropdownPortal.id = 'ui-dropdown-portal';
    _dropdownPortal.setAttribute('aria-hidden', 'true');
    (document.body || document.documentElement).appendChild(_dropdownPortal);
  }
  return _dropdownPortal;
}

function _ddAttachList(list) {
  _ddEnsurePortal().appendChild(list);
}

function CustomDropdown(el, options) {
  options = options || {};
  this.el = typeof el === 'string' ? document.getElementById(el) : el;
  if (!this.el) return null;

  this.onChange = options.onChange || null;
  this.autoSelectFirst = options.autoSelectFirst !== false;
  this._placeholder = options.placeholder
    || this.el.getAttribute('data-placeholder')
    || '';
  this._id = this.el.id || ('dropdown-' + Math.random().toString(36).slice(2, 8));
  this._options = [];
  this._selectedValue = '';
  this._originalSelect = null;
  this._built = false;
  this._searchInput = null;
  this._listEl = null;
  this._opensUp = false;

  this._build();
  this._bindEvents();
  this._defineValueProperty();
  _dropdownRegistry.push(this);
}

CustomDropdown.prototype._build = function () {
  var el = this.el;
  if (el.tagName === 'SELECT') {
    this._migrateFromSelect(el);
    return;
  }
  if (el.classList.contains('custom-dropdown') && el.querySelector('.custom-dropdown-trigger')) {
    this._listEl = document.getElementById(this._id + '-list');
    this._readOptionsFromDOM(el);
    this._built = true;
    return;
  }
  this._readOptionsFromDOM(el);
  el.classList.add('custom-dropdown');
  el.setAttribute('data-value', this._selectedValue || '');
  el.innerHTML = this._triggerHTML();
  this._createListElement();
  this._built = true;
  this._updateDisplay();
};

CustomDropdown.prototype._readOptionsFromDOM = function (root) {
  root = root || this.el;
  var opts = [];
  var nodes = root.querySelectorAll('[data-value], option, [data-option-value]');
  if (nodes.length) {
    for (var i = 0; i < nodes.length; i++) {
      var node = nodes[i];
      if (node.classList && node.classList.contains('custom-dropdown-trigger')) continue;
      if (node.classList && node.classList.contains('custom-dropdown-list')) continue;
      var val = node.getAttribute('data-value')
        || node.getAttribute('data-option-value')
        || node.getAttribute('value')
        || '';
      var text = node.getAttribute('data-label')
        || (node.textContent || '').trim();
      opts.push({ value: val, text: text });
    }
  }
  if (opts.length) {
    this._options = opts;
    if (!this._selectedValue && this.el.getAttribute('data-value')) {
      this._selectedValue = this.el.getAttribute('data-value');
    }
  }
};

CustomDropdown.prototype._createListElement = function () {
  if (this._listEl) return;
  var list = document.createElement('div');
  list.className = 'custom-dropdown-list';
  list.setAttribute('role', 'listbox');
  list.setAttribute('aria-hidden', 'true');
  list.id = this._id + '-list';
  this._renderListOptions(list);
  this._listEl = list;
  _ddAttachList(list);
};

CustomDropdown.prototype._renderListOptions = function (list) {
  list.innerHTML = '';
  for (var i = 0; i < this._options.length; i++) {
    var opt = this._options[i];
    var div = document.createElement('div');
    div.className = 'custom-dropdown-option';
    div.setAttribute('role', 'option');
    div.setAttribute('data-value', opt.value);
    div.setAttribute('aria-selected', opt.value === this._selectedValue ? 'true' : 'false');
    div.textContent = opt.text;
    list.appendChild(div);
  }
};

CustomDropdown.prototype._migrateFromSelect = function (selectEl) {
  var wrapper = document.createElement('div');
  wrapper.className = 'custom-dropdown';
  wrapper.id = selectEl.id;
  wrapper.setAttribute('data-value', selectEl.value || '');
  if (selectEl.getAttribute('data-placeholder')) {
    wrapper.setAttribute('data-placeholder', selectEl.getAttribute('data-placeholder'));
  }

  var opts = [];
  for (var i = 0; i < selectEl.options.length; i++) {
    opts.push({ value: selectEl.options[i].value, text: selectEl.options[i].text });
  }
  this._options = opts;
  this._selectedValue = selectEl.value || '';
  this._originalSelect = selectEl;
  if (!this._placeholder && selectEl.getAttribute('data-placeholder')) {
    this._placeholder = selectEl.getAttribute('data-placeholder');
  }

  wrapper.innerHTML = this._triggerHTML();
  this.el = wrapper;
  this._createListElement();
  selectEl.parentNode.replaceChild(wrapper, selectEl);
  this._built = true;
  this._updateDisplay();
};

CustomDropdown.prototype._defineValueProperty = function () {
  var self = this;
  Object.defineProperty(this.el, 'value', {
    get: function () { return self._selectedValue; },
    set: function (val) { self.setValue(val); },
    configurable: true,
  });
};
