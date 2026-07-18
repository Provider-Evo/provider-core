// inbox_events.js — 拆分自 inbox.js（2/5）：事件绑定
// 依赖 inbox_core.js 中定义的全局 InputBox。
// 原 _bind 约72行，拆出 _bindTextareaEvents / _bindPasteEvent /
// _bindButtonEvents 三个内部 helper 以满足单函数<=50行。

InputBox.prototype._bind = function() {
  var self = this;
  var ta = this._el('textarea');

  this._bindTextareaEvents(ta);
  this._bindPasteEvent(ta);
  this._bindButtonEvents();

  window.addEventListener('resize', function() { self._syncHeight(true); });
  this._syncHeight(true);
};

InputBox.prototype._bindTextareaEvents = function(ta) {
  var self = this;
  ta.addEventListener('input', function() { self._syncHeight(); self._checkLimit(); });
  ta.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); self._doSend(); }
  });
};

InputBox.prototype._bindPasteEvent = function(ta) {
  var self = this;
  var o = this._opts;

  ta.addEventListener('paste', function(e) {
    var clipboard = e.clipboardData || window.clipboardData;
    if (!clipboard) return;

    var imageItems = [];
    if (clipboard.items && clipboard.items.length) {
      for (var pi = 0; pi < clipboard.items.length; pi++) {
        var item = clipboard.items[pi];
        if (item.kind === 'file' && item.type && item.type.indexOf('image/') === 0) {
          var imageFile = item.getAsFile();
          if (imageFile) imageItems.push(imageFile);
        }
      }
    }

    if (imageItems.length > 0) {
      e.preventDefault();
      for (var ii = 0; ii < imageItems.length; ii++) {
        self._addFile(imageItems[ii]);
      }
      return;
    }

    e.preventDefault();
    var text = clipboard.getData('text');
    if (text.length > o.limitThreshold) {
      self._addFile({ name: 'pasted_text.txt', text: text });
    } else {
      var s = ta.selectionStart, end = ta.selectionEnd;
      ta.value = ta.value.slice(0, s) + text + ta.value.slice(end);
      ta.selectionStart = ta.selectionEnd = s + text.length;
      self._syncHeight();
    }
  });
};

InputBox.prototype._bindButtonEvents = function() {
  var self = this;
  var sendBtn = this._el('sendBtn');
  var fileBtn = this._el('fileBtn');
  var fileInput = this._el('fileInput');
  var voiceBtn = this._el('voiceBtn');

  if (sendBtn) sendBtn.addEventListener('click', function() { self._doSend(); });

  if (fileBtn && fileInput) {
    fileBtn.addEventListener('click', function() { fileInput.click(); });
    fileInput.addEventListener('change', function() {
      for (var i = 0; i < fileInput.files.length; i++) {
        self._addFile(fileInput.files[i]);
      }
      fileInput.value = '';
    });
  }

  if (voiceBtn) voiceBtn.addEventListener('click', function() { self._toggleVoice(); });
};
