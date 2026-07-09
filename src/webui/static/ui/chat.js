// Chat input handled by InputBox component (input-box.js)

// Clipboard helper with fallback for insecure contexts (HTTP)
function _chatCopyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text);
  }
  var textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  textarea.style.top = '-9999px';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  var success = false;
  try {
    success = document.execCommand('copy');
  } catch (e) {
    console.error('Copy failed:', e);
  }
  document.body.removeChild(textarea);
  return success ? Promise.resolve() : Promise.reject(new Error('Copy failed'));
}

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

// ========================= Tool Parameter Toggle (Global Delegate) =========================
document.addEventListener("click", function(e) {
  var trigger = e.target.closest(".chat-tool-dropdown-trigger");
  if (!trigger) return;
  var targetId = trigger.getAttribute("data-target");
  if (!targetId || !targetId.startsWith("tool-")) return;
  var argsEl = document.getElementById(targetId);
  var chevron = trigger.querySelector(".chat-tool-chevron");
  var label = trigger.querySelector(".chat-tool-dropdown-label");
  if (argsEl) {
    var isHidden = argsEl.style.display === "none";
    argsEl.style.display = isHidden ? "block" : "none";
    trigger.setAttribute("aria-expanded", isHidden ? "true" : "false");
    if (label) label.textContent = isHidden ? t('chat.collapseParams') : t('chat.viewParams');
    if (chevron) chevron.style.transform = isHidden ? "rotate(180deg)" : "rotate(0deg)";
  }
});

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
  var trimmed = String(raw || '').replace(/^\uFEFF/, '').trim();
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
      resultLines.push('<div style="padding-left:' + (indent * 20 + 16) + 'px;">\u2022 ' + renderInlineMarkdown(ulMatch[2]) + '</div>');
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
  processed = resultLines.join('\n');

  processed = processed.replace(/\n/g, function(match, offset) {
    var before = processed.substring(Math.max(0, offset - 30), offset);
    if (/<\/(h[1-6]|div|pre|ul|ol|li|table|blockquote)>\s*$/.test(before)) {
      return '';
    }
    return '<br>';
  });

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
          '<button class="chat-codeblock-collapse" type="button" title="' + escapeHtml(t('chat.collapseExpand')) + '">\u25B2</button>' +
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

function _fileItemSize(item) {
  if (!item) return 0;
  if (item.file && typeof item.file.size === 'number') return item.file.size;
  if (typeof item.size === 'number') return item.size;
  if (typeof item.text === 'string') return item.text.length;
  return 0;
}

function _isImageAttachment(name, mime) {
  if (mime && mime.indexOf('image/') === 0) return true;
  var ext = (name || '').split('.').pop().toLowerCase();
  return Object.prototype.hasOwnProperty.call(_IMAGE_EXT_MIMES, ext);
}

function _isCorruptFileTextPart(text) {
  return typeof text === 'string'
    && text.indexOf('[file:') === 0
    && text.indexOf('function text() { [native code] }') !== -1;
}

function _userDisplayText(content) {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return String(content || '');
  var texts = [];
  for (var i = 0; i < content.length; i++) {
    var part = content[i];
    if (!part || typeof part !== 'object') continue;
    if (part.type === 'text' && typeof part.text === 'string') {
      if (_isCorruptFileTextPart(part.text)) {
        var m = part.text.match(/^\[file:\s*([^\]]+)\]/);
        if (m) texts.push('[image: ' + m[1].trim() + ']');
        continue;
      }
      texts.push(part.text);
    } else if (part.type === 'image_url' || part.type === 'file') {
      // media shown as attachment cards / thumbnails outside the text bubble
    }
  }
  return texts.join('\n');
}

function _readBlobAsDataUrl(blob) {
  return new Promise(function(resolve, reject) {
    var reader = new FileReader();
    reader.onload = function() { resolve(String(reader.result || '')); };
    reader.onerror = function() { reject(new Error('read file failed')); };
    reader.readAsDataURL(blob);
  });
}

async function _buildUserMessageContent(text, files) {
  var parts = [];
  var trimmed = (text || '').trim();
  if (trimmed) parts.push({ type: 'text', text: trimmed });

  if (!files || !files.length) {
    return trimmed;
  }

  for (var i = 0; i < files.length; i++) {
    var item = files[i];
    if (typeof item.text === 'string') {
      parts.push({ type: 'text', text: '[file: ' + item.name + ']\n' + item.text });
      continue;
    }
    var blob = item.file || item;
    if (!(blob instanceof Blob)) continue;

    var mime = blob.type || _IMAGE_EXT_MIMES[(item.name || '').split('.').pop().toLowerCase()] || 'application/octet-stream';
    var dataUrl = await _readBlobAsDataUrl(blob);
    if (_isImageAttachment(item.name, mime)) {
      parts.push({ type: 'image_url', image_url: { url: dataUrl } });
    } else {
      parts.push({
        type: 'file',
        file: { filename: item.name || 'attachment', data: dataUrl },
      });
    }
  }

  if (parts.length === 1 && parts[0].type === 'text') return parts[0].text;
  return parts;
}

var _STRIPPED_MEDIA_MARKER = '[stripped]';
var _chatAbortReason = null;
var _saveChatStateTimer = null;

function _isStrippedMediaUrl(url) {
  return !url || url === _STRIPPED_MEDIA_MARKER;
}

function _contentHasMedia(content) {
  if (!Array.isArray(content)) return false;
  for (var i = 0; i < content.length; i++) {
    var p = content[i];
    if (!p || typeof p !== 'object') continue;
    if (p.type === 'image_url' || p.type === 'file' || p.type === 'video_url' || p.type === 'input_audio') {
      return true;
    }
  }
  return false;
}

function _stripContentPartForPersist(part) {
  if (!part || typeof part !== 'object') return part;
  var copy = Object.assign({}, part);
  if (copy.type === 'image_url' && copy.image_url) {
    copy.image_url = Object.assign({}, copy.image_url, { url: _STRIPPED_MEDIA_MARKER });
  } else if (copy.type === 'video_url' && copy.video_url) {
    copy.video_url = Object.assign({}, copy.video_url, { url: _STRIPPED_MEDIA_MARKER });
  } else if (copy.type === 'input_audio' && copy.input_audio) {
    copy.input_audio = Object.assign({}, copy.input_audio, { data: _STRIPPED_MEDIA_MARKER });
  } else if (copy.type === 'file' && copy.file) {
    copy.file = Object.assign({}, copy.file, { data: _STRIPPED_MEDIA_MARKER });
  }
  return copy;
}

function _stripContentForPersist(content) {
  if (typeof content === 'string') return content;
  if (!Array.isArray(content)) return content;
  var out = [];
  for (var i = 0; i < content.length; i++) out.push(_stripContentPartForPersist(content[i]));
  return out;
}

function _historyHasStrippedMedia(entry) {
  if (!entry || entry.role !== 'user') return false;
  var content = entry.content;
  if (!Array.isArray(content)) return false;
  for (var i = 0; i < content.length; i++) {
    var p = content[i];
    if (!p || typeof p !== 'object') continue;
    if (p.type === 'image_url' && _isStrippedMediaUrl((p.image_url || {}).url)) return true;
    if (p.type === 'file' && _isStrippedMediaUrl((p.file || {}).data)) return true;
  }
  return false;
}

function _cloneHistoryForPersist(history) {
  return history.map(function(m) {
    var copy = { role: m.role };
    if (m.content !== undefined) copy.content = _stripContentForPersist(m.content);
    if (m.reasoning_content) copy.reasoning_content = m.reasoning_content;
    if (m.tool_calls) copy.tool_calls = m.tool_calls;
    if (m.tool_call_id) copy.tool_call_id = m.tool_call_id;
    if (m.files) copy.files = m.files;
    return copy;
  });
}

async function _exportHistoryForPersist(history) {
  if (typeof ChatMediaPersist !== 'undefined' && ChatMediaPersist.exportHistory) {
    return await ChatMediaPersist.exportHistory(history);
  }
  return _cloneHistoryForPersist(history);
}

async function _hydrateHistoryForDisplay(history) {
  if (!history || !history.length) return [];
  if (typeof ChatMediaPersist !== 'undefined' && ChatMediaPersist.hydrateHistory) {
    return await ChatMediaPersist.hydrateHistory(history);
  }
  return history;
}

function _renderChatHistoryFromMemory() {
  var container = document.getElementById("chatMessagesContainer");
  if (!container) return;
  container.innerHTML = '';
  _userMsgCount = 0;
  for (var i = 0; i < chatConversationHistory.length; i++) {
    var msg = chatConversationHistory[i];
    if (msg.role === "tool") continue;
    try {
      appendChatMessage(msg.role, _userDisplayText(msg.content), {
        historyIndex: msg.role === "user" ? i : undefined,
        toolCalls: msg.tool_calls,
        files: msg.files || null,
        messageContent: msg.role === "user" ? msg.content : null,
        reasoning_content: msg.reasoning_content || ""
      });
    } catch (renderErr) {
      console.error('[_renderChatHistoryFromMemory] Failed to render message', i, msg.role, renderErr);
    }
  }
  _userMsgCount = _countUserMessages(chatConversationHistory);
}

function _prepareMessagesForApi(messages) {
  var out = [];
  for (var i = 0; i < messages.length; i++) {
    var m = messages[i];
    var msg = { role: m.role, content: m.content };
    if (m.role === 'assistant' && m.tool_calls && m.tool_calls.length) {
      msg.tool_calls = m.tool_calls;
    }
    if (m.role === 'tool') {
      msg.tool_call_id = m.tool_call_id;
      msg.content = m.content;
    }
    out.push(msg);
  }
  return out;
}

function _countUserMessages(history) {
  var n = 0;
  for (var i = 0; i < history.length; i++) {
    if (history[i].role === 'user') n++;
  }
  return n;
}

function _resolveUserTurn(el) {
  if (!el || !el.classList) return null;
  if (el.classList.contains("chat-user-turn")) return el;
  if (el.classList.contains("chat-message-user")) {
    var parent = el.parentElement;
    if (parent && parent.classList.contains("chat-user-turn")) return parent;
  }
  return null;
}

function _findPrevUserTurn(fromEl) {
  var el = fromEl;
  while (el) {
    el = el.previousElementSibling;
    if (!el) return null;
    if (el.id === "_chatSpinner") continue;
    if (el.classList.contains("chat-user-turn")) return el;
    if (el.classList.contains("chat-message-user")) return _resolveUserTurn(el) || el;
  }
  return null;
}

function _resolveUserHistoryEntry(turn) {
  if (!turn) return null;
  var idx = parseInt(turn.getAttribute("data-history-index"), 10);
  if (!isNaN(idx) && chatConversationHistory[idx] && chatConversationHistory[idx].role === "user") {
    return { entry: chatConversationHistory[idx], historyIndex: idx };
  }
  for (var i = chatConversationHistory.length - 1; i >= 0; i--) {
    if (chatConversationHistory[i].role === "user") {
      turn.setAttribute("data-history-index", String(i));
      return { entry: chatConversationHistory[i], historyIndex: i };
    }
  }
  return null;
}

function _removeMessagesFromDom(startMsg) {
  var container = document.getElementById("chatMessagesContainer");
  if (!container || !startMsg) return;
  var start = _resolveUserTurn(startMsg) || startMsg;
  var children = Array.prototype.slice.call(container.children);
  var found = false;
  for (var i = 0; i < children.length; i++) {
    if (children[i] === start) found = true;
    if (found) children[i].remove();
  }
}

function _truncateHistoryFrom(historyIndex) {
  chatConversationHistory = chatConversationHistory.slice(0, historyIndex);
  _userMsgCount = _countUserMessages(chatConversationHistory);
}

function _cancelActiveStreaming() {
  var msg = document.getElementById("chatStreamingMessage");
  if (msg) msg.remove();
  _removeChatSpinner();
}

function _mergeUserTextContent(newText, oldContent) {
  var mediaParts = [];
  if (Array.isArray(oldContent)) {
    for (var i = 0; i < oldContent.length; i++) {
      var p = oldContent[i];
      if (!p || typeof p !== 'object') continue;
      if (p.type === 'image_url' || p.type === 'file') mediaParts.push(p);
    }
  }
  if (!mediaParts.length) return (newText || '').trim();
  var parts = [];
  var trimmed = (newText || '').trim();
  if (trimmed) parts.push({ type: 'text', text: trimmed });
  for (var j = 0; j < mediaParts.length; j++) parts.push(mediaParts[j]);
  if (parts.length === 1 && parts[0].type === 'text') return parts[0].text;
  return parts;
}

function _buildUserAttachmentsHtml(options) {
  if (typeof ChatAttachments !== 'undefined' && ChatAttachments.buildHtml) {
    return ChatAttachments.buildHtml(
      options.messageContent != null ? options.messageContent : null,
      options.files || null
    );
  }
  var html = '';
  if (options.files && options.files.length) {
    html += buildFileCardsHtml(options.files);
  }
  if (options.messageContent != null) {
    html += _buildUserImagesHtml(options.messageContent);
  }
  return html;
}

function _ensureUserTurnAttachments(turn, options) {
  var att = turn.querySelector(".chat-user-attachments");
  if (typeof ChatAttachments !== 'undefined' && ChatAttachments.mountInto) {
    var msgContent = options.messageContent != null ? options.messageContent : null;
    var files = options.files || null;
    var items = ChatAttachments.collectAttachments(msgContent, files);
    if (!items.length) {
      if (att) att.remove();
      return;
    }
    if (!att) {
      att = document.createElement("div");
      att.className = "chat-user-attachments";
      var actions = turn.querySelector(".chat-msg-actions");
      var bubble = turn.querySelector(".chat-message-user");
      if (actions) turn.insertBefore(att, actions);
      else if (bubble) turn.insertBefore(att, bubble);
      else turn.appendChild(att);
    }
    ChatAttachments.mountInto(att, turn, msgContent, files);
    return;
  }
  var attachmentsHtml = _buildUserAttachmentsHtml(options);
  if (!attachmentsHtml) {
    if (att) att.remove();
    return;
  }
  if (!att) {
    att = document.createElement("div");
    att.className = "chat-user-attachments";
    var actions = turn.querySelector(".chat-msg-actions");
    if (actions) turn.insertBefore(att, actions);
    else turn.appendChild(att);
  }
  att.innerHTML = attachmentsHtml;
}

function _setUserTurnBubble(turn, displayText) {
  var bubble = turn.querySelector(".chat-message-user");
  if (!displayText) {
    if (bubble) bubble.remove();
    return null;
  }
  if (!bubble) {
    bubble = document.createElement("div");
    bubble.className = "chat-message chat-message-user";
    var att = turn.querySelector(".chat-user-attachments");
    var actions = turn.querySelector(".chat-msg-actions");
    if (att) turn.insertBefore(bubble, att.nextSibling);
    else if (actions) turn.insertBefore(bubble, actions);
    else turn.appendChild(bubble);
  }
  bubble.innerHTML = escapeHtml(displayText);
  return bubble;
}

function _restoreUserMessageHtml(turnOrMsg, displayText, filesJson, messageContent) {
  var turn = _resolveUserTurn(turnOrMsg) || turnOrMsg;
  if (!turn.classList.contains("chat-user-turn")) {
    var legacyHtml = displayText ? escapeHtml(displayText) : '';
    turn.innerHTML = legacyHtml;
    return;
  }
  var files = null;
  if (filesJson) {
    try { files = JSON.parse(filesJson); } catch (e) { files = null; }
  }
  turn.setAttribute("data-raw", displayText || "");
  _ensureUserTurnAttachments(turn, { files: files, messageContent: messageContent });
  _setUserTurnBubble(turn, displayText);
}

async function _resendUserHistoryEntry(entry, newText) {
  if (!entry || entry.role !== 'user') return;
  if (_historyHasStrippedMedia(entry)) {
    toast(_tOr('chat.mediaNotRestored', '图片附件未从持久化恢复，请重新上传后发送'), 'warn');
    var fallbackText = newText != null ? newText : _userDisplayText(entry.content);
    if (fallbackText && String(fallbackText).trim()) {
      await sendChatMessage(fallbackText, null);
    }
    return;
  }
  var content = newText != null ? _mergeUserTextContent(newText, entry.content) : entry.content;
  if (!content || (typeof content === 'string' && !content.trim() && !_contentHasMedia(content))) return;
  await sendChatMessage(_userDisplayText(content), null, {
    presetContent: content,
    presetFiles: entry.files || null,
  });
}

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

function _buildUserImagesHtml(messageContent) {
  if (!Array.isArray(messageContent)) return '';
  var html = '';
  for (var i = 0; i < messageContent.length; i++) {
    var part = messageContent[i];
    if (!part || part.type !== 'image_url' || !part.image_url) continue;
    var url = part.image_url.url;
    if (_isStrippedMediaUrl(url)) continue;
    html += '<div class="chat-user-image"><img src="' + escapeHtml(url) + '" alt="image"></div>';
  }
  return html;
}

// ========================= Chat Message Rendering =========================
var _userMsgCount = 0;
var _toolIdCounter = 0;

function _buildToolCallsHtml(toolCalls) {
  var msgUid = ++_toolIdCounter;
  var html = '<div class="chat-tools-container">';
  for (var i = 0; i < toolCalls.length; i++) {
    var tc = toolCalls[i];
    var name = (tc.function && tc.function.name) || "unknown";
    var args = (tc.function && tc.function.arguments) || "";
    var toolId = "tool-" + msgUid + "-" + i;
    var formattedArgs = "";
    try {
      formattedArgs = JSON.stringify(JSON.parse(args), null, 2);
    } catch(e) {
      formattedArgs = args || "{}";
    }
    html += '<div class="chat-tool-dropdown">';
    html += '<div class="chat-tool-dropdown-trigger" data-target="' + toolId + '">';
    html += '<span class="chat-tool-btn">' + escapeHtml(name) + '</span> ';
    html += '<span class="chat-tool-dropdown-label">' + escapeHtml(t('chat.viewParams')) + '</span>';
    html += '<svg class="chat-tool-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>';
    html += '</div>';
    html += '<pre class="chat-tool-args" id="' + toolId + '" style="display:none;">' + escapeHtml(formattedArgs) + '</pre>';
    html += '</div>';
  }
  html += '</div>';
  return html;
}

function _buildReasoningHtml(reasoning, isOpen) {
  if (!reasoning) return "";
  var open = isOpen !== false;
  return '<div class="chat-reasoning-block' + (open ? " is-open" : "") + '" role="button" tabindex="0" aria-expanded="' + (open ? "true" : "false") + '">'
    + '<div class="chat-reasoning-header">'
    + '<svg class="chat-reasoning-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>'
    + '<span class="chat-reasoning-title">' + escapeHtml(t('chat.thinking')) + '</span>'
    + '</div>'
    + '<div class="chat-reasoning-content">' + escapeHtml(reasoning) + "</div>"
    + "</div>";
}

function _toggleReasoningBlock(block) {
  if (!block) return;
  var open = block.classList.toggle("is-open");
  block.setAttribute("aria-expanded", open ? "true" : "false");
}

function _assistantMessageHtml(content, options) {
  options = options || {};
  var html = "";
  if (options.reasoning_content) {
    html += _buildReasoningHtml(options.reasoning_content);
  }
  if (options.toolCalls && options.toolCalls.length > 0) {
    html += _buildToolCallsHtml(options.toolCalls);
  }
  html += '<div class="chat-assistant-text">' + renderWithCodeBlocks(content || "") + "</div>";
  return html;
}

function appendChatMessage(role, content, options) {
  options = options || {};
  var container = document.getElementById("chatMessagesContainer");
  if (!container) return;

  if (role === "user") {
    var historyIndex = options.historyIndex != null
      ? options.historyIndex
      : Math.max(0, chatConversationHistory.length - 1);
    var displayText = typeof content === 'string' ? content : _userDisplayText(content);
    var turn = document.createElement("div");
    turn.className = "chat-user-turn";
    turn.setAttribute("data-history-index", String(historyIndex));
    turn.setAttribute("data-raw", displayText || "");
    if (options.files && options.files.length > 0) {
      turn.setAttribute("data-files", JSON.stringify(options.files));
    }
    _ensureUserTurnAttachments(turn, {
      files: options.files,
      messageContent: options.messageContent != null ? options.messageContent : content,
    });
    if (displayText) {
      _setUserTurnBubble(turn, displayText);
    }
    container.appendChild(turn);
    if (!options.isStreaming) appendMessageActions(role, turn);
    container.scrollTop = container.scrollHeight;
    return turn;
  }

  var msg = document.createElement("div");
  msg.className = "chat-message chat-message-" + role;
  if (options.toolCalls && options.toolCalls.length > 0 && role !== "assistant") {
    var toolHtml = _buildToolCallsHtml(options.toolCalls);
    msg.innerHTML = toolHtml + '<div class="chat-assistant-text">' + renderWithCodeBlocks(content) + '</div>';
  } else if (role === "assistant") {
    msg.setAttribute("data-raw", content || "");
    if (options.reasoning_content) {
      msg.setAttribute("data-reasoning", options.reasoning_content);
    }
    msg.innerHTML = _assistantMessageHtml(content, options);
  } else if (role === "system") {
    msg.className = "chat-message chat-message-system";
    msg.style.cssText = "background:rgba(255,180,0,0.12);border-left:3px solid #e6a817;color:#b8860b;padding:8px 12px;border-radius:6px;font-size:13px;margin:6px 0;";
    msg.textContent = content;
  } else {
    msg.textContent = content;
  }
  if (options.isStreaming) {
    msg.id = "chatStreamingMessage";
  }
  container.appendChild(msg);
  if (role === "assistant" && !options.isStreaming) {
    appendMessageActions(role, msg);
  }
  container.scrollTop = container.scrollHeight;
  return msg;
}

var _spinnerCreatedAt = 0;
var _SPINNER_MIN_MS = 400;
var _pendingContent = null;
var _pendingTimer = null;

function _removeChatSpinner() {
  var s = document.getElementById("_chatSpinner");
  if (s) s.remove();
  if (_pendingTimer) { clearTimeout(_pendingTimer); _pendingTimer = null; _pendingContent = null; }
}

function _ensureStreamingMessage() {
  var msg = document.getElementById("chatStreamingMessage");
  if (msg) return msg;
  var spinner = document.getElementById("_chatSpinner");
  msg = document.createElement("div");
  msg.className = "chat-message chat-message-assistant";
  msg.id = "chatStreamingMessage";
  var container = document.getElementById("chatMessagesContainer");
  if (spinner && container) {
    container.insertBefore(msg, spinner);
  } else if (container) {
    container.appendChild(msg);
  }
  if (spinner) {
    var span = spinner.querySelector(".chat-loading-spinner");
    if (span) span.childNodes[span.childNodes.length - 1].textContent = t('chat.generating');
  }
  return msg;
}

function _ensureAssistantTextEl(msg) {
  var el = msg.querySelector(".chat-assistant-text");
  if (!el) {
    el = document.createElement("div");
    el.className = "chat-assistant-text";
    msg.appendChild(el);
  }
  return el;
}

function _applyStreamingContent(msg, content) {
  if (!msg || !content) return;
  var textEl = _ensureAssistantTextEl(msg);
  textEl.innerHTML = renderStreamingContent(content);
  msg.setAttribute("data-raw", content);
}

function updateStreamingMessage(content) {
  if (!content) return;
  var msg = _ensureStreamingMessage();
  if (!msg) return;

  var elapsed = Date.now() - _spinnerCreatedAt;
  if (elapsed < _SPINNER_MIN_MS) {
    _pendingContent = content;
    if (!_pendingTimer) {
      _pendingTimer = setTimeout(function() {
        _pendingTimer = null;
        var m = document.getElementById("chatStreamingMessage");
        if (m && _pendingContent) {
          _applyStreamingContent(m, _pendingContent);
        }
        _pendingContent = null;
        var c = document.getElementById("chatMessagesContainer");
        if (c) c.scrollTop = c.scrollHeight;
      }, _SPINNER_MIN_MS - elapsed);
    }
    return;
  }
  _pendingContent = null;
  if (_pendingTimer) { clearTimeout(_pendingTimer); _pendingTimer = null; }
  _applyStreamingContent(msg, content);
  var container = document.getElementById("chatMessagesContainer");
  if (container) container.scrollTop = container.scrollHeight;
}

function updateStreamingReasoning(reasoning) {
  if (!reasoning) return;
  var msg = _ensureStreamingMessage();
  if (!msg) return;
  msg.setAttribute("data-reasoning", reasoning);
  var block = msg.querySelector(".chat-reasoning-block");
  if (!block) {
    var wrapper = document.createElement("div");
    wrapper.innerHTML = _buildReasoningHtml(reasoning, true);
    var node = wrapper.firstChild;
    if (node) {
      msg.insertBefore(node, msg.firstChild);
    }
    return;
  }
  block.setAttribute("aria-expanded", block.classList.contains("is-open") ? "true" : "false");
  var body = block.querySelector(".chat-reasoning-content");
  if (body) body.textContent = reasoning;
  var container = document.getElementById("chatMessagesContainer");
  if (container) container.scrollTop = container.scrollHeight;
}

function finalizeStreamingMessage(toolCalls) {
  var msg = document.getElementById("chatStreamingMessage");
  // If no message element exists but there are tool calls, create one
  if (!msg && toolCalls && toolCalls.length > 0) {
    msg = appendChatMessage("assistant", "", { isStreaming: false });
  }
  if (!msg) { _removeChatSpinner(); return; }
  msg.removeAttribute("id");
  _removeChatSpinner();

  var content = msg.getAttribute("data-raw") || "";
  var reasoning = msg.getAttribute("data-reasoning") || "";

  if (toolCalls && toolCalls.length > 0) {
    msg.innerHTML = _assistantMessageHtml(content, {
      reasoning_content: reasoning,
      toolCalls: toolCalls
    });
    msg.setAttribute("data-raw", content);
    if (reasoning) msg.setAttribute("data-reasoning", reasoning);
  } else if (!content && !reasoning) {
    msg.innerHTML = '';
    msg.setAttribute("data-raw", "");
    msg.removeAttribute("data-reasoning");
  } else {
    msg.innerHTML = _assistantMessageHtml(content, { reasoning_content: reasoning });
    msg.setAttribute("data-raw", content);
    if (reasoning) msg.setAttribute("data-reasoning", reasoning);
  }

  appendMessageActions("assistant", msg);
  saveChatState();
}

function escapeHtml(text) {
  var div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}

function _tOr(key, fallback) {
  var value = t(key);
  return value === key ? fallback : value;
}

document.addEventListener("keydown", function(e) {
  var reasoningBlock = e.target.closest(".chat-reasoning-block");
  if (!reasoningBlock || (e.key !== "Enter" && e.key !== " ")) return;
  e.preventDefault();
  _toggleReasoningBlock(reasoningBlock);
});

document.addEventListener("click", function(e) {
  var reasoningBlock = e.target.closest(".chat-reasoning-block");
  if (reasoningBlock) {
    var sel = window.getSelection();
    if (sel && sel.toString().length > 0) return;
    _toggleReasoningBlock(reasoningBlock);
    return;
  }
  // Code block copy button
  var btn = e.target.closest(".chat-codeblock-copy");
  if (btn) {
    var wrapper = btn.closest('.chat-codeblock-wrapper');
    var pre = wrapper ? wrapper.querySelector('.chat-codeblock') : null;
    var idx = pre ? parseInt(pre.getAttribute('data-cb-index'), 10) : -1;
    var raw = (idx >= 0 && idx < _codeBlockStore.length) ? _codeBlockStore[idx] : (pre ? pre.textContent : '');
    _chatCopyToClipboard(raw).then(function() {
      btn.textContent = t('toast.copied');
      btn.classList.add("is-copied");
      setTimeout(function() {
        btn.textContent = t('common.copy');
        btn.classList.remove("is-copied");
      }, 2000);
    });
    return;
  }

  // Code block collapse/expand toggle
  var collapseBtn = e.target.closest(".chat-codeblock-collapse");
  if (collapseBtn) {
    var wrapper = collapseBtn.closest('.chat-codeblock-wrapper');
    if (!wrapper) return;
    var body = wrapper.querySelector('.chat-codeblock-body');
    if (!body) return;
    var isCollapsed = body.style.display === 'none';
    body.style.display = isCollapsed ? '' : 'none';
    collapseBtn.textContent = isCollapsed ? '\u25B2' : '\u25BC';
    return;
  }

  // Code block preview/code toggle
  var tab = e.target.closest(".chat-codeblock-tab");
  if (tab) {
    var wrapper = tab.closest('.chat-codeblock-wrapper');
    if (!wrapper) return;
    var pre = wrapper.querySelector('.chat-codeblock');
    var previewDiv = wrapper.querySelector('.chat-codeblock-preview');
    var idx = pre ? parseInt(pre.getAttribute('data-cb-index'), 10) : -1;
    var raw = (idx >= 0 && idx < _codeBlockStore.length) ? _codeBlockStore[idx] : '';
    var mode = tab.getAttribute('data-tab');
    wrapper.querySelectorAll('.chat-codeblock-tab').forEach(function(t) {
      t.classList.toggle('is-active', t === tab);
    });
    if (mode === 'code') {
      if (pre) pre.style.display = '';
      if (previewDiv) {
        previewDiv.style.display = 'none';
        _clearCodeBlockPreview(previewDiv);
      }
    } else {
      if (pre) pre.style.display = 'none';
      if (previewDiv) {
        previewDiv.style.display = 'block';
        _renderCodeBlockPreview(previewDiv, raw);
      }
    }
    return;
  }
});

// ========================= Message Actions Component =========================
function appendMessageActions(role, msg) {
  var bar = document.createElement("div");
  bar.className = "chat-msg-actions chat-msg-actions-" + role;
  var allButtons = {
    copy: { title: t('common.copy'), icon:
      '<rect x="9" y="9" width="13" height="13" rx="2"/>' +
      '<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>' },
    edit: { title: t('files.edit'), icon:
      '<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>' +
      '<path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>' },
    retry: { title: t('chat.retry'), icon:
      '<polyline points="23 4 23 10 17 10"/>' +
      '<path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>' }
  };
  var actions = (role === "user") ? ["copy", "edit"] : ["copy", "edit", "retry"];
  var html = "";
  for (var i = 0; i < actions.length; i++) {
    var key = actions[i];
    var b = allButtons[key];
    html += '<button class="chat-msg-action" data-action="' + key + '" data-role="' + role + '" type="button" title="' + b.title + '">' +
      '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + b.icon + '</svg>' +
      '</button>';
  }
  bar.innerHTML = html;
  if (role === "user" && msg.classList.contains("chat-user-turn")) {
    msg.appendChild(bar);
  } else {
    msg.parentNode.insertBefore(bar, msg.nextSibling);
  }
}

// ========================= Message Action Handlers =========================
document.addEventListener("click", function(e) {
  var btn = e.target.closest(".chat-msg-action");
  if (!btn) return;

  var action = btn.getAttribute("data-action");
  var role = btn.getAttribute("data-role");
  var actionsBar = btn.closest(".chat-msg-actions");
  if (!actionsBar) return;

  var userTurn = actionsBar.closest(".chat-user-turn");
  var bubble = null;
  if (userTurn) {
    bubble = userTurn.querySelector(".chat-message-user") || userTurn;
  } else {
    bubble = actionsBar.previousElementSibling;
    if (!bubble || !bubble.classList.contains("chat-message")) return;
  }

  if (action === "copy") {
    var text = (userTurn ? userTurn.getAttribute("data-raw") : bubble.getAttribute("data-raw")) || bubble.textContent || "";
    if (role === "assistant") {
      var reasoning = bubble.getAttribute("data-reasoning") || "";
      if (reasoning) text = reasoning + (text ? "\n\n" + text : "");
    }
    var origSvg = btn.innerHTML;
    _chatCopyToClipboard(text).then(function() {
      btn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
      btn.classList.add("is-active");
      setTimeout(function() {
        btn.innerHTML = origSvg;
        btn.classList.remove("is-active");
      }, 1500);
    });
    return;
  }

  if (action === "edit") {
    if (role === "assistant") {
      // Edit assistant message content directly
      if (bubble.querySelector(".chat-msg-edit-area")) return;
      var rawText = bubble.getAttribute("data-raw") || bubble.textContent || "";
      var reasoningText = bubble.getAttribute("data-reasoning") || "";

      var area = document.createElement("div");
      area.className = "chat-msg-edit-area";
      area.innerHTML =
        '<textarea class="chat-msg-edit-input" rows="4" style="background:var(--panel-alt);color:var(--text);border-color:var(--border);">' + escapeHtml(rawText) + '</textarea>' +
        '<div class="chat-msg-edit-actions">' +
        '<button class="chat-msg-edit-send" type="button" style="background:var(--accent);color:#fff;border-color:var(--accent);">' + escapeHtml(t('dialog.ok')) + '</button>' +
        '<button class="chat-msg-edit-cancel" type="button" style="background:var(--panel-alt);color:var(--text);border-color:var(--border);">' + escapeHtml(t('dialog.cancel')) + '</button>' +
        '</div>';

      bubble.textContent = "";
      bubble.appendChild(area);

      var textarea = area.querySelector(".chat-msg-edit-input");
      textarea.focus();
      textarea.setSelectionRange(textarea.value.length, textarea.value.length);

      area.querySelector(".chat-msg-edit-cancel").addEventListener("click", function() {
        bubble.innerHTML = _assistantMessageHtml(rawText, { reasoning_content: reasoningText });
        bubble.setAttribute("data-raw", rawText);
        if (reasoningText) bubble.setAttribute("data-reasoning", reasoningText);
      });

      area.querySelector(".chat-msg-edit-send").addEventListener("click", function() {
        var newText = textarea.value;
        bubble.innerHTML = _assistantMessageHtml(newText, { reasoning_content: reasoningText });
        bubble.setAttribute("data-raw", newText);
        if (reasoningText) bubble.setAttribute("data-reasoning", reasoningText);
      });
      return;
    }

    // Edit user message: open editor on bubble (or create one), re-send on save
    var userAnchor = userTurn || bubble;
    var editHost = userTurn ? userTurn.querySelector(".chat-message-user") : bubble;
    if (!editHost && userTurn) {
      editHost = document.createElement("div");
      editHost.className = "chat-message chat-message-user";
      var attBlock = userTurn.querySelector(".chat-user-attachments");
      if (attBlock) userTurn.insertBefore(editHost, attBlock.nextSibling);
      else userTurn.insertBefore(editHost, actionsBar);
    }
    if (!editHost) return;
    if (editHost.querySelector(".chat-msg-edit-area")) return;

    var rawText = userAnchor.getAttribute("data-raw") || "";
    var resolved = _resolveUserHistoryEntry(userTurn || userAnchor);
    if (!resolved) return;
    var historyIndex = resolved.historyIndex;
    var entry = resolved.entry;
    var filesJson = userAnchor.getAttribute("data-files") || "";
    var messageContent = entry.content;

    var area = document.createElement("div");
    area.className = "chat-msg-edit-area";
    area.innerHTML =
      '<textarea class="chat-msg-edit-input" rows="2">' + escapeHtml(rawText) + '</textarea>' +
      '<div class="chat-msg-edit-actions">' +
      '<button class="chat-msg-edit-send" type="button">' + escapeHtml(t('dialog.ok')) + '</button>' +
      '<button class="chat-msg-edit-cancel" type="button">' + escapeHtml(t('dialog.cancel')) + '</button>' +
      '</div>';

    editHost.textContent = "";
    editHost.appendChild(area);

    var textarea = area.querySelector(".chat-msg-edit-input");
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);

    area.querySelector(".chat-msg-edit-cancel").addEventListener("click", function() {
      _restoreUserMessageHtml(userAnchor, rawText, filesJson, messageContent);
    });

    area.querySelector(".chat-msg-edit-send").addEventListener("click", function() {
      var newText = textarea.value.trim();
      if (!entry) return;
      var merged = _mergeUserTextContent(newText, entry.content);
      if (!newText && !_contentHasMedia(merged)) return;
      _removeMessagesFromDom(userAnchor);
      _truncateHistoryFrom(historyIndex);
      _resendUserHistoryEntry(entry, newText);
    });
    return;
  }

  if (action === "retry") {
    var targetUserTurn = userTurn;
    if (role === "assistant") {
      targetUserTurn = _findPrevUserTurn(actionsBar);
    }
    if (!targetUserTurn) return;

    var resolved = _resolveUserHistoryEntry(targetUserTurn);
    if (!resolved) {
      toast(_tOr('chat.retryNoHistory', '无法重试：找不到对应的历史消息'), 'warn');
      return;
    }
    var historyIndex = resolved.historyIndex;
    var entry = resolved.entry;

    _removeMessagesFromDom(targetUserTurn);
    _truncateHistoryFrom(historyIndex);
    _resendUserHistoryEntry(entry, null);
    return;
  }
});

function clearChatMessages() {
  var container = document.getElementById("chatMessagesContainer");
  if (container) {
    container.innerHTML = "";
  }
  _userMsgCount = 0;
  chatConversationHistory = [];
  var report = document.getElementById("chatTestReport");
  if (report) { report.innerHTML = ""; report.classList.add("hidden"); }
  // 确保不清空其他元素
  var inputSection = document.getElementById("chatInputSection");
  if (inputSection && !document.body.contains(inputSection)) {
    document.body.appendChild(inputSection);
  }
  saveChatState();
}

// ========================= Model List =========================
async function loadModelsList() {
  try {
    var result = await fetchJson("/v1/models");
    var dropdown = window._dropdowns && window._dropdowns["chatModelSelect"];
    if (!dropdown || !result || !result.data) return;
    var models = result.data;
    var opts = [];
    var autoSelect = null;
    for (var i = 0; i < models.length; i++) {
      var caps = models[i].capabilities || {};
      if (!caps.chat) continue;
      opts.push({ value: models[i].id, text: models[i].id });
      if (models[i].id === "qwen3.7-max") autoSelect = models[i].id;
    }
    dropdown.setOptions(opts, false);
    // Apply saved model from persist if it exists in the options
    if (_savedChatModel) {
      var found = false;
      for (var j = 0; j < opts.length; j++) {
        if (opts[j].value === _savedChatModel) { found = true; break; }
      }
      if (found) {
        dropdown.setValue(_savedChatModel);
        _savedChatModel = null;
        return;
      }
    }
    if (autoSelect) dropdown.setValue(autoSelect);
    else if (opts.length > 0) dropdown.setValue(opts[0].value);
  } catch (error) {
    var dropdown = window._dropdowns && window._dropdowns["chatModelSelect"];
    if (dropdown) dropdown.setOptions([{ value: '', text: t('overview.loadFailed') }], false);
  }
}

// ========================= Send Chat Message (Streaming) =========================
var chatConversationHistory = [];
var _chatAbortController = null;
var _chatStateLoaded = null;
var _savedChatModel = null;
var _chatStateReady = false;

function _setStreaming(isStreaming) {
  if (!window._chatInputBox) return;
  var sendBtn = window._chatInputBox._el('sendBtn');
  if (!sendBtn) return;
  var span = sendBtn.querySelector('span');
  var svg = sendBtn.querySelector('svg');
  if (isStreaming) {
    if (span) span.textContent = t('chat.stop');
    if (svg) svg.innerHTML = '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>';
    sendBtn.onclick = function() {
      _chatAbortReason = 'user';
      if (_chatAbortController) _chatAbortController.abort();
    };
  } else {
    if (span) span.textContent = t('chat.send');
    if (svg) svg.innerHTML = '<path d="M6 12L3.269 3.125A59.769 59.769 0 0121.485 12 59.768 59.768 0 013.27 20.875L5.999 12Zm0 0h7.5"/>';
    sendBtn.onclick = function() { window._chatInputBox._doSend(); };
  }
}

function _isChatThinkingEnabled() {
  var toggle = document.getElementById("chatThinkingToggle");
  return !!(toggle && toggle.checked);
}

function _applyChatThinkingEnabled(enabled) {
  var toggle = document.getElementById("chatThinkingToggle");
  if (toggle) toggle.checked = !!enabled;
}

function _isChatStreamingEnabled() {
  var toggle = document.getElementById("chatStreamToggle");
  if (!toggle) return true;
  return !!toggle.checked;
}

function _applyChatStreamingEnabled(enabled) {
  var toggle = document.getElementById("chatStreamToggle");
  if (toggle) toggle.checked = !!enabled;
}

function _appendAssistantToHistory(assistantContent, reasoningContent, toolCalls) {
  var assistantMsg = { role: "assistant", content: assistantContent || "" };
  if (reasoningContent) assistantMsg.reasoning_content = reasoningContent;
  if (toolCalls && toolCalls.length > 0) {
    assistantMsg.tool_calls = toolCalls;
    chatConversationHistory.push(assistantMsg);
    for (var ti = 0; ti < toolCalls.length; ti++) {
      chatConversationHistory.push({
        role: "tool",
        tool_call_id: toolCalls[ti].id,
        content: "[WebUI test mode: tool call displayed but not executed]"
      });
    }
  } else {
    chatConversationHistory.push(assistantMsg);
  }
  saveChatState();
}

function _appendErrorAssistantMessage(text) {
  appendChatMessage("assistant", text);
  chatConversationHistory.push({ role: "assistant", content: text || "" });
  saveChatState();
}

function saveChatState() {
  if (_saveChatStateTimer) clearTimeout(_saveChatStateTimer);
  _saveChatStateTimer = setTimeout(function() {
    _saveChatStateTimer = null;
    flushSaveChatState();
  }, 400);
}

async function flushSaveChatState() {
  try {
    var container = document.getElementById("chatMessagesContainer");
    var html = container ? container.innerHTML : "";
    var modelSelect = document.getElementById("chatModelSelect");
    var protocolSelect = document.getElementById("chatProtocolSelect");
    var savedModel = modelSelect ? modelSelect.value : "";
    var savedProtocol = protocolSelect ? protocolSelect.value : "xml";
    var savedThinking = _isChatThinkingEnabled();
    var savedStreaming = _isChatStreamingEnabled();
    _userMsgCount = _countUserMessages(chatConversationHistory);
    var persistHistory = await _exportHistoryForPersist(chatConversationHistory);
    localStorage.setItem("provider.webui.chatHistory", JSON.stringify(persistHistory));
    localStorage.setItem("provider.webui.chatDom", html);
    localStorage.setItem("provider.webui.userMsgCount", String(_userMsgCount));
    localStorage.setItem("provider.webui.chatModel", savedModel);
    localStorage.setItem("provider.webui.chatProtocol", savedProtocol);
    localStorage.setItem("provider.webui.chatThinking", savedThinking ? "1" : "0");
    localStorage.setItem("provider.webui.chatStreaming", savedStreaming ? "1" : "0");
    if (typeof persistSave === 'function') {
      persistSave('chat.json', {
        history: persistHistory,
        userMsgCount: _userMsgCount,
        model: savedModel,
        protocol: savedProtocol,
        thinking: savedThinking,
        streaming: savedStreaming
      });
    }
  } catch (e) { console.debug("flushSaveChatState failed:", e); }
}

function _saveModelProtocol() {
  var modelSelect = document.getElementById("chatModelSelect");
  var protocolSelect = document.getElementById("chatProtocolSelect");
  var m = modelSelect ? modelSelect.value : "";
  var p = protocolSelect ? protocolSelect.value : "xml";
  var thinking = _isChatThinkingEnabled();
  var streaming = _isChatStreamingEnabled();
  try {
    localStorage.setItem("provider.webui.chatModel", m);
    localStorage.setItem("provider.webui.chatProtocol", p);
    localStorage.setItem("provider.webui.chatThinking", thinking ? "1" : "0");
    localStorage.setItem("provider.webui.chatStreaming", streaming ? "1" : "0");
    if (typeof persistSave === 'function') {
      persistSave('chat_model.json', { model: m, protocol: p, thinking: thinking, streaming: streaming });
    }
  } catch (e) { console.debug("_saveModelProtocol failed:", e); }
}

async function loadChatState() {
  _chatStateLoaded = (async function() {
  try {
  try {
    // Try loading from backend persist first
    if (typeof persistLoad === 'function') {
      try {
        var persisted = await persistLoad('chat.json');
        if (persisted && persisted.history && persisted.history.length > 0) {
          chatConversationHistory = await _hydrateHistoryForDisplay(persisted.history);
          _userMsgCount = persisted.userMsgCount || 0;
          // Restore model and protocol selections
          if (persisted.model) {
            _savedChatModel = persisted.model;
            await loadModelsList();
          }
          if (persisted.protocol) {
            var protocolSelect = document.getElementById("chatProtocolSelect");
            if (protocolSelect) protocolSelect.value = persisted.protocol;
          }
          if (typeof persisted.thinking === "boolean") {
            _applyChatThinkingEnabled(persisted.thinking);
          } else if (typeof persistLoad === "function") {
            try {
              var modelPrefs = await persistLoad("chat_model.json");
              if (modelPrefs && typeof modelPrefs.thinking === "boolean") {
                _applyChatThinkingEnabled(modelPrefs.thinking);
              }
            } catch (e) { console.debug("loadChatState: failed to load chat_model.json thinking pref:", e); }
          }
          if (typeof persisted.streaming === "boolean") {
            _applyChatStreamingEnabled(persisted.streaming);
          } else if (typeof persistLoad === "function") {
            try {
              var streamPrefs = await persistLoad("chat_model.json");
              if (streamPrefs && typeof streamPrefs.streaming === "boolean") {
                _applyChatStreamingEnabled(streamPrefs.streaming);
              }
            } catch (e) { console.debug("loadChatState: failed to load chat_model.json streaming pref:", e); }
          }
          _renderChatHistoryFromMemory();
          return;
        }
      } catch (e) { console.debug("loadChatState backend path failed, falling back to localStorage:", e); chatConversationHistory = []; }
    }
    // Fallback to localStorage for model/protocol
    var savedModel = localStorage.getItem("provider.webui.chatModel");
    var savedProtocol = localStorage.getItem("provider.webui.chatProtocol");
    if (savedModel) {
      _savedChatModel = savedModel;
      var dd = window._dropdowns && window._dropdowns["chatModelSelect"];
      if (dd) dd.setValue(savedModel);
    }
    if (savedProtocol) {
      var protocolSelect = document.getElementById("chatProtocolSelect");
      if (protocolSelect) protocolSelect.value = savedProtocol;
    }
    var savedThinking = localStorage.getItem("provider.webui.chatThinking");
    if (savedThinking === "1" || savedThinking === "0") {
      _applyChatThinkingEnabled(savedThinking === "1");
    } else if (typeof persistLoad === "function") {
      try {
        var modelPrefs = await persistLoad("chat_model.json");
        if (modelPrefs && typeof modelPrefs.thinking === "boolean") {
          _applyChatThinkingEnabled(modelPrefs.thinking);
        }
      } catch (e) { console.debug("loadChatState: failed to load chat_model.json thinking pref:", e); }
    }
    var savedStreaming = localStorage.getItem("provider.webui.chatStreaming");
    if (savedStreaming === "1" || savedStreaming === "0") {
      _applyChatStreamingEnabled(savedStreaming === "1");
    } else if (typeof persistLoad === "function") {
      try {
        var streamPrefs = await persistLoad("chat_model.json");
        if (streamPrefs && typeof streamPrefs.streaming === "boolean") {
          _applyChatStreamingEnabled(streamPrefs.streaming);
        }
      } catch (e) { console.debug("loadChatState: failed to load chat_model.json streaming pref:", e); }
    }
    // Fallback to localStorage
    var hist = localStorage.getItem("provider.webui.chatHistory");
    var dom = localStorage.getItem("provider.webui.chatDom");
    var count = localStorage.getItem("provider.webui.userMsgCount");
    if (hist) {
      try {
        var parsed = JSON.parse(hist);
        if (Array.isArray(parsed) && parsed.length > 0) {
          chatConversationHistory = await _hydrateHistoryForDisplay(parsed);
          _renderChatHistoryFromMemory();
        }
      } catch (e) { console.debug("loadChatState: failed to parse chat history from localStorage:", e); }
    }
    if (count) _userMsgCount = parseInt(count, 10) || 0;
    if (dom) {
      var container = document.getElementById("chatMessagesContainer");
      if (container && (!chatConversationHistory || chatConversationHistory.length === 0)) {
        container.innerHTML = dom;
      }
    }
  } catch (e) { console.debug("loadChatState: unexpected error during state restoration:", e); }
  } finally {
    _chatStateReady = true;
  }
  })();
  return _chatStateLoaded;
}

async function sendChatMessage(text, files, options) {
  options = options || {};
  if (!text && (!files || files.length === 0) && options.presetContent === undefined) return;
  // Ensure chat history is loaded before sending
  if (_chatStateLoaded) {
    try { await _chatStateLoaded; } catch (e) { console.debug("sendChatMessage: error awaiting chat state load:", e); }
    _chatStateLoaded = null;
  }

  var model = document.getElementById("chatModelSelect").value;
  var protocol = document.getElementById("chatProtocolSelect").value;
  if (!model) { toast(t('chat.selectModelFirst'), "error"); return; }

  var messageContent;
  try {
    if (options.presetContent !== undefined) {
      messageContent = options.presetContent;
    } else {
      messageContent = await _buildUserMessageContent(text, files);
    }
  } catch (e) {
    toast(t('chat.error', { error: e.message || String(e) }), 'error');
    return;
  }

  var displayText = _userDisplayText(messageContent);
  if (!displayText && text) displayText = text;

  var fileMeta = options.presetFiles || null;
  if (!fileMeta && files && files.length > 0) {
    fileMeta = files.filter(function(f) {
      var mime = f.file && f.file.type;
      return !_isImageAttachment(f.name, mime);
    }).map(function(f) {
      return { name: f.name, size: _fileItemSize(f) };
    });
    if (!fileMeta.length) fileMeta = null;
  }

  var historyIndex = chatConversationHistory.length;
  var histEntry = { role: "user", content: messageContent };
  if (fileMeta) histEntry.files = fileMeta;
  chatConversationHistory.push(histEntry);
  appendChatMessage("user", displayText, {
    files: fileMeta,
    historyIndex: historyIndex,
    messageContent: messageContent,
  });
  if (_contentHasMedia(messageContent)) {
    await flushSaveChatState();
  } else {
    saveChatState();
  }

  try {
    var tools = getToolsDefinition();
    var historySlice = _prepareMessagesForApi(chatConversationHistory.slice(-20));
    var streamEnabled = _isChatStreamingEnabled();
    var body = {
      model: model,
      messages: historySlice,
      stream: streamEnabled,
      protocol: protocol,
      extra_body: { thinking: _isChatThinkingEnabled() }
    };
    if (tools.length > 0) {
      body.tools = tools;
    }


    // 创建超时控制器（默认 120 秒）
    var timeoutMs = 120000;
    var abortController = new AbortController();
    _chatAbortController = abortController;
    _chatAbortReason = null;
    _setStreaming(true);
    var timeoutId = setTimeout(function() {
      abortController.abort();
    }, timeoutMs);
    var streamTimeoutId = null;

    // Show loading spinner while waiting for response
    _spinnerCreatedAt = Date.now();
    var container = document.getElementById("chatMessagesContainer");
    var spinnerEl = document.createElement("div");
    spinnerEl.id = "_chatSpinner";
    spinnerEl.style.cssText = "display:inline-flex;align-items:center;gap:10px;margin:6px 0 6px 4px;";
    spinnerEl.innerHTML = '<span class="chat-loading-spinner">' + escapeHtml(t('chat.thinkingInProgress')) + '</span>';
    if (container) {
      container.appendChild(spinnerEl);
      container.scrollTop = container.scrollHeight;
    }

    var response = await fetch("/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify(body),
      signal: abortController.signal
    });

    clearTimeout(timeoutId); // 响应已开始，取消超时

    if (!response.ok) {
      _removeChatSpinner();
      var errText = await response.text();
      if (response.status === 401) {
        window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname);
        return;
      }
      _appendErrorAssistantMessage("Error " + response.status + ": " + errText);
      return;
    }

    if (!streamEnabled) {
      var payload = await response.json();
      _removeChatSpinner();
      if (payload.error) {
        var perr = payload.error;
        _appendErrorAssistantMessage("[" + (perr.type || "error") + "] " + (perr.message || "unknown error"));
        return;
      }
      var choice = (payload.choices || [])[0] || {};
      var message = choice.message || {};
      var assistantContent = message.content || "";
      var reasoningContent = message.reasoning_content || "";
      var toolCalls = message.tool_calls || [];
      appendChatMessage("assistant", assistantContent, {
        reasoning_content: reasoningContent,
        toolCalls: toolCalls
      });
      _appendAssistantToHistory(assistantContent, reasoningContent, toolCalls);
      return;
    }

    // 设置流式读取超时（60 秒无数据）
    streamTimeoutId = setTimeout(function() {
      _chatAbortReason = 'timeout';
      abortController.abort();
    }, 60000);

    function resetStreamTimeout() {
      clearTimeout(streamTimeoutId);
      streamTimeoutId = setTimeout(function() {
        _chatAbortReason = 'timeout';
        abortController.abort();
      }, 60000);
    }

    // Parse SSE stream
    var reader = response.body.getReader();
    var decoder = new TextDecoder();
    var buffer = "";
    var assistantContent = "";
    var reasoningContent = "";
    var toolCalls = [];
    var currentToolCall = null;
    var assistantAdded = false; // 标记助手消息是否已添加到历史

    while (true) {
      var result = await reader.read();
      if (result.done) break;
      resetStreamTimeout(); // 收到数据，重置超时
      buffer += decoder.decode(result.value, { stream: true });

      var lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (var i = 0; i < lines.length; i++) {
        var line = lines[i].trim();
        if (!line || !line.startsWith("data: ")) continue;
        var data = line.slice(6);
        if (data === "[DONE]") break;

        try {
          var chunk = JSON.parse(data);

          // Check for error response in stream
          if (chunk.error) {
            var errMsg = chunk.error.message || chunk.error.code || "unknown error";
            var errType = chunk.error.type || "error";
            _cancelActiveStreaming();
            _appendErrorAssistantMessage("[" + errType + "] " + errMsg);
            return;
          }

          var choices = chunk.choices || [];
          for (var j = 0; j < choices.length; j++) {
            var choice = choices[j];
            var delta = choice.delta || {};

            if (delta.content) {
              assistantContent += delta.content;
              updateStreamingMessage(assistantContent);
            }

            if (delta.reasoning_content) {
              reasoningContent += delta.reasoning_content;
              updateStreamingReasoning(reasoningContent);
            }

            if (delta.tool_calls && delta.tool_calls.length > 0) {
              for (var k = 0; k < delta.tool_calls.length; k++) {
                var tc = delta.tool_calls[k];
                if (tc.id !== undefined && tc.id !== null) {
                  // New tool call
                  currentToolCall = { id: tc.id, index: tc.index || 0, function: { name: tc.function.name, arguments: "" } };
                  toolCalls.push(currentToolCall);
                } else if (currentToolCall && tc.function && tc.function.arguments) {
                  currentToolCall.function.arguments += tc.function.arguments;
                }
              }
            }

            if (choice.finish_reason && !assistantAdded) {
              finalizeStreamingMessage(toolCalls);
              _appendAssistantToHistory(assistantContent, reasoningContent, toolCalls);
              assistantAdded = true;
            }
          }
        } catch (parseError) {
          // Ignore parse errors for non-JSON data lines
        }
      }
    }

    // 如果流结束但助手消息未添加到历史（某些服务器不发送 finish_reason），手动添加
    if (!assistantAdded && (assistantContent || reasoningContent || toolCalls.length > 0)) {
      if (reasoningContent) updateStreamingReasoning(reasoningContent);
      if (assistantContent) updateStreamingMessage(assistantContent);
      finalizeStreamingMessage(toolCalls);
      _appendAssistantToHistory(assistantContent, reasoningContent, toolCalls);
      assistantAdded = true;
    }

    // 如果流结束但完全没有内容，显示错误提示
    if (!assistantAdded && !assistantContent && !reasoningContent && toolCalls.length === 0) {
      _cancelActiveStreaming();
      _appendErrorAssistantMessage("[stream_error] response ended with no content from model " + (body.model || "unknown"));
    }
  } catch (error) {
    _cancelActiveStreaming();
    if (error.name === 'AbortError') {
      _appendErrorAssistantMessage(_chatAbortReason === 'timeout' ? t('chat.streamTimeout') : t('chat.requestCancelled'));
    } else {
      _appendErrorAssistantMessage(t('chat.error', { error: String(error) }));
    }
  } finally {
    clearTimeout(timeoutId);
    if (streamTimeoutId) clearTimeout(streamTimeoutId);
    _chatAbortReason = null;
    _setStreaming(false);
    _chatAbortController = null;
  }
}

// ========================= Batch Test (OpenAI Batch style) =========================
async function runChatTests() {
  var modelSelect = document.getElementById("chatModelSelect");
  var protocolSelect = document.getElementById("chatProtocolSelect");
  var batchTextarea = document.getElementById("chatBatchPrompts");
  var tempInput = document.getElementById("batchTemperature");
  var maxTokInput = document.getElementById("batchMaxTokens");
  var sysPromptInput = document.getElementById("batchSystemPrompt");

  var testModel = modelSelect ? modelSelect.value : "qwen3.7-max";
  var protocol = protocolSelect ? protocolSelect.value : "xml";
  var temperature = tempInput ? parseFloat(tempInput.value) || 0.7 : 0.7;
  var maxTokens = maxTokInput ? parseInt(maxTokInput.value) || 1024 : 1024;
  var systemPrompt = sysPromptInput ? sysPromptInput.value.trim() : "";

  // Get prompts from textarea (one per line) or fallback to input box or default
  var prompts = [];
  if (batchTextarea && batchTextarea.value.trim()) {
    prompts = batchTextarea.value.split('\n').map(function(l) { return l.trim(); }).filter(function(l) { return l.length > 0; });
  } else {
    var inputText = (window._chatInputBox && window._chatInputBox.getText()) || '';
    var single = inputText.trim();
    if (single) {
      prompts = [single];
    } else {
      prompts = [t('chat.batchPromptsPlaceholder')];
    }
  }

  var report = document.getElementById("chatTestReport");
  if (!report) return;

  report.classList.remove("hidden");
  report.innerHTML = '<div style="padding:8px;"><div style="text-align:center;color:var(--muted);margin-bottom:12px;">'
    + escapeHtml(t('chat.batchTestSummary', {
      count: prompts.length,
      model: testModel,
      protocol: protocol,
      thinking: _isChatThinkingEnabled() ? t('common.on') : t('common.off'),
      streaming: _isChatStreamingEnabled() ? t('common.on') : t('common.off'),
    }))
    + '</div><div id="batchResultsList"></div></div>';

  var resultsList = document.getElementById("batchResultsList");
  var completedCount = 0;
  var passCount = 0;

  for (var i = 0; i < prompts.length; i++) {
    var prompt = prompts[i];
    var resultId = 'batch-result-' + i;

    // Add result placeholder
    var resultDiv = document.createElement('div');
    resultDiv.id = resultId;
    resultDiv.className = 'border border-border rounded-xl p-3 mb-2 cursor-pointer hover:border-accent transition';
    resultDiv.dataset.fullContent = '';
    resultDiv.dataset.prompt = prompt;
    resultDiv.innerHTML = '<div class="flex justify-between items-center mb-2">'
      + '<span class="text-[12px] text-muted">Prompt ' + (i+1) + '/' + prompts.length + '</span>'
      + '<span class="text-[12px] text-muted" id="' + resultId + '-status">' + escapeHtml(t('chat.testing')) + '</span>'
      + '</div>'
      + '<div class="text-[13px] mb-2" style="color:var(--text);">' + escapeHtml(prompt.substring(0, 100) + (prompt.length > 100 ? '...' : '')) + '</div>'
      + '<div class="text-[12px] font-mono" style="color:var(--muted);min-height:20px;" id="' + resultId + '-content">...</div>'
      + '<div class="flex gap-3 mt-2 text-[11px] text-muted" id="' + resultId + '-stats">'
      + '<span>' + escapeHtml(t('chat.firstToken')) + ': <span id="' + resultId + '-ftt">-</span>ms</span>'
      + '<span>' + escapeHtml(t('chat.totalTime')) + ': <span id="' + resultId + '-total">-</span>ms</span>'
      + '<span>' + escapeHtml(t('chat.tps')) + ': <span id="' + resultId + '-tps">-</span></span>'
      + '</div>';
    resultDiv.addEventListener('click', function() { showBatchResultDialog(this.dataset.prompt, this.dataset.fullContent, this); });
    resultsList.appendChild(resultDiv);

    try {
      var messages = [];
      if (systemPrompt) messages.push({ role: "system", content: systemPrompt });
      messages.push({ role: "user", content: prompt });

      var tools = getToolsDefinition();
      var body = {
        model: testModel,
        messages: messages,
        stream: _isChatStreamingEnabled(),
        protocol: protocol,
        temperature: temperature,
        max_tokens: maxTokens,
        extra_body: { thinking: _isChatThinkingEnabled() }
      };
      if (tools.length > 0) body.tools = tools;

      var response = await fetch("/v1/chat/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        credentials: "same-origin",
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(60000)
      });

      if (!response.ok) {
        document.getElementById(resultId + '-status').textContent = t('chat.failedHttp', { status: response.status });
        document.getElementById(resultId + '-status').style.color = 'var(--err)';
        document.getElementById(resultId + '-content').textContent = 'HTTP ' + response.status;
        completedCount++;
        continue;
      }

      var content = "";
      var hasToolCalls = false;
      var completed = false;
      var contentEl = document.getElementById(resultId + '-content');
      var statusEl = document.getElementById(resultId + '-status');
      var startTime = Date.now();
      var firstTokenTime = null;
      var tokenCount = 0;

      if (!_isChatStreamingEnabled()) {
        var payload = await response.json();
        if (payload.error) {
          throw new Error(payload.error.message || "request failed");
        }
        var batchChoice = (payload.choices || [])[0] || {};
        var batchMsg = batchChoice.message || {};
        content = batchMsg.content || "";
        if (batchMsg.reasoning_content) {
          content = t('chat.thinkingPrefix') + batchMsg.reasoning_content.substring(0, 80) + (batchMsg.reasoning_content.length > 80 ? "..." : "") + "\n" + content;
        }
        hasToolCalls = !!(batchMsg.tool_calls && batchMsg.tool_calls.length > 0);
        tokenCount = content ? Math.max(1, Math.floor(content.length / 4)) : 0;
        completed = true;
      } else {
      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";

      while (true) {
        var readResult = await reader.read();
        if (readResult.done) break;
        buffer += decoder.decode(readResult.value, { stream: true });

        var lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (var li = 0; li < lines.length; li++) {
          var line = lines[li].trim();
          if (!line || !line.startsWith("data: ")) continue;
          var data = line.slice(6);
          if (data === "[DONE]") { completed = true; break; }

          try {
            var chunk = JSON.parse(data);
            var choices = chunk.choices || [];
            for (var ci = 0; ci < choices.length; ci++) {
              var delta = choices[ci].delta || {};
              if (delta.content) {
                if (firstTokenTime === null) firstTokenTime = Date.now();
                content += delta.content;
                tokenCount++;
                contentEl.textContent = content.substring(0, 200) + (content.length > 200 ? '...' : '');
                resultDiv.dataset.fullContent = content;
                resultDiv.dataset.firstTokenTime = firstTokenTime - startTime;
                resultDiv.dataset.tokenCount = tokenCount;
                resultDiv.dataset.elapsed = Date.now() - startTime;
                // Update stats display in real-time
                var fttEl = document.getElementById(resultId + '-ftt');
                var totalEl = document.getElementById(resultId + '-total');
                var tpsEl = document.getElementById(resultId + '-tps');
                if (fttEl) fttEl.textContent = (firstTokenTime - startTime);
                if (totalEl) totalEl.textContent = (Date.now() - startTime);
                if (tpsEl && tokenCount > 0) {
                  var elapsed = (Date.now() - startTime) / 1000;
                  tpsEl.textContent = elapsed > 0 ? (tokenCount / elapsed).toFixed(1) : '0';
                }
              }
              if (delta.tool_calls && delta.tool_calls.length > 0) hasToolCalls = true;
              if (choices[ci].finish_reason) completed = true;
            }
          } catch(e) {}
        }
        if (completed) break;
      }
      }

      var totalTime = Date.now() - startTime;
      var tps = tokenCount > 0 && totalTime > 0 ? (tokenCount / (totalTime / 1000)).toFixed(1) : '0';
      statusEl.textContent = hasToolCalls ? t('chat.passedWithTools') : t('chat.passed');
      statusEl.style.color = 'var(--ok)';
      contentEl.textContent = content.substring(0, 200) + (content.length > 200 ? '...' : '');
      resultDiv.dataset.fullContent = content;
      resultDiv.dataset.firstTokenTime = firstTokenTime ? (firstTokenTime - startTime) : '-';
      resultDiv.dataset.totalTime = totalTime;
      resultDiv.dataset.tokenCount = tokenCount;
      resultDiv.dataset.tps = tps;
      passCount++;
    } catch (error) {
      document.getElementById(resultId + '-status').textContent = t('chat.failedWithError', { error: String(error).substring(0, 50) });
      document.getElementById(resultId + '-status').style.color = 'var(--err)';
      document.getElementById(resultId + '-content').textContent = String(error);
      resultDiv.dataset.fullContent = String(error);
    }
    completedCount++;
  }

  // Add summary
  var summaryDiv = document.createElement('div');
  summaryDiv.style.cssText = 'margin-top:12px;text-align:right;font-size:13px;color:var(--muted);';
  summaryDiv.textContent = t('chat.batchComplete', { passed: passCount, total: prompts.length });
  resultsList.appendChild(summaryDiv);

  toast(t('chat.batchCompleteToast', { passed: passCount, total: prompts.length }), passCount === prompts.length ? "ok" : "warn");
}

function showBatchResultDialog(prompt, fullContent, resultDiv) {
  var displayContent = fullContent || '<span style="color:var(--muted);">' + escapeHtml(t('chat.generating')) + '</span>';
  var stats = resultDiv ? {
    ftt: resultDiv.dataset.firstTokenTime || '-',
    total: resultDiv.dataset.totalTime || resultDiv.dataset.elapsed || '-',
    tokens: resultDiv.dataset.tokenCount || '0',
    tps: resultDiv.dataset.tps || '0'
  } : { ftt: '-', total: '-', tokens: '0', tps: '0' };

  var overlay = document.createElement('div');
  overlay.className = 'batch-result-overlay';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;padding:24px;';

  var contentPreId = 'batch-result-content-' + Date.now();
  var statsId = 'batch-result-stats-' + Date.now();

  overlay.innerHTML = '<div style="background:var(--panel);border:1px solid var(--border);border-radius:16px;max-width:700px;width:100%;max-height:80vh;display:flex;flex-direction:column;overflow:hidden;">'
    + '<div style="display:flex;justify-content:space-between;align-items:center;padding:16px 20px;border-bottom:1px solid var(--border);">'
    + '<span style="font-weight:600;font-size:15px;">' + escapeHtml(t('chat.batchResultTitle')) + '</span>'
    + '<button style="background:none;border:none;cursor:pointer;font-size:20px;color:var(--muted);" id="batchResultCloseBtn">&times;</button>'
    + '</div>'
    + '<div style="padding:16px 20px;overflow-y:auto;flex:1;">'
    + '<div style="margin-bottom:12px;"><span style="font-size:12px;color:var(--muted);">Prompt:</span><div style="font-size:13px;margin-top:4px;color:var(--text);">' + escapeHtml(prompt) + '</div></div>'
    + '<div id="' + statsId + '" class="flex gap-4 mb-3 text-[12px] text-muted">'
    + '<span>' + escapeHtml(t('chat.firstToken')) + ': <strong>' + stats.ftt + '</strong>ms</span>'
    + '<span>' + escapeHtml(t('chat.totalTime')) + ': <strong>' + stats.total + '</strong>ms</span>'
    + '<span>' + escapeHtml(t('chat.tokens')) + ': <strong>' + stats.tokens + '</strong></span>'
    + '<span>' + escapeHtml(t('chat.tps')) + ': <strong>' + stats.tps + '</strong></span>'
    + '</div>'
    + '<div><span style="font-size:12px;color:var(--muted);">' + escapeHtml(t('chat.responseLabel')) + '</span><pre id="' + contentPreId + '" style="font-size:13px;margin-top:4px;white-space:pre-wrap;word-break:break-word;color:var(--text);background:var(--panel-alt);padding:12px;border-radius:8px;max-height:400px;overflow-y:auto;">' + (typeof displayContent === 'string' ? escapeHtml(displayContent) : displayContent) + '</pre></div>'
    + '</div></div>';
  document.body.appendChild(overlay);

  // Real-time update: poll resultDiv dataset for updates
  var updateInterval = null;
  if (resultDiv) {
    updateInterval = setInterval(function() {
      var pre = document.getElementById(contentPreId);
      var statsEl = document.getElementById(statsId);
      if (!pre || !statsEl) { clearInterval(updateInterval); return; }
      var currentContent = resultDiv.dataset.fullContent || '';
      pre.textContent = currentContent || t('chat.generating');
      statsEl.innerHTML = '<span>' + escapeHtml(t('chat.firstToken')) + ': <strong>' + (resultDiv.dataset.firstTokenTime || '-') + '</strong>ms</span>'
        + '<span>' + escapeHtml(t('chat.totalTime')) + ': <strong>' + (resultDiv.dataset.totalTime || resultDiv.dataset.elapsed || '-') + '</strong>ms</span>'
        + '<span>' + escapeHtml(t('chat.tokens')) + ': <strong>' + (resultDiv.dataset.tokenCount || '0') + '</strong></span>'
        + '<span>' + escapeHtml(t('chat.tps')) + ': <strong>' + (resultDiv.dataset.tps || '0') + '</strong></span>';
    }, 200);
  }

  document.getElementById('batchResultCloseBtn').addEventListener('click', function() {
    if (updateInterval) clearInterval(updateInterval);
    overlay.remove();
  });
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) {
      if (updateInterval) clearInterval(updateInterval);
      overlay.remove();
    }
  });
}

// ========================= Tool Definition Section =========================
var _toolsSaveTimer = null;

function _saveTools() {
  if (_toolsSaveTimer) clearTimeout(_toolsSaveTimer);
  _toolsSaveTimer = setTimeout(function() {
    var toolsList = document.getElementById("chatToolsList");
    if (!toolsList) return;
    var items = toolsList.querySelectorAll(".tool-item");
    var tools = [];
    for (var i = 0; i < items.length; i++) {
      var item = items[i];
      var name = item.querySelector(".tool-name-input");
      var desc = item.querySelector(".tool-desc-input");
      var params = item.querySelector(".tool-params-input");
      if (name) {
        tools.push({
          name: name.value || '',
          desc: desc ? desc.value : '',
          params: params ? params.value : ''
        });
      }
    }
    if (typeof persistSave === 'function') {
      persistSave('tools.json', { tools: tools });
    }
  }, 500);
}

function _loadTools() {
  if (typeof persistLoad !== 'function') return;
  persistLoad('tools.json').then(function(data) {
    if (!data || !data.tools || !data.tools.length) return;
    var toolsList = document.getElementById("chatToolsList");
    var template = document.getElementById("chatToolTemplate");
    if (!toolsList || !template) return;
    for (var i = 0; i < data.tools.length; i++) {
      var t = data.tools[i];
      var clone = template.content.cloneNode(true);
      var item = clone.querySelector(".tool-item");
      var removeBtn = item.querySelector(".tool-remove-btn");
      item.querySelector(".tool-name-input").value = t.name || '';
      item.querySelector(".tool-desc-input").value = t.desc || '';
      item.querySelector(".tool-params-input").value = t.params || '';
      (function(itm) {
        removeBtn.addEventListener("click", function() {
          itm.remove();
          _saveTools();
        });
      })(item);
      toolsList.appendChild(clone);
    }
  }).catch(function() {});
}

(function() {
  var toolsList = document.getElementById("chatToolsList");
  var template = document.getElementById("chatToolTemplate");
  var addBtn = document.getElementById("chatAddToolBtn");
  var clearBtn = document.getElementById("chatClearToolsBtn");

  if (!toolsList || !template || !addBtn) return;

  var firstToolTemplate = {
    name: "get_weather",
    desc: t('chat.sampleToolDesc'),
    params: '{\n  "city": {\n    "type": "string",\n    "description": "' + t('chat.sampleCityDesc') + '"\n  }\n}'
  };

  addBtn.addEventListener("click", function() {
    var isFirst = toolsList.children.length === 0;
    var clone = template.content.cloneNode(true);
    var item = clone.querySelector(".tool-item");
    var removeBtn = item.querySelector(".tool-remove-btn");

    if (isFirst) {
      item.querySelector(".tool-name-input").value = firstToolTemplate.name;
      item.querySelector(".tool-desc-input").value = firstToolTemplate.desc;
      item.querySelector(".tool-params-input").value = firstToolTemplate.params;
    }

    removeBtn.addEventListener("click", function() {
      item.remove();
      _saveTools();
    });

    // Auto-save on input changes
    item.querySelectorAll("input, textarea").forEach(function(el) {
      el.addEventListener("input", _saveTools);
    });

    toolsList.appendChild(clone);
    _saveTools();
  });

  clearBtn.addEventListener("click", function() {
    if (toolsList.children.length === 0) return;
    showConfirmDialog(t('chat.clearToolsConfirm')).then(function(ok) {
      if (ok) {
        toolsList.innerHTML = "";
        _saveTools();
      }
    });
  });
})();

/**
 * 获取当前定义的工具列表，格式化为 OpenAI tools 格式。
 * @returns {Array} OpenAI tools 数组
 */
function getToolsDefinition() {
  var toolsList = document.getElementById("chatToolsList");
  if (!toolsList) return [];

  var items = toolsList.querySelectorAll(".tool-item");
  var tools = [];

  for (var i = 0; i < items.length; i++) {
    var item = items[i];
    var name = item.querySelector(".tool-name-input").value.trim();
    var desc = item.querySelector(".tool-desc-input").value.trim();
    var paramsRaw = item.querySelector(".tool-params-input").value.trim();

    if (!name) continue;

    var properties = {};
    try {
      if (paramsRaw) {
        properties = JSON.parse(paramsRaw);
      }
    } catch (e) {
      // Ignore parse errors, use empty properties
    }

    tools.push({
      type: "function",
      function: {
        name: name,
        description: desc || "",
        parameters: {
          type: "object",
          properties: properties,
          required: Object.keys(properties).length > 0 ? Object.keys(properties) : []
        }
      }
    });
  }

  return tools;
}

// ========================= Auto-save model/protocol on change =========================
(function() {
  var modelEl = document.getElementById("chatModelSelect");
  var protocolEl = document.getElementById("chatProtocolSelect");
  var thinkingEl = document.getElementById("chatThinkingToggle");
  var streamEl = document.getElementById("chatStreamToggle");
  if (modelEl) modelEl.addEventListener("change", function() { if (_chatStateReady) _saveModelProtocol(); });
  if (protocolEl) protocolEl.addEventListener("change", function() { if (_chatStateReady) _saveModelProtocol(); });
  if (thinkingEl) thinkingEl.addEventListener("change", function() { if (_chatStateReady) _saveModelProtocol(); });
  if (streamEl) streamEl.addEventListener("change", function() { if (_chatStateReady) _saveModelProtocol(); });
})();

if (typeof ChatAttachments !== 'undefined') {
  ChatAttachments.install();
}

