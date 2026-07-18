// ========================= Custom DatePicker Component (core) =========================
// Replaces native <input type="date"> with a themed calendar picker.
// ES5 compatible, no framework dependencies.
// Split across dtpick_core.js / dtpick_render.js / dtpick_events.js / dtpick_api.js.
'use strict';

var activePicker = null;
var _registry = [];

function _t(key, opts) {
  return (typeof t === 'function') ? t(key, opts) : key;
}

function _weekdayLabels() {
  var labels = [];
  for (var w = 0; w < 7; w++) {
    labels.push(_t('datepicker.weekday' + w));
  }
  return labels;
}

function _monthName(monthIndex) {
  return _t('datepicker.month' + (monthIndex + 1));
}

/**
 * @param {string|HTMLElement} el - The <input type="date"> element or its ID.
 * @param {Object} [options]
 * @param {Function} [options.onChange] - Called with (dateString) when date changes. dateString is 'YYYY-MM-DD' or ''.
 * @param {string} [options.placeholder] - Placeholder text when no date selected.
 */
function CustomDatePicker(el, options) {
  options = options || {};
  this.el = typeof el === 'string' ? document.getElementById(el) : el;
  if (!this.el || this.el.tagName !== 'INPUT') return null;

  this.onChange = options.onChange || null;
  this._customPlaceholder = options.placeholder || null;
  this.placeholder = this._customPlaceholder || _t('datepicker.placeholder');
  this._id = this.el.id || ('datepicker-' + Math.random().toString(36).slice(2, 8));
  this._value = this.el.value || '';
  this._viewYear = 0;
  this._viewMonth = 0;
  this._calendarEl = null;
  this._triggerEl = null;
  this._isOpen = false;

  this._parseViewFromValue();
  this._build();
  this._bindEvents();
  _registry.push(this);
}

CustomDatePicker.prototype._parseViewFromValue = function() {
  if (this._value) {
    var parts = this._value.split('-');
    this._viewYear = parseInt(parts[0], 10) || new Date().getFullYear();
    this._viewMonth = (parseInt(parts[1], 10) || 1) - 1;
  } else {
    var now = new Date();
    this._viewYear = now.getFullYear();
    this._viewMonth = now.getMonth();
  }
};

CustomDatePicker.prototype._build = function() {
  // Replace the native <input> with a trigger div
  var wrapper = document.createElement('div');
  wrapper.className = 'custom-datepicker';
  wrapper.id = this._id;

  var trigger = document.createElement('button');
  trigger.type = 'button';
  trigger.className = 'custom-datepicker-trigger';
  trigger.setAttribute('aria-haspopup', 'dialog');
  trigger.setAttribute('aria-expanded', 'false');
  this._triggerEl = trigger;
  this._updateTriggerDisplay();

  wrapper.appendChild(trigger);

  // Build calendar popup
  var cal = document.createElement('div');
  cal.className = 'custom-datepicker-calendar';
  cal.setAttribute('role', 'dialog');
  cal.setAttribute('aria-label', _t('datepicker.ariaLabel'));
  cal.innerHTML = this._calendarHTML();
  this._calendarEl = cal;
  wrapper.appendChild(cal);

  // Replace in DOM
  this.el.parentNode.replaceChild(wrapper, this.el);
  this.el = wrapper;
  this._defineValueProperty();
};

CustomDatePicker.prototype._defineValueProperty = function() {
  var self = this;
  Object.defineProperty(this.el, 'value', {
    get: function() { return self._value; },
    set: function(val) { self.setValue(val); },
    configurable: true
  });
};

CustomDatePicker.prototype._updateTriggerDisplay = function() {
  if (!this._triggerEl) return;
  if (this._value) {
    this._triggerEl.textContent = this._value;
    this._triggerEl.classList.remove('is-placeholder');
  } else {
    this._triggerEl.textContent = this.placeholder;
    this._triggerEl.classList.add('is-placeholder');
  }
};
