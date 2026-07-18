// inbox_send.js — 拆分自 inbox.js（3/5）：高度同步、字数限制、发送、文件附件
// 依赖 inbox_core.js 中定义的全局 InputBox。

InputBox.prototype._syncHeight = function(immediate) {
  var ta = this._el('textarea');
  var vp = this._el('viewport');
  if (!ta || !vp) return;
  var o = this._opts;
  var lh = parseFloat(getComputedStyle(ta).lineHeight) || 24;
  var minH = lh * o.minRows, maxH = lh * o.maxRows;
  ta.style.height = '0px';
  var h = Math.min(maxH, Math.max(minH, ta.scrollHeight));
  ta.style.height = h + 'px';
  vp.style.height = h + 'px';
};

InputBox.prototype._checkLimit = function() {
  var ta = this._el('textarea');
  if (!ta) return;
  this._isOverLimit = ta.value.length > this._opts.limitThreshold;
  var sendBtn = this._el('sendBtn');
  if (sendBtn) {
    var span = sendBtn.querySelector('span');
    if (span) span.textContent = this._isOverLimit ? 'Save as File' : 'Send';
  }
};

InputBox.prototype._doSend = function() {
  var ta = this._el('textarea');
  if (!ta) return;
  var text = ta.value.trim();
  if (this._isOverLimit && text) {
    this._addFile({ name: 'long_text.txt', text: text });
    ta.value = '';
    this._isOverLimit = false;
    this._checkLimit();
    this._syncHeight();
    return;
  }
  if (!text && this._files.length === 0) return;
  if (this._opts.onSend) this._opts.onSend(text, this._files.slice());
  ta.value = '';
  this._files = [];
  this._isOverLimit = false;
  this._checkLimit();
  this._syncHeight();
  this._renderFiles();
  ta.focus();
};

InputBox.prototype._addFile = function(fileOrText) {
  if (fileOrText && typeof fileOrText.text === 'string') {
    this._files.push({ name: fileOrText.name, size: fileOrText.text.length, text: fileOrText.text });
  } else {
    this._files.push({ name: fileOrText.name, size: fileOrText.size, file: fileOrText });
  }
  this._renderFiles();
};

InputBox.prototype._renderFiles = function() {
  var zone = this._el('fileZone');
  var countEl = this._el('fileCount');
  if (!zone) return;
  if (this._files.length === 0) {
    zone.style.display = 'none';
    if (countEl) countEl.style.display = 'none';
    return;
  }
  zone.style.display = 'flex';
  var self = this;
  zone.innerHTML = this._files.map(function(f, i) {
    var sizeStr = f.size > 1024 ? (f.size / 1024).toFixed(1) + ' KB' : f.size + ' B';
    return '<div class="ib-file-card"><span class="ib-file-name">' + f.name + '</span><span class="ib-file-size">' + sizeStr + '</span><button class="ib-file-rm" data-idx="' + i + '">&times;</button></div>';
  }).join('');
  zone.querySelectorAll('.ib-file-rm').forEach(function(btn) {
    btn.addEventListener('click', function() {
      self._files.splice(parseInt(btn.dataset.idx), 1);
      self._renderFiles();
    });
  });
  if (countEl) { countEl.style.display = ''; countEl.textContent = this._files.length + ' file(s)'; }
};
