// ========================= Custom Dropdown Component =========================
(function() {
  'use strict';

  var activeDropdown = null;

  /**
   * Initialize a custom dropdown on an element (replaces native <select> or
   * creates a new custom dropdown from a wrapper <div>).
   *
   * @param {string|HTMLElement} el - The element or its ID.
   * @param {Object} options
   * @param {Function} [options.onChange] - Called with (value, text, previousValue) when selection changes.
   * @param {boolean} [options.autoSelectFirst] - Auto-select first option on init (default: true).
   */
  function CustomDropdown(el, options) {
    options = options || {};
    this.el = typeof el === 'string' ? document.getElementById(el) : el;
    if (!this.el) return null;

    this.onChange = options.onChange || null;
    this.autoSelectFirst = options.autoSelectFirst !== false;
    this._id = this.el.id || ('dropdown-' + Math.random().toString(36).slice(2, 8));
    this._options = []; // { value, text }
    this._selectedValue = '';
    this._originalSelect = null;
    this._built = false;

    this._build();
    this._bindEvents();
    this._defineValueProperty();
  }

  CustomDropdown.prototype._build = function() {
    var el = this.el;

    if (el.tagName === 'SELECT') {
      this._migrateFromSelect(el);
      return;
    }

    if (el.classList.contains('custom-dropdown')) {
      this._readOptionsFromDOM(el);
      this._built = true;
      return;
    }

    el.classList.add('custom-dropdown');
    el.setAttribute('data-value', '');
    el.innerHTML = '';
    this._built = true;
  };

  CustomDropdown.prototype._migrateFromSelect = function(selectEl) {
    var wrapper = document.createElement('div');
    wrapper.className = 'custom-dropdown';
    wrapper.id = selectEl.id;
    wrapper.setAttribute('data-value', selectEl.value || '');

    // Clone all options
    var opts = [];
    for (var i = 0; i < selectEl.options.length; i++) {
      opts.push({ value: selectEl.options[i].value, text: selectEl.options[i].text });
    }
    this._options = opts;
    this._selectedValue = selectEl.value || '';
    this._originalSelect = selectEl;

    // Build the custom dropdown HTML
    wrapper.innerHTML = this._triggerHTML() + this._listHTML();

    // Replace the <select> in the DOM
    selectEl.parentNode.replaceChild(wrapper, selectEl);
    this.el = wrapper;
    this._built = true;
    this._updateDisplay();
  };

  CustomDropdown.prototype._defineValueProperty = function() {
    var self = this;
    Object.defineProperty(this.el, 'value', {
      get: function() { return self._selectedValue; },
      set: function(val) { self.setValue(val); },
      configurable: true
    });
  };

  CustomDropdown.prototype._triggerHTML = function() {
    var selectedText = this._getSelectedText() || '请选择';
    var labelId = this._id + '-label';
    var valueId = this._id + '-value';
    return '<button type="button" class="custom-dropdown-trigger" ' +
      'aria-haspopup="listbox" aria-expanded="false" ' +
      'aria-labelledby="' + labelId + ' ' + valueId + '">' +
      '<span class="custom-dropdown-label" id="' + labelId + '">' + escapeHtml(selectedText) + '</span>' +
      '<span class="custom-dropdown-value" id="' + valueId + '" hidden>' + escapeHtml(this._selectedValue) + '</span>' +
      '<svg class="custom-dropdown-chevron" aria-hidden="true" viewBox="0 0 20 20" fill="currentColor">' +
        '<path fill-rule="evenodd" d="M5.23 7.21a.75.75 0 011.06.02L10 11.168l3.71-3.938a.75.75 0 111.08 1.04l-4.25 4.5a.75.75 0 01-1.08 0l-4.25-4.5a.75.75 0 01.02-1.06z"/>' +
      '</svg></button>';
  };

  CustomDropdown.prototype._listHTML = function() {
    var html = '<div class="custom-dropdown-list" role="listbox" aria-hidden="true">';
    for (var i = 0; i < this._options.length; i++) {
      var opt = this._options[i];
      var selected = opt.value === this._selectedValue ? ' aria-selected="true"' : ' aria-selected="false"';
      html += '<div class="custom-dropdown-option" role="option" data-value="' + escapeHtml(opt.value) + '"' + selected + '>' +
        escapeHtml(opt.text) + '</div>';
    }
    html += '</div>';
    return html;
  };

  CustomDropdown.prototype._getSelectedText = function() {
    for (var i = 0; i < this._options.length; i++) {
      if (this._options[i].value === this._selectedValue) {
        return this._options[i].text;
      }
    }
    return '';
  };

  CustomDropdown.prototype._updateDisplay = function() {
    var label = this.el.querySelector('.custom-dropdown-label');
    var valueSpan = this.el.querySelector('.custom-dropdown-value');
    var text = this._getSelectedText() || '';
    if (label) label.textContent = text;
    if (valueSpan) valueSpan.textContent = this._selectedValue;
    this.el.setAttribute('data-value', this._selectedValue);
  };

  CustomDropdown.prototype._bindEvents = function() {
    var self = this;
    var trigger = this.el.querySelector('.custom-dropdown-trigger');
    var list = this.el.querySelector('.custom-dropdown-list');

    if (!trigger || !list) return;

    // Click trigger to toggle
    trigger.addEventListener('click', function(e) {
      e.stopPropagation();
      if (self.el.classList.contains('is-open')) {
        self.close();
      } else {
        self.open();
      }
    });

    // Click option to select
    list.addEventListener('click', function(e) {
      var option = e.target.closest('.custom-dropdown-option');
      if (option) {
        self.select(option.getAttribute('data-value'));
        self.close();
      }
    });

    // Keyboard navigation on trigger
    trigger.addEventListener('keydown', function(e) {
      switch (e.key) {
        case 'Enter':
        case ' ':
          e.preventDefault();
          if (self.el.classList.contains('is-open')) self.close();
          else self.open();
          break;
        case 'Escape':
          self.close();
          break;
        case 'ArrowDown':
          e.preventDefault();
          if (!self.el.classList.contains('is-open')) self.open();
          else self._highlightNext(1);
          break;
        case 'ArrowUp':
          e.preventDefault();
          if (!self.el.classList.contains('is-open')) self.open();
          else self._highlightNext(-1);
          break;
      }
    });

    // Keyboard navigation on options
    list.addEventListener('keydown', function(e) {
      switch (e.key) {
        case 'Enter':
        case ' ':
          e.preventDefault();
          var highlighted = list.querySelector('.custom-dropdown-option[data-highlighted="true"]');
          if (highlighted) {
            self.select(highlighted.getAttribute('data-value'));
            self.close();
          }
          break;
        case 'Escape':
          self.close();
          trigger.focus();
          break;
        case 'ArrowDown':
          e.preventDefault();
          self._highlightNext(1);
          break;
        case 'ArrowUp':
          e.preventDefault();
          self._highlightNext(-1);
          break;
      }
    });
  };

  CustomDropdown.prototype._highlightNext = function(delta) {
    var list = this.el.querySelector('.custom-dropdown-list');
    var options = list.querySelectorAll('.custom-dropdown-option');
    var currentIndex = -1;
    for (var i = 0; i < options.length; i++) {
      if (options[i].hasAttribute('data-highlighted')) {
        currentIndex = i;
        options[i].removeAttribute('data-highlighted');
        break;
      }
    }
    var newIndex = currentIndex + delta;
    if (newIndex < 0) newIndex = options.length - 1;
    if (newIndex >= options.length) newIndex = 0;
    options[newIndex].setAttribute('data-highlighted', 'true');
    options[newIndex].scrollIntoView({ block: 'nearest' });
  };

  CustomDropdown.prototype.open = function() {
    if (activeDropdown && activeDropdown !== this) {
      activeDropdown.close();
    }

    var list = this.el.querySelector('.custom-dropdown-list');
    var trigger = this.el.querySelector('.custom-dropdown-trigger');
    if (!list || !trigger) return;

    // Position the dropdown list using fixed positioning to escape ancestor clipping
    this._positionList(list, trigger);

    list.classList.add('is-open');
    list.setAttribute('aria-hidden', 'false');
    trigger.setAttribute('aria-expanded', 'true');
    this.el.classList.add('is-open');
    activeDropdown = this;

    // Highlight the currently selected option
    var options = list.querySelectorAll('.custom-dropdown-option');
    for (var i = 0; i < options.length; i++) {
      options[i].removeAttribute('data-highlighted');
      if (options[i].getAttribute('data-value') === this._selectedValue) {
        options[i].setAttribute('data-highlighted', 'true');
      }
    }

    // Bind scroll/resize listeners to reposition
    this._repositionOnScroll = this._repositionOnScroll || this._positionList.bind(this, list, trigger);
    window.addEventListener('scroll', this._repositionOnScroll, true);
    window.addEventListener('resize', this._repositionOnScroll);
  };

  CustomDropdown.prototype._positionList = function(list, trigger) {
    var rect = trigger.getBoundingClientRect();
    list.style.top = (rect.bottom + 4) + 'px';
    list.style.left = rect.left + 'px';
    list.style.width = rect.width + 'px';
  };

  CustomDropdown.prototype.close = function() {
    var list = this.el.querySelector('.custom-dropdown-list');
    var trigger = this.el.querySelector('.custom-dropdown-trigger');
    if (!list || !trigger) return;

    list.classList.remove('is-open');
    list.setAttribute('aria-hidden', 'true');
    trigger.setAttribute('aria-expanded', 'false');
    this.el.classList.remove('is-open');

    // Remove scroll/resize listeners
    if (this._repositionOnScroll) {
      window.removeEventListener('scroll', this._repositionOnScroll, true);
      window.removeEventListener('resize', this._repositionOnScroll);
    }

    var options = list.querySelectorAll('.custom-dropdown-option');
    for (var i = 0; i < options.length; i++) {
      options[i].removeAttribute('data-highlighted');
    }

    if (activeDropdown === this) activeDropdown = null;
  };

  CustomDropdown.prototype.select = function(value) {
    var previousValue = this._selectedValue;
    this._selectedValue = value;

    // Update aria-selected on options
    var list = this.el.querySelector('.custom-dropdown-list');
    if (list) {
      var options = list.querySelectorAll('.custom-dropdown-option');
      for (var i = 0; i < options.length; i++) {
        options[i].setAttribute('aria-selected', options[i].getAttribute('data-value') === value ? 'true' : 'false');
      }
    }

    this._updateDisplay();

    // Dispatch 'change' event on the wrapper for backward compatibility
    this.el.dispatchEvent(new CustomEvent('change', {
      bubbles: true,
      detail: { value: value, previousValue: previousValue }
    }));

    // Also dispatch on the original <select> if it was migrated
    if (this._originalSelect) {
      this._originalSelect.value = value;
      this._originalSelect.dispatchEvent(new Event('change', { bubbles: true }));
    }

    // Call onChange callback
    if (typeof this.onChange === 'function') {
      this.onChange(value, this._getSelectedText(), previousValue);
    }
  };

  CustomDropdown.prototype.setValue = function(value) {
    if (value !== this._selectedValue) {
      this.select(value);
    }
  };

  /**
   * Rebuild the dropdown options from an array of { value, text } objects.
   */
  CustomDropdown.prototype.setOptions = function(options, preserveValue) {
    this._options = options || [];
    if (!preserveValue) {
      this._selectedValue = '';
      if (this.autoSelectFirst && this._options.length > 0 && this._options[0].value !== '') {
        this._selectedValue = this._options[0].value;
      }
    }
    if (preserveValue) {
      var exists = false;
      for (var i = 0; i < this._options.length; i++) {
        if (this._options[i].value === this._selectedValue) { exists = true; break; }
      }
      if (!exists && this._options.length > 0) {
        this._selectedValue = this._options[0].value;
      }
    }

    // Rebuild the list DOM
    var list = this.el.querySelector('.custom-dropdown-list');
    if (list) {
      list.innerHTML = '';
      for (var j = 0; j < this._options.length; j++) {
        var opt = this._options[j];
        var div = document.createElement('div');
        div.className = 'custom-dropdown-option';
        div.setAttribute('role', 'option');
        div.setAttribute('data-value', opt.value);
        div.setAttribute('aria-selected', opt.value === this._selectedValue ? 'true' : 'false');
        div.textContent = opt.text;
        list.appendChild(div);
      }
    }
    this._updateDisplay();
  };

  CustomDropdown.prototype.getOptions = function() {
    return this._options.slice();
  };

  // ========================= Global click-outside handler =========================
  document.addEventListener('click', function(e) {
    if (activeDropdown && !activeDropdown.el.contains(e.target)) {
      activeDropdown.close();
    }
  });

  // ========================= Export =========================
  window.CustomDropdown = CustomDropdown;

  function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
  }

})();
