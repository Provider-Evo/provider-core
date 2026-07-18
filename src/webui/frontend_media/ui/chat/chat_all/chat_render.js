// ========================= Simple Streaming Renderer =========================
function renderStreamingContent(text) {
  var codeBlocks = [];
  var sentinel = '\x00CB';
  var codeBlockRegex = /```(\w*)\n([\s\S]*?)```/g;
  var processed = text.replace(codeBlockRegex, function(match, lang, code) {
    var idx = codeBlocks.length;
    codeBlocks.push({ lang: lang, code: code });
    return sentinel + idx + sentinel;
  });
  // Handle incomplete code block at end (starts with ``` but no closing ```)
  var incompleteMatch = processed.match(/```(\w*)\n?([\s\S]*)$/);
  var incompleteCode = '';
  if (incompleteMatch && !processed.endsWith('```')) {
    var iLang = incompleteMatch[1] || '';
    var iCode = incompleteMatch[2] || '';
    var iIdx = codeBlocks.length;
    codeBlocks.push({ lang: iLang, code: iCode, incomplete: true });
    processed = processed.substring(0, incompleteMatch.index) + sentinel + iIdx + sentinel;
  }
  processed = escapeHtml(processed);
  processed = processed.replace(/\n/g, '<br>');
  for (var j = 0; j < codeBlocks.length; j++) {
    var cb = codeBlocks[j];
    var escapedCode = escapeHtml(cb.code);
    processed = processed.replace(sentinel + j + sentinel,
      '<pre class="chat-codeblock"><code>' + escapedCode + '</code></pre>');
  }
  return processed;
}

// ========================= Code Block Rendering =========================
/**
 * Render inline markdown (bold, italic, inline code, links).
 * Input should already be HTML-escaped. Code blocks are extracted before calling this.
 */
function renderInlineMarkdown(text) {
  // Protect inline code first
  var inlineCodes = [];
  text = text.replace(/`([^`\n]+)`/g, function(m, code) {
    var idx = inlineCodes.length;
    inlineCodes.push(code);
    return '\x00IC' + idx + '\x00';
  });
  // Bold: **text**
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  // Italic: *text*
  text = text.replace(/(?<![&\w])\*([^*\n]+)\*/g, '<em>$1</em>');
  // Links: [text](url)
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" style="color:var(--accent);text-decoration:underline;">$1</a>');
  // Restore inline code
  for (var i = 0; i < inlineCodes.length; i++) {
    text = text.replace('\x00IC' + i + '\x00', '<code class="chat-inline-code">' + inlineCodes[i] + '</code>');
  }
  return text;
}

/**
 * 将包含 ```code``` 块的文本转换为 HTML，支持 markdown 渲染。
 * @param {string} text - 原始文本
 * @returns {string} HTML 字符串
 */
var _codeBlockStore = [];

function _wrapCodeBlockPreviewHtml(raw) {
  var trimmed = String(raw || '').replace(/^﻿/, '').trim();
  if (/^<!DOCTYPE\s+html/i.test(trimmed) || /^<html[\s>]/i.test(trimmed)) {
    return trimmed;
  }
  return '<!DOCTYPE html><html><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<style>html,body{margin:0;padding:8px;overflow:auto;background:#fff;color:#111;word-wrap:break-word;}' +
    'img,video,canvas,svg,table{max-width:100%;height:auto;}</style></head><body>' +
    trimmed + '</body></html>';
}

function _clearCodeBlockPreview(previewDiv) {
  if (!previewDiv) return;
  var oldUrl = previewDiv.getAttribute('data-preview-blob');
  if (oldUrl) {
    URL.revokeObjectURL(oldUrl);
    previewDiv.removeAttribute('data-preview-blob');
  }
  while (previewDiv.firstChild) {
    previewDiv.removeChild(previewDiv.firstChild);
  }
}

function _renderCodeBlockPreview(previewDiv, raw) {
  _clearCodeBlockPreview(previewDiv);
  var frame = document.createElement('iframe');
  frame.className = 'chat-codeblock-preview-frame';
  frame.setAttribute('sandbox', '');
  frame.setAttribute('referrerpolicy', 'no-referrer');
  frame.setAttribute('loading', 'lazy');
  frame.setAttribute('title', 'HTML preview');
  frame.setAttribute('tabindex', '-1');
  var blob = new Blob([_wrapCodeBlockPreviewHtml(raw)], { type: 'text/html;charset=utf-8' });
  var blobUrl = URL.createObjectURL(blob);
  previewDiv.setAttribute('data-preview-blob', blobUrl);
  frame.src = blobUrl;
  previewDiv.appendChild(frame);
}

function _renderBlockMarkdownLines(processed) {
  // Process block-level markdown on each line
  var lines = processed.split('\n');
  var resultLines = [];
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    var hMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (hMatch) {
      var level = hMatch[1].length;
      var sizes = { 1: '1.4em', 2: '1.25em', 3: '1.1em', 4: '1em', 5: '0.95em', 6: '0.9em' };
      resultLines.push('<h' + level + ' style="margin:8px 0 4px;font-size:' + sizes[level] + ';font-weight:bold;">' + renderInlineMarkdown(hMatch[2]) + '</h' + level + '>');
      continue;
    }
    var ulMatch = line.match(/^(\s*)[*-]\s+(.+)$/);
    if (ulMatch) {
      var indent = Math.floor(ulMatch[1].length / 2);
      resultLines.push('<div style="padding-left:' + (indent * 20 + 16) + 'px;">• ' + renderInlineMarkdown(ulMatch[2]) + '</div>');
      continue;
    }
    var olMatch = line.match(/^(\s*)(\d+)[.)]\s+(.+)$/);
    if (olMatch) {
      var indent2 = Math.floor(olMatch[1].length / 2);
      resultLines.push('<div style="padding-left:' + (indent2 * 20 + 16) + 'px;">' + olMatch[2] + '. ' + renderInlineMarkdown(olMatch[3]) + '</div>');
      continue;
    }
    resultLines.push(renderInlineMarkdown(line));
  }
  return resultLines.join('\n');
}

function _restoreCodeBlocks(processed, codeBlocks, sentinel) {
  // Restore code blocks — store raw code in JS Map, render with collapse/expand
  for (var j = 0; j < codeBlocks.length; j++) {
    var cb = codeBlocks[j];
    var storeIdx = _codeBlockStore.length;
    _codeBlockStore.push(cb.code);
    var langClass = cb.lang ? ' class="language-' + cb.lang.toLowerCase() + '"' : '';
    var langLabel = cb.lang ? cb.lang.toLowerCase() : 'code';
    var escapedCode = escapeHtml(cb.code);
    var tabsHtml = '';
    if (cb.lang && cb.lang.toLowerCase() === 'html') {
      tabsHtml =
        '<div class="chat-codeblock-tabs">' +
          '<button class="chat-codeblock-tab is-active" data-tab="code" type="button">code</button>' +
          '<button class="chat-codeblock-tab" data-tab="preview" type="button">preview</button>' +
        '</div>';
    }
    var blockHtml =
      '<div class="chat-codeblock-wrapper">' +
        '<div class="chat-codeblock-header">' +
          '<span class="chat-codeblock-lang">' + langLabel + '</span>' +
          tabsHtml +
          '<button class="chat-codeblock-copy" type="button">' + escapeHtml(t('common.copy')) + '</button>' +
          '<button class="chat-codeblock-collapse" type="button" title="' + escapeHtml(t('chat.collapseExpand')) + '">▲</button>' +
        '</div>' +
        '<div class="chat-codeblock-body">' +
          '<pre class="chat-codeblock" data-cb-index="' + storeIdx + '"><code' + langClass + '>' + escapedCode + '</code></pre>' +
          '<div class="chat-codeblock-preview" data-cb-index="' + storeIdx + '" style="display:none;"></div>' +
        '</div>' +
      '</div>';
    processed = processed.replace(sentinel + j + sentinel, blockHtml);
  }
  return processed;
}

function renderWithCodeBlocks(text) {
  // Extract code blocks first (protect from escaping and markdown)
  var codeBlocks = [];
  var sentinel = '\x00CB';
  var codeBlockRegex = /```(\w*)\n([\s\S]*?)```/g;
  var processed = text.replace(codeBlockRegex, function(match, lang, code) {
    var idx = codeBlocks.length;
    codeBlocks.push({ lang: lang, code: code });
    return sentinel + idx + sentinel;
  });

  // Escape HTML in remaining text
  processed = escapeHtml(processed);

  processed = _renderBlockMarkdownLines(processed);

  processed = processed.replace(/\n/g, function(match, offset) {
    var before = processed.substring(Math.max(0, offset - 30), offset);
    if (/<\/(h[1-6]|div|pre|ul|ol|li|table|blockquote)>\s*$/.test(before)) {
      return '';
    }
    return '<br>';
  });

  processed = _restoreCodeBlocks(processed, codeBlocks, sentinel);

  return processed;
}

// ========================= File Card Helpers =========================
function formatFileSize(bytes) {
  if (bytes == null || bytes < 0) return '0 B';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
}

var _IMAGE_EXT_MIMES = {
  jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png',
  gif: 'image/gif', webp: 'image/webp', bmp: 'image/bmp', svg: 'image/svg+xml',
};

function getFileIcon(name) {
  var ext = (name || '').split('.').pop().toLowerCase();
  var icons = {
    pdf: '\u{1F4C4}', doc: '\u{1F4C4}', docx: '\u{1F4C4}',
    xls: '\u{1F4CA}', xlsx: '\u{1F4CA}', csv: '\u{1F4CA}',
    png: '\u{1F5BC}', jpg: '\u{1F5BC}', jpeg: '\u{1F5BC}', gif: '\u{1F5BC}', svg: '\u{1F5BC}', webp: '\u{1F5BC}',
    mp3: '\u{1F3B5}', wav: '\u{1F3B5}', ogg: '\u{1F3B5}', flac: '\u{1F3B5}',
    mp4: '\u{1F3AC}', avi: '\u{1F3AC}', mkv: '\u{1F3AC}', mov: '\u{1F3AC}',
    zip: '\u{1F4E6}', rar: '\u{1F4E6}', '7z': '\u{1F4E6}', tar: '\u{1F4E6}', gz: '\u{1F4E6}',
    js: '\u{1F4DC}', ts: '\u{1F4DC}', py: '\u{1F4DC}', html: '\u{1F4DC}', css: '\u{1F4DC}', json: '\u{1F4DC}',
    txt: '\u{1F4DD}', md: '\u{1F4DD}', log: '\u{1F4DD}',
  };
  return icons[ext] || '\u{1F4CE}';
}

function buildFileCardsHtml(files) {
  if (!files || !files.length) return '';
  var html = '<div class="chat-file-cards">';
  for (var i = 0; i < files.length; i++) {
    var f = files[i];
    html += '<div class="chat-file-card">'
      + '<span class="chat-file-icon">' + getFileIcon(f.name) + '</span>'
      + '<span class="chat-file-info">'
      + '<span class="chat-file-name">' + escapeHtml(f.name) + '</span>'
      + '<span class="chat-file-size">' + formatFileSize(f.size) + '</span>'
      + '</span></div>';
  }
  html += '</div>';
  return html;
}

function escapeHtml(text) {
  var div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}
