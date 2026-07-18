// ========================= Custom DatePicker Component (render) =========================
// Calendar HTML rendering helpers. Depends on dtpick_core.js.
'use strict';

CustomDatePicker.prototype._buildPrevMonthDays = function(year, month, firstDay) {
  var daysInPrevMonth = new Date(year, month, 0).getDate();
  var html = '';
  for (var p = firstDay - 1; p >= 0; p--) {
    var d = daysInPrevMonth - p;
    var pm = month - 1;
    var py = year;
    if (pm < 0) { pm = 11; py--; }
    var pStr = this._formatDate(py, pm, d);
    html += '<button type="button" class="datepicker-day is-other-month" data-date="' + pStr + '">' + d + '</button>';
  }
  return html;
};

CustomDatePicker.prototype._buildCurrentMonthDays = function(year, month, daysInMonth, todayStr) {
  var html = '';
  for (var i = 1; i <= daysInMonth; i++) {
    var cStr = this._formatDate(year, month, i);
    var cls = 'datepicker-day';
    if (cStr === todayStr) cls += ' is-today';
    if (cStr === this._value) cls += ' is-selected';
    html += '<button type="button" class="' + cls + '" data-date="' + cStr + '">' + i + '</button>';
  }
  return html;
};

CustomDatePicker.prototype._buildNextMonthDays = function(year, month, firstDay, daysInMonth) {
  var html = '';
  var totalCells = firstDay + daysInMonth;
  var remaining = (7 - (totalCells % 7)) % 7;
  for (var n = 1; n <= remaining; n++) {
    var nm = month + 1;
    var ny = year;
    if (nm > 11) { nm = 0; ny++; }
    var nStr = this._formatDate(ny, nm, n);
    html += '<button type="button" class="datepicker-day is-other-month" data-date="' + nStr + '">' + n + '</button>';
  }
  return html;
};

CustomDatePicker.prototype._calendarHTML = function() {
  var year = this._viewYear;
  var month = this._viewMonth;
  var weekdayLabels = _weekdayLabels();
  var today = new Date();
  var todayStr = this._formatDate(today.getFullYear(), today.getMonth(), today.getDate());

  var html = '<div class="datepicker-header">';
  html += '<button type="button" class="datepicker-nav datepicker-prev-year" title="' + _t('datepicker.prevYear') + '">&laquo;</button>';
  html += '<button type="button" class="datepicker-nav datepicker-prev-month" title="' + _t('datepicker.prevMonth') + '">&lsaquo;</button>';
  html += '<span class="datepicker-title">' + _t('datepicker.title', { year: year, month: _monthName(month) }) + '</span>';
  html += '<button type="button" class="datepicker-nav datepicker-next-month" title="' + _t('datepicker.nextMonth') + '">&rsaquo;</button>';
  html += '<button type="button" class="datepicker-nav datepicker-next-year" title="' + _t('datepicker.nextYear') + '">&raquo;</button>';
  html += '</div>';

  // Weekday headers
  html += '<div class="datepicker-weekdays">';
  for (var w = 0; w < 7; w++) {
    html += '<span class="datepicker-weekday">' + weekdayLabels[w] + '</span>';
  }
  html += '</div>';

  // Day grid
  var firstDay = new Date(year, month, 1).getDay();
  var daysInMonth = new Date(year, month + 1, 0).getDate();
  html += '<div class="datepicker-days">';
  html += this._buildPrevMonthDays(year, month, firstDay);
  html += this._buildCurrentMonthDays(year, month, daysInMonth, todayStr);
  html += this._buildNextMonthDays(year, month, firstDay, daysInMonth);
  html += '</div>';

  // Today & clear buttons
  html += '<div class="datepicker-footer">';
  html += '<button type="button" class="datepicker-today-btn">' + _t('datepicker.today') + '</button>';
  html += '<button type="button" class="datepicker-clear-btn">' + _t('datepicker.clear') + '</button>';
  html += '</div>';

  return html;
};

CustomDatePicker.prototype._formatDate = function(year, month, day) {
  var m = (month + 1 < 10 ? '0' : '') + (month + 1);
  var d = (day < 10 ? '0' : '') + day;
  return year + '-' + m + '-' + d;
};

CustomDatePicker.prototype._refreshCalendar = function() {
  if (this._calendarEl) {
    this._calendarEl.setAttribute('aria-label', _t('datepicker.ariaLabel'));
    this._calendarEl.innerHTML = this._calendarHTML();
  }
};

CustomDatePicker.prototype._onLocaleChange = function() {
  if (!this._customPlaceholder) {
    this.placeholder = _t('datepicker.placeholder');
  }
  this._updateTriggerDisplay();
  if (this._calendarEl) {
    this._refreshCalendar();
  }
};
