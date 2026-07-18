// Chat input handled by InputBox component (inbox.js)

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
  try { success = document.execCommand('copy'); } catch (e) { console.error('Copy failed:', e); }
  document.body.removeChild(textarea);
  return success ? Promise.resolve() : Promise.reject(new Error('Copy failed'));
}

function _getStreamIdleTimeoutMs() {
  if (typeof getStreamIdleTimeoutMs === 'function') return getStreamIdleTimeoutMs();
  return 60000;
}

function _streamTimeoutMessage() {
  return t('chat.streamTimeout', { seconds: Math.round(_getStreamIdleTimeoutMs() / 1000) });
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

async function _hydrateHistoryForDisplay(history) {
  if (!history || !history.length) return [];
  if (typeof ChatMediaPersist !== 'undefined' && ChatMediaPersist.hydrateHistory) {
    return await ChatMediaPersist.hydrateHistory(history);
  }
  return history;
}

// ========================= File / Content Helpers =========================
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
  var imgExts = { jpg: 1, jpeg: 1, png: 1, gif: 1, webp: 1, bmp: 1, svg: 1 };
  return Object.prototype.hasOwnProperty.call(imgExts, ext);
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
  if (!files || !files.length) return trimmed;
  for (var i = 0; i < files.length; i++) {
    var item = files[i];
    if (typeof item.text === 'string') {
      parts.push({ type: 'text', text: '[file: ' + item.name + ']\n' + item.text });
      continue;
    }
    var blob = item.file || item;
    if (!(blob instanceof Blob)) continue;
    var mime = blob.type || ({ jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', gif: 'image/gif', webp: 'image/webp', bmp: 'image/bmp', svg: 'image/svg+xml' })[(item.name || '').split('.').pop().toLowerCase()] || 'application/octet-stream';
    var dataUrl = await _readBlobAsDataUrl(blob);
    if (_isImageAttachment(item.name, mime)) {
      parts.push({ type: 'image_url', image_url: { url: dataUrl } });
    } else {
      parts.push({ type: 'file', file: { filename: item.name || 'attachment', data: dataUrl } });
    }
  }
  if (parts.length === 1 && parts[0].type === 'text') return parts[0].text;
  return parts;
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
    try { formattedArgs = JSON.stringify(JSON.parse(args), null, 2); } catch(e) { formattedArgs = args || "{}"; }
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
  if (options.reasoning_content) html += _buildReasoningHtml(options.reasoning_content);
  if (options.toolCalls && options.toolCalls.length > 0) html += _buildToolCallsHtml(options.toolCalls);
  html += '<div class="chat-assistant-text">' + renderWithCodeBlocks(content || "") + "</div>";
  return html;
}

function _appendUserTurn(container, content, options) {
  var historyIndex = options.historyIndex != null ? options.historyIndex : Math.max(0, chatConversationHistory.length - 1);
  var displayText = typeof content === 'string' ? content : _userDisplayText(content);
  var turn = document.createElement("div");
  turn.className = "chat-user-turn";
  turn.setAttribute("data-history-index", String(historyIndex));
  turn.setAttribute("data-raw", displayText || "");
  if (options.files && options.files.length > 0) turn.setAttribute("data-files", JSON.stringify(options.files));
  _ensureUserTurnAttachments(turn, {
    files: options.files,
    messageContent: options.messageContent != null ? options.messageContent : content,
  });
  if (displayText) _setUserTurnBubble(turn, displayText);
  container.appendChild(turn);
  if (!options.isStreaming) appendMessageActions("user", turn);
  container.scrollTop = container.scrollHeight;
  return turn;
}

function appendChatMessage(role, content, options) {
  options = options || {};
  var container = document.getElementById("chatMessagesContainer");
  if (!container) return;
  if (role === "user") return _appendUserTurn(container, content, options);
  var msg = document.createElement("div");
  msg.className = "chat-message chat-message-" + role;
  if (role === "assistant") {
    msg.setAttribute("data-raw", content || "");
    if (options.reasoning_content) msg.setAttribute("data-reasoning", options.reasoning_content);
    msg.innerHTML = _assistantMessageHtml(content, options);
  } else if (role === "system") {
    msg.className = "chat-message chat-message-system";
    msg.style.cssText = "background:rgba(255,180,0,0.12);border-left:3px solid #e6a817;color:#b8860b;padding:8px 12px;border-radius:6px;font-size:13px;margin:6px 0;";
    msg.textContent = content;
  } else {
    msg.textContent = content;
  }
  if (options.isStreaming) msg.id = "chatStreamingMessage";
  container.appendChild(msg);
  if (role === "assistant" && !options.isStreaming) appendMessageActions(role, msg);
  container.scrollTop = container.scrollHeight;
  return msg;
}

// ========================= Event Listeners =========================
document.addEventListener("keydown", function(e) {
  var block = e.target.closest(".chat-reasoning-block");
  if (!block || (e.key !== "Enter" && e.key !== " ")) return;
  e.preventDefault();
  _toggleReasoningBlock(block);
});

function _handleCodeblockCopyClick(btn) {
  var wrapper = btn.closest('.chat-codeblock-wrapper');
  var pre = wrapper ? wrapper.querySelector('.chat-codeblock') : null;
  var idx = pre ? parseInt(pre.getAttribute('data-cb-index'), 10) : -1;
  var raw = (idx >= 0 && idx < _codeBlockStore.length) ? _codeBlockStore[idx] : (pre ? pre.textContent : '');
  _chatCopyToClipboard(raw).then(function() {
    btn.textContent = t('toast.copied');
    btn.classList.add("is-copied");
    setTimeout(function() { btn.textContent = t('common.copy'); btn.classList.remove("is-copied"); }, 2000);
  });
}

function _handleCodeblockTabClick(tab) {
  var wrapper = tab.closest('.chat-codeblock-wrapper');
  if (!wrapper) return;
  var pre = wrapper.querySelector('.chat-codeblock');
  var previewDiv = wrapper.querySelector('.chat-codeblock-preview');
  var idx = pre ? parseInt(pre.getAttribute('data-cb-index'), 10) : -1;
  var raw = (idx >= 0 && idx < _codeBlockStore.length) ? _codeBlockStore[idx] : '';
  var mode = tab.getAttribute('data-tab');
  wrapper.querySelectorAll('.chat-codeblock-tab').forEach(function(tabEl) { tabEl.classList.toggle('is-active', tabEl === tab); });
  if (mode === 'code') {
    if (pre) pre.style.display = '';
    if (previewDiv) { previewDiv.style.display = 'none'; _clearCodeBlockPreview(previewDiv); }
  } else {
    if (pre) pre.style.display = 'none';
    if (previewDiv) { previewDiv.style.display = 'block'; _renderCodeBlockPreview(previewDiv, raw); }
  }
}

document.addEventListener("click", function(e) {
  var reasoningBlock = e.target.closest(".chat-reasoning-block");
  if (reasoningBlock) {
    var sel = window.getSelection();
    if (sel && sel.toString().length > 0) return;
    _toggleReasoningBlock(reasoningBlock);
    return;
  }
  var copyBtn = e.target.closest(".chat-codeblock-copy");
  if (copyBtn) { _handleCodeblockCopyClick(copyBtn); return; }
  var collapseBtn = e.target.closest(".chat-codeblock-collapse");
  if (collapseBtn) {
    var wrapper2 = collapseBtn.closest('.chat-codeblock-wrapper');
    if (!wrapper2) return;
    var body = wrapper2.querySelector('.chat-codeblock-body');
    if (!body) return;
    var isCollapsed = body.style.display === 'none';
    body.style.display = isCollapsed ? '' : 'none';
    collapseBtn.textContent = isCollapsed ? '▲' : '▼';
    return;
  }
  var tab = e.target.closest(".chat-codeblock-tab");
  if (tab) { _handleCodeblockTabClick(tab); return; }
});

// ========================= Model List =========================
async function loadModelsList() {
  try {
    if (state.modelsLoaded && state.models.length) {
      if (typeof populateModelDropdowns === 'function') populateModelDropdowns(state.models);
      if (typeof renderModels === 'function') renderModels(state.models);
      return;
    }
    var result = await fetchJson('/v1/webui/summary');
    if (!result || !Array.isArray(result.models)) {
      if (typeof populateModelDropdowns === 'function') populateModelDropdowns(null, { error: true });
      return;
    }
    state.summary = result; state.modelsLoaded = true; state.models = result.models;
    if (typeof renderModels === 'function') renderModels(result.models);
    if (typeof populateModelDropdowns === 'function') populateModelDropdowns(result.models);
  } catch (error) {
    if (typeof populateModelDropdowns === 'function') populateModelDropdowns(null, { error: true });
  }
}

function clearChatMessages() {
  var container = document.getElementById("chatMessagesContainer");
  if (container) container.innerHTML = "";
  _userMsgCount = 0;
  chatConversationHistory = [];
  var report = document.getElementById("chatTestReport");
  if (report) { report.innerHTML = ""; report.classList.add("hidden"); }
  var inputSection = document.getElementById("chatInputSection");
  if (inputSection && !document.body.contains(inputSection)) document.body.appendChild(inputSection);
  saveChatState();
}

// ========================= History / DOM Utilities =========================
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

function _truncateHistoryFrom(historyIndex) {
  chatConversationHistory = chatConversationHistory.slice(0, historyIndex);
  _userMsgCount = _countUserMessages(chatConversationHistory);
}

function _cancelActiveStreaming() {
  var msg = document.getElementById("chatStreamingMessage");
  if (msg) msg.remove();
  _removeChatSpinner();
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

function _tOr(key, fallback) {
  var value = t(key);
  return value === key ? fallback : value;
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
