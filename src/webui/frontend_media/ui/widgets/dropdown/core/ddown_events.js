// ddown_events.js — 拆分自 ddown.js（3/5）：事件绑定 + 键盘高亮导航
// 依赖 ddown_core.js 中定义的全局 CustomDropdown。

CustomDropdown.prototype._bindEvents = function () {
  var trigger = this.el.querySelector('.custom-dropdown-trigger');
  var list = this._listEl;
  if (!trigger || !list) return;

  this._bindTriggerEvents(trigger, list);
  this._bindListEvents(trigger, list);
};

CustomDropdown.prototype._bindTriggerEvents = function (trigger, list) {
  var self = this;

  trigger.addEventListener('click', function (e) {
    e.stopPropagation();
    if (self.el.classList.contains('is-open')) self.close();
    else self.open();
  });

  trigger.addEventListener('keydown', function (e) {
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
      default:
        break;
    }
  });
};

CustomDropdown.prototype._bindListEvents = function (trigger, list) {
  var self = this;

  list.addEventListener('click', function (e) {
    var option = e.target.closest('.custom-dropdown-option');
    if (option) {
      self.select(option.getAttribute('data-value'));
      self.close();
    }
  });

  list.addEventListener('keydown', function (e) {
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
      default:
        break;
    }
  });
};

CustomDropdown.prototype._highlightNext = function (delta) {
  var list = this._listEl;
  var allOptions = list.querySelectorAll('.custom-dropdown-option');
  var options = [];
  for (var k = 0; k < allOptions.length; k++) {
    if (allOptions[k].style.display !== 'none') options.push(allOptions[k]);
  }
  if (!options.length) return;
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
