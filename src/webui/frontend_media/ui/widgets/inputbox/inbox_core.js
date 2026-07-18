/**
 * InputBox — Portable chat input component.
 * Usage: InputBox.create(container, options)
 *
 * Options:
 *   placeholder: string
 *   maxRows / minRows: number
 *   limitThreshold: number (auto-convert to file if text exceeds)
 *   buttons: { file: bool, voice: bool, send: bool }
 *   voice: { sttModel, ttsModel, ttsPrompt, recordingDeviceId }
 *   onSend: function(text, files)
 *   onVoiceStart / onVoiceEnd: function()
 *
 * 拆分自 inbox.js（1/5）：内部状态 + 构造函数 + 基础渲染。
 * 注意：不用 IIFE 包裹——后续 inbox_events.js / inbox_send.js /
 * inputbox_voice.js / inputbox_api.js 需要跨文件继续挂载 prototype 方法，
 * 必须共享同一个全局 InputBox 函数引用。
 */

var _ibUid = 0;

function InputBox(container, opts) {
  opts = opts || {};
  this._id = 'ib' + (++_ibUid);
  this._container = typeof container === 'string' ? document.querySelector(container) : container;
  this._opts = Object.assign({
    placeholder: 'Type a message...',
    maxRows: 6, minRows: 4,
    limitThreshold: 1024,
    buttons: { file: true, voice: true, send: true },
    voice: { sttModel: '', ttsModel: '', ttsPrompt: '', recordingDeviceId: '' },
    onSend: null,
    onVoiceStart: null,
    onVoiceEnd: null,
  }, opts);
  this._files = [];
  this._isOverLimit = false;
  this._isRecording = false;
  this._mediaRecorder = null;
  this._audioChunks = [];
  this._render();
  this._bind();
}

InputBox.prototype._el = function(suffix) {
  return document.getElementById(this._id + '-' + suffix);
};

InputBox.prototype._render = function() {
  var id = this._id;
  var o = this._opts;
  var btns = o.buttons;
  var html = '<div class="ib-root" id="' + id + '-root">';
  // File zone
  html += '<div class="ib-file-zone" id="' + id + '-fileZone" style="display:none;"></div>';
  // Text area
  html += '<div class="ib-viewport" id="' + id + '-viewport" style="height:' + (o.minRows * 24) + 'px;">';
  html += '<textarea class="ib-textarea native-scroll-hidden" id="' + id + '-textarea" placeholder="' + o.placeholder + '" rows="' + o.minRows + '"></textarea>';
  html += '<div class="ib-caret" id="' + id + '-caret"></div>';
  html += '<div class="ib-scrollbar" id="' + id + '-scrollbar"><div class="ib-track"></div><div class="ib-thumb" id="' + id + '-thumb"></div></div>';
  html += '</div>';
  // Button bar
  html += '<div class="ib-bar">';
  html += '<div class="ib-bar-left">';
  if (btns.file) html += '<button class="ib-btn" id="' + id + '-fileBtn" title="Upload file"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z"/></svg></button>';
  if (btns.file) html += '<input type="file" id="' + id + '-fileInput" multiple style="display:none;">';
  if (btns.voice) html += '<button class="ib-btn" id="' + id + '-voiceBtn" title="Voice input"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M12 18.75a6 6 0 006-6v-1.5m-6 7.5a6 6 0 01-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 01-3-3V4.5a3 3 0 116 0v8.25a3 3 0 01-3 3z"/></svg></button>';
  html += '</div>';
  html += '<div class="ib-bar-right">';
  html += '<span class="ib-file-count" id="' + id + '-fileCount" style="display:none;"></span>';
  if (btns.send) html += '<button class="ib-send" id="' + id + '-sendBtn"><span>Send</span><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 12L3.269 3.125A59.769 59.769 0 0121.485 12 59.768 59.768 0 013.27 20.875L5.999 12Zm0 0h7.5"/></svg></button>';
  html += '</div></div></div>';
  this._container.innerHTML = html;
};
