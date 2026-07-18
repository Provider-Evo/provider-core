// ddown_api.js — 拆分自 ddown.js（5/5）：公开 API + UiDropdown + 导出
// 依赖 ddown_core.js 中定义的全局 CustomDropdown、_dropdownRegistry、
// _ddEnsurePortal。文末保留 window.CustomDropdown / window.UiDropdown 导出。

CustomDropdown.prototype.select = function (value) {
  var previousValue = this._selectedValue;
  this._selectedValue = value;

  var list = this._listEl;
  if (list) {
    var options = list.querySelectorAll('.custom-dropdown-option');
    for (var i = 0; i < options.length; i++) {
      options[i].setAttribute('aria-selected', options[i].getAttribute('data-value') === value ? 'true' : 'false');
    }
  }

  this._updateDisplay();

  this.el.dispatchEvent(new CustomEvent('change', {
    bubbles: true,
    detail: { value: value, previousValue: previousValue },
  }));

  if (this._originalSelect) {
    this._originalSelect.value = value;
    this._originalSelect.dispatchEvent(new Event('change', { bubbles: true }));
  }

  if (typeof this.onChange === 'function') {
    this.onChange(value, this._getSelectedText(), previousValue);
  }
};

CustomDropdown.prototype.setValue = function (value) {
  if (value !== this._selectedValue) this.select(value);
};

CustomDropdown.prototype.setOptions = function (options, preserveValue) {
  this._options = options || [];
  if (!preserveValue) {
    this._selectedValue = '';
    if (this.autoSelectFirst && this._options.length > 0 && this._options[0].value !== '') {
      this._selectedValue = this._options[0].value;
    }
  } else {
    var exists = false;
    for (var i = 0; i < this._options.length; i++) {
      if (this._options[i].value === this._selectedValue) { exists = true; break; }
    }
    if (!exists && this._options.length > 0) {
      this._selectedValue = this._options[0].value;
    }
  }

  if (this._searchInput && this._searchInput.parentNode) {
    this._searchInput.parentNode.removeChild(this._searchInput);
    this._searchInput._bound = false;
  }

  if (!this._listEl) this._createListElement();
  else this._renderListOptions(this._listEl);
  this._updateDisplay();
};

CustomDropdown.prototype.getOptions = function () {
  return this._options.slice();
};

CustomDropdown.prototype.destroy = function () {
  this.close();
  if (this._listEl && this._listEl.parentNode) {
    this._listEl.parentNode.removeChild(this._listEl);
  }
  var idx = _dropdownRegistry.indexOf(this);
  if (idx !== -1) _dropdownRegistry.splice(idx, 1);
};

CustomDropdown.prototype._onLocaleChange = function () {
  if (this._searchInput) {
    this._searchInput.placeholder = _ddT('dropdown.searchPlaceholder');
    this._searchInput.setAttribute('aria-label', _ddT('dropdown.searchAriaLabel'));
  }
  this._updateDisplay();
};

function _ddMountSelectDropdowns(root, registry) {
  root.querySelectorAll('select[data-ui-dropdown]').forEach(function (el) {
    if (el.dataset.uiDropdownMounted === '1') return;
    var id = el.id;
    if (!id) {
      id = 'dropdown-' + Math.random().toString(36).slice(2, 8);
      el.id = id;
    }
    registry[id] = new CustomDropdown(el);
    el.dataset.uiDropdownMounted = '1';
  });
}

function _ddMountPlainDropdowns(root, registry) {
  root.querySelectorAll('[data-ui-dropdown]:not(select)').forEach(function (el) {
    if (el.dataset.uiDropdownMounted === '1') return;
    if (el.classList.contains('custom-dropdown') && el.querySelector('.custom-dropdown-trigger')) return;
    var id = el.id;
    if (!id) {
      id = 'dropdown-' + Math.random().toString(36).slice(2, 8);
      el.id = id;
    }
    registry[id] = new CustomDropdown(el);
    el.dataset.uiDropdownMounted = '1';
  });
}

var UiDropdown = {
  mount: function (root, registry) {
    root = root || document;
    registry = registry || window._dropdowns || (window._dropdowns = {});
    _ddEnsurePortal();

    _ddMountSelectDropdowns(root, registry);
    _ddMountPlainDropdowns(root, registry);

    return registry;
  },

  get: function (id) {
    return (window._dropdowns || {})[id];
  },

  create: function (spec) {
    spec = spec || {};
    var select = document.createElement('select');
    if (spec.id) select.id = spec.id;
    if (spec.placeholder) select.setAttribute('data-placeholder', spec.placeholder);
    select.setAttribute('data-ui-dropdown', '');
    (spec.options || []).forEach(function (opt) {
      var o = document.createElement('option');
      o.value = opt.value;
      o.textContent = opt.text;
      select.appendChild(o);
    });
    if (spec.container) spec.container.appendChild(select);
    UiDropdown.mount(spec.container || document);
    return spec.id ? UiDropdown.get(spec.id) : null;
  },
};

document.addEventListener('click', function (e) {
  if (!_dropdownActive) return;
  var isInsideWrapper = _dropdownActive.el.contains(e.target);
  var isInsideList = _dropdownActive._listEl && _dropdownActive._listEl.contains(e.target);
  if (!isInsideWrapper && !isInsideList) _dropdownActive.close();
});

if (typeof i18n !== 'undefined' && i18n.onLanguageChanged) {
  i18n.onLanguageChanged(function () {
    for (var i = 0; i < _dropdownRegistry.length; i++) _dropdownRegistry[i]._onLocaleChange();
  });
}

window.CustomDropdown = CustomDropdown;
window.UiDropdown = UiDropdown;
