// inbox_api.js — 拆分自 inbox.js（5/5）：公开 API、工厂方法、全局挂载。
// 依赖 inbox_core.js 中定义的全局 InputBox。
// 这是拆分链的最后一个文件：负责把 InputBox 挂载到 window 上。

InputBox.prototype.getText = function() { return (this._el('textarea') || {}).value || ''; };
InputBox.prototype.setText = function(v) { var ta = this._el('textarea'); if (ta) { ta.value = v; this._syncHeight(); } };
InputBox.prototype.getFiles = function() { return this._files.slice(); };
InputBox.prototype.focus = function() { var ta = this._el('textarea'); if (ta) ta.focus(); };

// Factory
InputBox.create = function(container, options) {
  return new InputBox(container, options);
};

window.InputBox = InputBox;
