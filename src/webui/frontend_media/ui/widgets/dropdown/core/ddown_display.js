// ddown_display.js — 拆分自 ddown.js（2/5）：显示/搜索输入相关方法
// 依赖 ddown_core.js 中定义的全局 CustomDropdown、_ddT、_ddEscapeHtml、
// DROPDOWN_SEARCH_THRESHOLD、DROPDOWN_MAX_VISIBLE、DROPDOWN_OPTION_HEIGHT。

CustomDropdown.prototype._displayLabel = function () {
  var text = this._getSelectedText();
  if (text) return text;
  return this._placeholder || _ddT('dropdown.pleaseSelect');
};

CustomDropdown.prototype._isPlaceholderShown = function () {
  return !this._getSelectedText();
};

CustomDropdown.prototype._createSearchInput = function () {
  if (this._searchInput) return;
  var input = document.createElement('input');
  input.type = 'text';
  input.className = 'custom-dropdown-search';
  input.placeholder = _ddT('dropdown.searchPlaceholder');
  input.setAttribute('autocomplete', 'off');
  input.setAttribute('aria-label', _ddT('dropdown.searchAriaLabel'));
  this._searchInput = input;
};

CustomDropdown.prototype._applyFilter = function (keyword) {
  var list = this._listEl;
  if (!list) return;
  var options = list.querySelectorAll('.custom-dropdown-option');
  var lower = (keyword || '').toLowerCase();
  for (var i = 0; i < options.length; i++) {
    var text = (options[i].textContent || '').toLowerCase();
    options[i].style.display = (!lower || text.indexOf(lower) !== -1) ? '' : 'none';
  }
  this._updateListHeight();
};

CustomDropdown.prototype._updateListHeight = function () {
  var list = this._listEl;
  if (!list) return;
  var visibleCount = 0;
  var options = list.querySelectorAll('.custom-dropdown-option');
  for (var i = 0; i < options.length; i++) {
    if (options[i].style.display !== 'none') visibleCount++;
  }
  var showSearch = this._options.length > DROPDOWN_SEARCH_THRESHOLD;
  var searchHeight = showSearch ? 44 : 0;
  var maxItems = Math.min(Math.max(visibleCount, 1), DROPDOWN_MAX_VISIBLE);
  list.style.maxHeight = (maxItems * DROPDOWN_OPTION_HEIGHT + searchHeight + 12) + 'px';
};

CustomDropdown.prototype._triggerHTML = function () {
  var selectedText = this._displayLabel();
  var labelId = this._id + '-label';
  var valueId = this._id + '-value';
  var phCls = this._isPlaceholderShown() ? ' is-placeholder' : '';
  return ''
    + '<button type="button" class="custom-dropdown-trigger"'
    + ' aria-haspopup="listbox" aria-expanded="false"'
    + ' aria-labelledby="' + labelId + ' ' + valueId + '">'
    + '<span class="custom-dropdown-label' + phCls + '" id="' + labelId + '">' + _ddEscapeHtml(selectedText) + '</span>'
    + '<span class="custom-dropdown-value" id="' + valueId + '" hidden>' + _ddEscapeHtml(this._selectedValue) + '</span>'
    + '<svg class="custom-dropdown-chevron" aria-hidden="true" viewBox="0 0 20 20" fill="currentColor">'
    + '<path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"/>'
    + '</svg></button>';
};

CustomDropdown.prototype._getSelectedText = function () {
  for (var i = 0; i < this._options.length; i++) {
    if (this._options[i].value === this._selectedValue) {
      return this._options[i].text;
    }
  }
  return '';
};

CustomDropdown.prototype._updateDisplay = function () {
  var label = this.el.querySelector('.custom-dropdown-label');
  var valueSpan = this.el.querySelector('.custom-dropdown-value');
  if (label) {
    label.textContent = this._displayLabel();
    label.classList.toggle('is-placeholder', this._isPlaceholderShown());
  }
  if (valueSpan) valueSpan.textContent = this._selectedValue;
  this.el.setAttribute('data-value', this._selectedValue);
};
