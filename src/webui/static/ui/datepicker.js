// ========================= Custom DatePicker Component =========================
// Replaces native <input type="date"> with a themed calendar picker.
// ES5 compatible, no framework dependencies.
(function() {
  'use strict';

  var activePicker = null;
  var WEEKDAY_LABELS = ['日', '一', '二', '三', '四', '五', '六'];

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
    this.placeholder = options.placeholder || '选择日期';
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
    cal.setAttribute('aria-label', '日期选择器');
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

  CustomDatePicker.prototype._calendarHTML = function() {
    var year = this._viewYear;
    var month = this._viewMonth;
    var monthNames = ['1月', '2月', '3月', '4月', '5月', '6月',
                      '7月', '8月', '9月', '10月', '11月', '12月'];
    var today = new Date();
    var todayStr = this._formatDate(today.getFullYear(), today.getMonth(), today.getDate());

    var html = '<div class="datepicker-header">';
    html += '<button type="button" class="datepicker-nav datepicker-prev-year" title="上一年">&laquo;</button>';
    html += '<button type="button" class="datepicker-nav datepicker-prev-month" title="上一月">&lsaquo;</button>';
    html += '<span class="datepicker-title">' + year + '年 ' + monthNames[month] + '</span>';
    html += '<button type="button" class="datepicker-nav datepicker-next-month" title="下一月">&rsaquo;</button>';
    html += '<button type="button" class="datepicker-nav datepicker-next-year" title="下一年">&raquo;</button>';
    html += '</div>';

    // Weekday headers
    html += '<div class="datepicker-weekdays">';
    for (var w = 0; w < 7; w++) {
      html += '<span class="datepicker-weekday">' + WEEKDAY_LABELS[w] + '</span>';
    }
    html += '</div>';

    // Day grid
    html += '<div class="datepicker-days">';
    var firstDay = new Date(year, month, 1).getDay();
    var daysInMonth = new Date(year, month + 1, 0).getDate();
    var daysInPrevMonth = new Date(year, month, 0).getDate();

    // Previous month trailing days
    for (var p = firstDay - 1; p >= 0; p--) {
      var d = daysInPrevMonth - p;
      var pm = month - 1;
      var py = year;
      if (pm < 0) { pm = 11; py--; }
      var pStr = this._formatDate(py, pm, d);
      html += '<button type="button" class="datepicker-day is-other-month" data-date="' + pStr + '">' + d + '</button>';
    }

    // Current month days
    for (var i = 1; i <= daysInMonth; i++) {
      var cStr = this._formatDate(year, month, i);
      var cls = 'datepicker-day';
      if (cStr === todayStr) cls += ' is-today';
      if (cStr === this._value) cls += ' is-selected';
      html += '<button type="button" class="' + cls + '" data-date="' + cStr + '">' + i + '</button>';
    }

    // Next month leading days
    var totalCells = firstDay + daysInMonth;
    var remaining = (7 - (totalCells % 7)) % 7;
    for (var n = 1; n <= remaining; n++) {
      var nm = month + 1;
      var ny = year;
      if (nm > 11) { nm = 0; ny++; }
      var nStr = this._formatDate(ny, nm, n);
      html += '<button type="button" class="datepicker-day is-other-month" data-date="' + nStr + '">' + n + '</button>';
    }

    html += '</div>';

    // Today & clear buttons
    html += '<div class="datepicker-footer">';
    html += '<button type="button" class="datepicker-today-btn">今天</button>';
    html += '<button type="button" class="datepicker-clear-btn">清除</button>';
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
      this._calendarEl.innerHTML = this._calendarHTML();
    }
  };

  CustomDatePicker.prototype._bindEvents = function() {
    var self = this;

    // Trigger click
    this._triggerEl.addEventListener('click', function(e) {
      e.stopPropagation();
      if (self._isOpen) self.close();
      else self.open();
    });

    // Calendar click delegation
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

      // Nav buttons
      if (target.classList.contains('datepicker-prev-month')) {
        self._viewMonth--;
        if (self._viewMonth < 0) { self._viewMonth = 11; self._viewYear--; }
        self._refreshCalendar();
        return;
      }
      if (target.classList.contains('datepicker-next-month')) {
        self._viewMonth++;
        if (self._viewMonth > 11) { self._viewMonth = 0; self._viewYear++; }
        self._refreshCalendar();
        return;
      }
      if (target.classList.contains('datepicker-prev-year')) {
        self._viewYear--;
        self._refreshCalendar();
        return;
      }
      if (target.classList.contains('datepicker-next-year')) {
        self._viewYear++;
        self._refreshCalendar();
        return;
      }

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

    // Keyboard on trigger
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

    // Keyboard on calendar
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

    // Click outside
    document.addEventListener('click', function(e) {
      if (self._isOpen && !self.el.contains(e.target)) {
        self.close();
      }
    });
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

  // ========================= Export =========================
  window.CustomDatePicker = CustomDatePicker;

})();
