/**
 * File Manager -- editor body rendering (image/binary/error/html/markdown/
 * source views), search/replace within the active tab, and statusbar updates.
 *
 * Part of the files.js split. Depends on editor.js (_editorWin,
 * _editorActiveTab, _editorMarkDirty, _editorFmtLineEnding,
 * _editorDetectLangLabel) and preview.js (_renderHtmlPreviewHost,
 * _renderMarkdownPreviewHtml). Calls into ops.js (_downloadFile).
 */

function _editorGotoLine() {
  var tab = _editorActiveTab();
  if (!tab || !tab.editable) return;
  var lineStr = window.prompt(t('files.gotoLinePrompt'));
  if (!lineStr) return;
  var lineNum = parseInt(lineStr, 10);
  if (!lineNum || lineNum < 1) return;
  var ta = _editorWin.bodyEl.querySelector('.files-editor2-textarea');
  if (!ta) return;
  var lines = ta.value.split('\n');
  var pos = 0;
  for (var i = 0; i < Math.min(lineNum - 1, lines.length); i++) pos += lines[i].length + 1;
  ta.focus();
  ta.setSelectionRange(pos, pos);
  var lineHeight = 1.6 * _editorWin.fontSize;
  ta.scrollTop = Math.max(0, (lineNum - 3) * lineHeight);
  _editorUpdateCursorStatus(ta);
}

function _editorSearchMatches(text, query) {
  var matches = [];
  if (!query) return matches;
  var lower = text.toLowerCase();
  var q = query.toLowerCase();
  var idx = 0;
  while (true) {
    var found = lower.indexOf(q, idx);
    if (found === -1) break;
    matches.push(found);
    idx = found + q.length;
  }
  return matches;
}

function _editorSearchRefresh() {
  var win = _editorWin;
  var tab = _editorActiveTab();
  var input = win.overlay.querySelector('#filesEditorSearchInput');
  var countEl = win.overlay.querySelector('#filesEditorSearchCount');
  if (!tab || !tab.editable) { countEl.textContent = ''; return; }
  var ta = win.bodyEl.querySelector('.files-editor2-textarea');
  var query = input.value;
  tab._searchQuery = query;
  tab._searchMatches = ta ? _editorSearchMatches(ta.value, query) : [];
  tab._searchIdx = tab._searchMatches.length > 0 ? 0 : -1;
  countEl.textContent = tab._searchMatches.length > 0
    ? (tab._searchIdx + 1) + '/' + tab._searchMatches.length
    : (query ? t('files.noSearchResults') : '');
  if (tab._searchIdx >= 0) _editorSearchApplySelection(tab, ta);
}

function _editorSearchApplySelection(tab, ta) {
  if (!ta || tab._searchIdx < 0) return;
  var start = tab._searchMatches[tab._searchIdx];
  var len = (tab._searchQuery || '').length;
  ta.focus();
  ta.setSelectionRange(start, start + len);
  var linesBefore = ta.value.substring(0, start).split('\n').length;
  var lineHeight = 1.6 * _editorWin.fontSize;
  ta.scrollTop = Math.max(0, (linesBefore - 5) * lineHeight);
}

function _editorSearchStep(dir) {
  var win = _editorWin;
  var tab = _editorActiveTab();
  if (!tab || !tab._searchMatches || tab._searchMatches.length === 0) return;
  tab._searchIdx = (tab._searchIdx + dir + tab._searchMatches.length) % tab._searchMatches.length;
  var ta = win.bodyEl.querySelector('.files-editor2-textarea');
  _editorSearchApplySelection(tab, ta);
  win.overlay.querySelector('#filesEditorSearchCount').textContent = (tab._searchIdx + 1) + '/' + tab._searchMatches.length;
}

function _editorReplaceOne() {
  var win = _editorWin;
  var tab = _editorActiveTab();
  if (!tab || !tab.editable || !tab._searchMatches || tab._searchIdx < 0) return;
  var replaceVal = win.overlay.querySelector('#filesEditorReplaceInput').value;
  var ta = win.bodyEl.querySelector('.files-editor2-textarea');
  var start = tab._searchMatches[tab._searchIdx];
  var len = (tab._searchQuery || '').length;
  ta.value = ta.value.substring(0, start) + replaceVal + ta.value.substring(start + len);
  tab.content = ta.value;
  _editorMarkDirty(tab);
  _editorUpdateLineNumbers(ta);
  _editorUpdateStatusbar(tab);
  _editorSearchRefresh();
}

function _editorReplaceAll() {
  var win = _editorWin;
  var tab = _editorActiveTab();
  if (!tab || !tab.editable) return;
  var query = win.overlay.querySelector('#filesEditorSearchInput').value;
  var replaceVal = win.overlay.querySelector('#filesEditorReplaceInput').value;
  if (!query) return;
  var ta = win.bodyEl.querySelector('.files-editor2-textarea');
  var re = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'gi');
  ta.value = ta.value.replace(re, replaceVal);
  tab.content = ta.value;
  _editorMarkDirty(tab);
  _editorUpdateLineNumbers(ta);
  _editorUpdateStatusbar(tab);
  _editorSearchRefresh();
}

function _editorUpdateCursorStatus(ta) {
  var win = _editorWin;
  var pos = ta.selectionStart;
  var textBefore = ta.value.substring(0, pos);
  var lines = textBefore.split('\n');
  var line = lines.length;
  var col = lines[lines.length - 1].length + 1;
  win.overlay.querySelector('#statusCursor').textContent = 'Ln ' + line + ', Col ' + col;
}

function _editorUpdateStatusbar(tab) {
  var win = _editorWin;
  win.overlay.querySelector('#statusPath').textContent = tab.entry.path;
  win.overlay.querySelector('#statusLineEnding').textContent = _editorFmtLineEnding(tab.content);
  win.overlay.querySelector('#statusChars').textContent = t('files.charCount', { count: (tab.content || '').length });
  win.overlay.querySelector('#statusLanguage').textContent = _editorDetectLangLabel(tab.entry.name);
}

function _editorUpdateLineNumbers(ta) {
  var linesDiv = _editorWin.bodyEl.querySelector('.files-editor2-gutter');
  if (!linesDiv) return;
  var count = (ta.value.match(/\n/g) || []).length + 1;
  var nums = [];
  for (var i = 1; i <= count; i++) nums.push(i);
  linesDiv.textContent = nums.join('\n');
}

function _editorSetupModeToggle(tab, container) {
  if (tab.kind !== 'html' && tab.kind !== 'markdown') return;
  var modes = document.createElement('div');
  modes.className = 'files-editor2-modes';
  var sourceLabel = t('files.viewSource');
  var renderedLabel = tab.kind === 'html' ? t('files.viewPreview') : t('files.viewRendered');
  modes.innerHTML =
    '<button type="button" class="files-editor2-mode' + (tab.viewMode === 'source' ? ' is-active' : '') + '" data-mode="source">' + sourceLabel + '</button>' +
    '<button type="button" class="files-editor2-mode' + (tab.viewMode === 'rendered' ? ' is-active' : '') + '" data-mode="rendered">' + renderedLabel + '</button>';
  modes.querySelectorAll('.files-editor2-mode').forEach(function (btn) {
    btn.addEventListener('click', function () {
      tab.viewMode = btn.getAttribute('data-mode');
      _editorRenderBody();
    });
  });
  container.appendChild(modes);
}

function _editorClearStatusbar(win) {
  win.overlay.querySelector('#statusPath').textContent = '';
  win.overlay.querySelector('#statusLineEnding').textContent = '';
  win.overlay.querySelector('#statusChars').textContent = '';
  win.overlay.querySelector('#statusLanguage').textContent = '';
  win.overlay.querySelector('#statusCursor').textContent = '';
}

function _editorRenderImageBody(win, tab) {
  win.bodyEl.innerHTML =
    '<div class="files-preview-image"><img src="' + tab.content + '" alt="' + _escapeAttr(tab.entry.name) + '"></div>';
  _editorUpdateStatusbar(tab);
}

function _editorRenderBinaryBody(win, tab) {
  win.bodyEl.innerHTML =
    '<div class="files-preview-binary">' +
    '<div style="font-size:48px;opacity:0.5;">&#128196;</div>' +
    '<div>' + t('files.binaryFile', { size: _formatSize(tab.totalSize) }) + '</div>' +
    '<button class="files-preview-btn" type="button" id="filesEditorBinaryDownload">' + t('files.download') + '</button>' +
    '</div>';
  var dl = win.bodyEl.querySelector('#filesEditorBinaryDownload');
  if (dl) dl.addEventListener('click', function () { _downloadFile(tab.entry.path); });
  _editorUpdateStatusbar(tab);
}

function _editorRenderErrorBody(win, tab) {
  win.bodyEl.innerHTML = '<div class="files-preview-binary"><div>' + t('files.loadFileFailed', { error: _escapeHtml(tab.errorMessage) }) + '</div></div>';
}

function _editorBuildRenderWrap(tab) {
  var renderWrap = document.createElement('div');
  renderWrap.className = 'files-editor2-render-wrap';
  if (tab.kind === 'html') {
    var host = document.createElement('div');
    host.className = 'files-preview-html-host';
    renderWrap.appendChild(host);
    tab.htmlHost = host;
    _renderHtmlPreviewHost(host, tab.content);
  } else {
    renderWrap.className += ' files-preview-markdown';
    renderWrap.innerHTML = _renderMarkdownPreviewHtml(tab.content);
    renderWrap.querySelectorAll('pre code').forEach(function (el) {
      if (typeof hljs !== 'undefined') hljs.highlightElement(el);
    });
  }
  return renderWrap;
}

// Renders the rendered (non-source) view for html/markdown tabs.
// Returns true if it fully handled rendering (caller should stop).
function _editorRenderPreviewModeBody(win, tab, wrap) {
  _editorSetupModeToggle(tab, wrap);
  if (tab.viewMode !== 'rendered') return false;
  var renderWrap = _editorBuildRenderWrap(tab);
  wrap.appendChild(renderWrap);
  win.bodyEl.appendChild(wrap);
  _editorUpdateStatusbar(tab);
  return true;
}

function _editorWireTextareaEvents(textarea, gutter, tab) {
  textarea.addEventListener('scroll', function () { gutter.scrollTop = textarea.scrollTop; });
  textarea.addEventListener('input', function () {
    tab.content = textarea.value;
    _editorMarkDirty(tab);
    _editorUpdateLineNumbers(textarea);
    _editorUpdateStatusbar(tab);
  });
  textarea.addEventListener('click', function () { _editorUpdateCursorStatus(textarea); });
  textarea.addEventListener('keyup', function () { _editorUpdateCursorStatus(textarea); });
  textarea.addEventListener('keydown', function (e) {
    if (e.key !== 'Tab') return;
    e.preventDefault();
    var start = textarea.selectionStart;
    var end = textarea.selectionEnd;
    textarea.value = textarea.value.substring(0, start) + '    ' + textarea.value.substring(end);
    textarea.selectionStart = textarea.selectionEnd = start + 4;
    tab.content = textarea.value;
    _editorMarkDirty(tab);
    _editorUpdateLineNumbers(textarea);
  });
}

function _editorRenderSourceBody(win, tab, wrap) {
  var editorDiv = document.createElement('div');
  editorDiv.className = 'files-editor2-editor';

  var gutter = document.createElement('div');
  gutter.className = 'files-editor2-gutter';

  var textarea = document.createElement('textarea');
  textarea.className = 'files-editor2-textarea';
  textarea.spellcheck = false;
  textarea.readOnly = !tab.editable;
  textarea.value = tab.content || '';
  textarea.style.whiteSpace = win.wrap ? 'pre-wrap' : 'pre';

  editorDiv.appendChild(gutter);
  editorDiv.appendChild(textarea);
  wrap.appendChild(editorDiv);
  win.bodyEl.appendChild(wrap);
  win.bodyEl.style.fontSize = win.fontSize + 'px';

  _editorUpdateLineNumbers(textarea);
  _editorWireTextareaEvents(textarea, gutter, tab);

  if (tab.focusOnOpen) {
    textarea.focus();
    tab.focusOnOpen = false;
  }
  _editorUpdateStatusbar(tab);
  _editorUpdateCursorStatus(textarea);
}

function _editorRenderBody() {
  var win = _editorWin;
  var tab = _editorActiveTab();
  win.bodyEl.innerHTML = '';
  _editorClearStatusbar(win);
  if (!tab) {
    win.bodyEl.innerHTML = '<div class="files-editor2-empty">' + t('files.noOpenTabs') + '</div>';
    return;
  }

  if (tab.kind === 'image') { _editorRenderImageBody(win, tab); return; }
  if (tab.kind === 'binary') { _editorRenderBinaryBody(win, tab); return; }
  if (tab.kind === 'error') { _editorRenderErrorBody(win, tab); return; }

  var wrap = document.createElement('div');
  wrap.className = 'files-editor2-content';

  if (tab.kind === 'html' || tab.kind === 'markdown') {
    if (_editorRenderPreviewModeBody(win, tab, wrap)) return;
  }

  _editorRenderSourceBody(win, tab, wrap);
}
