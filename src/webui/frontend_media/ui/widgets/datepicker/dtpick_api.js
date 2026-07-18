// ========================= Custom DatePicker Component (public API) =========================
// open/close/setValue/getValue + i18n binding + export. Depends on dtpick_core.js.
'use strict';

CustomDatePicker.prototype.open = function() {
  if (activePicker && activePicker !== this) {
    activePicker.close();
  }
  this._refreshCalendar();

  // Position
  var trigger = this._triggerEl;
  var cal = this._calendarEl;
  var rect = trigger.getBoundingClientRect();
  cal.style.position = 'fixed';
  cal.style.top = (rect.bottom + 4) + 'px';
  cal.style.left = rect.left + 'px';
  cal.style.minWidth = rect.width + 'px';

  cal.classList.add('is-open');
  this._triggerEl.setAttribute('aria-expanded', 'true');
  this.el.classList.add('is-open');
  this._isOpen = true;
  activePicker = this;

  // Focus the selected day or today
  var self = this;
  setTimeout(function() {
    var target = self._calendarEl.querySelector('.datepicker-day.is-selected') ||
                 self._calendarEl.querySelector('.datepicker-day.is-today');
    if (target) target.focus();
  }, 50);
};

CustomDatePicker.prototype.close = function() {
  if (!this._isOpen) return;
  this._calendarEl.classList.remove('is-open');
  this._triggerEl.setAttribute('aria-expanded', 'false');
  this.el.classList.remove('is-open');
  this._isOpen = false;
  if (activePicker === this) activePicker = null;
};

CustomDatePicker.prototype.setValue = function(dateStr) {
  var prev = this._value;
  this._value = dateStr || '';
  this._parseViewFromValue();
  this._updateTriggerDisplay();

  if (this._value !== prev) {
    this.el.dispatchEvent(new CustomEvent('change', {
      bubbles: true,
      detail: { value: this._value, previousValue: prev }
    }));
    if (typeof this.onChange === 'function') {
      this.onChange(this._value, prev);
    }
  }
};

CustomDatePicker.prototype.getValue = function() {
  return this._value;
};

if (typeof i18n !== 'undefined' && i18n.onLanguageChanged) {
  i18n.onLanguageChanged(function() {
    for (var i = 0; i < _registry.length; i++) {
      _registry[i]._onLocaleChange();
    }
  });
}

// ========================= Export =========================
window.CustomDatePicker = CustomDatePicker;
