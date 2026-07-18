// ========================= Custom DatePicker Component (events) =========================
// Event binding helpers. Depends on dtpick_core.js / dtpick_render.js.
'use strict';

CustomDatePicker.prototype._bindTriggerEvents = function() {
  var self = this;

  this._triggerEl.addEventListener('click', function(e) {
    e.stopPropagation();
    if (self._isOpen) self.close();
    else self.open();
  });

  this._triggerEl.addEventListener('keydown', function(e) {
    switch (e.key) {
      case 'Enter':
      case ' ':
        e.preventDefault();
        if (self._isOpen) self.close();
        else self.open();
        break;
      case 'Escape':
        self.close();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        if (!self._isOpen) self.open();
        else self._moveSelection(-1);
        break;
      case 'ArrowRight':
        e.preventDefault();
        if (!self._isOpen) self.open();
        else self._moveSelection(1);
        break;
    }
  });
};

CustomDatePicker.prototype._handleCalendarNavClick = function(target) {
  // Nav buttons
  if (target.classList.contains('datepicker-prev-month')) {
    this._viewMonth--;
    if (this._viewMonth < 0) { this._viewMonth = 11; this._viewYear--; }
    this._refreshCalendar();
    return true;
  }
  if (target.classList.contains('datepicker-next-month')) {
    this._viewMonth++;
    if (this._viewMonth > 11) { this._viewMonth = 0; this._viewYear++; }
    this._refreshCalendar();
    return true;
  }
  if (target.classList.contains('datepicker-prev-year')) {
    this._viewYear--;
    this._refreshCalendar();
    return true;
  }
  if (target.classList.contains('datepicker-next-year')) {
    this._viewYear++;
    this._refreshCalendar();
    return true;
  }
  return false;
};

CustomDatePicker.prototype._bindCalendarClickEvents = function() {
  var self = this;

  this._calendarEl.addEventListener('click', function(e) {
    var target = e.target;

    // Day click
    if (target.classList.contains('datepicker-day')) {
      var dateStr = target.getAttribute('data-date');
      if (dateStr) {
        self.setValue(dateStr);
        self.close();
      }
      return;
    }

    if (self._handleCalendarNavClick(target)) return;

    // Today button
    if (target.classList.contains('datepicker-today-btn')) {
      var now = new Date();
      self._viewYear = now.getFullYear();
      self._viewMonth = now.getMonth();
      self.setValue(self._formatDate(self._viewYear, self._viewMonth, now.getDate()));
      self._refreshCalendar();
      return;
    }

    // Clear button
    if (target.classList.contains('datepicker-clear-btn')) {
      self.setValue('');
      self._refreshCalendar();
      return;
    }
  });
};

CustomDatePicker.prototype._bindKeyboardEvents = function() {
  var self = this;

  this._calendarEl.addEventListener('keydown', function(e) {
    switch (e.key) {
      case 'Escape':
        self.close();
        self._triggerEl.focus();
        break;
      case 'ArrowLeft':
        e.preventDefault();
        self._moveSelection(-1);
        break;
      case 'ArrowRight':
        e.preventDefault();
        self._moveSelection(1);
        break;
      case 'ArrowUp':
        e.preventDefault();
        self._moveSelection(-7);
        break;
      case 'ArrowDown':
        e.preventDefault();
        self._moveSelection(7);
        break;
      case 'Enter':
        e.preventDefault();
        var focused = self._calendarEl.querySelector('.datepicker-day:focus');
        if (focused) {
          var dateStr = focused.getAttribute('data-date');
          if (dateStr) {
            self.setValue(dateStr);
            self.close();
          }
        }
        break;
    }
  });
};

CustomDatePicker.prototype._bindOutsideClickEvents = function() {
  var self = this;
  document.addEventListener('click', function(e) {
    if (self._isOpen && !self.el.contains(e.target)) {
      self.close();
    }
  });
};

CustomDatePicker.prototype._bindEvents = function() {
  this._bindTriggerEvents();
  this._bindCalendarClickEvents();
  this._bindKeyboardEvents();
  this._bindOutsideClickEvents();
};

CustomDatePicker.prototype._moveSelection = function(delta) {
  // Find currently focused or selected day
  var days = this._calendarEl.querySelectorAll('.datepicker-day');
  var currentIdx = -1;
  for (var i = 0; i < days.length; i++) {
    if (days[i] === document.activeElement || days[i].classList.contains('is-selected')) {
      currentIdx = i;
      break;
    }
  }
  // If nothing focused, focus the selected or today
  if (currentIdx === -1) {
    var sel = this._calendarEl.querySelector('.datepicker-day.is-selected') ||
              this._calendarEl.querySelector('.datepicker-day.is-today');
    if (sel) { sel.focus(); return; }
    // Focus first day of current month
    var firstCurrent = this._calendarEl.querySelector('.datepicker-day:not(.is-other-month)');
    if (firstCurrent) firstCurrent.focus();
    return;
  }
  var newIdx = currentIdx + delta;
  if (newIdx < 0 || newIdx >= days.length) return;
  days[newIdx].focus();
};
