// Chat input handled by InputBox component (input-box.js)

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
    if (label) label.textContent = isHidden ? "收起参数" : "查看参数";
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
          '<button class="chat-codeblock-copy" type="button">复制</button>' +
          '<button class="chat-codeblock-collapse" type="button" title="折叠/展开">\u25B2</button>' +
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
    html += '<span class="chat-tool-dropdown-label">查看参数</span>';
    html += '<svg class="chat-tool-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>';
    html += '</div>';
    html += '<pre class="chat-tool-args" id="' + toolId + '" style="display:none;">' + escapeHtml(formattedArgs) + '</pre>';
    html += '</div>';
  }
  html += '</div>';
  return html;
}

function appendChatMessage(role, content, options) {
  options = options || {};
  var container = document.getElementById("chatMessagesContainer");
  if (!container) return;
  var msg = document.createElement("div");
  msg.className = "chat-message chat-message-" + role;
  if (options.toolCalls && options.toolCalls.length > 0) {
    var toolHtml = _buildToolCallsHtml(options.toolCalls);
    msg.innerHTML = toolHtml + '<div class="chat-assistant-text">' + renderWithCodeBlocks(content) + '</div>';
  } else if (role === "assistant") {
    msg.setAttribute("data-raw", content);
    msg.innerHTML = renderWithCodeBlocks(content);
  } else if (role === "user") {
    var histIdx = _userMsgCount++;
    msg.setAttribute("data-hist-index", histIdx);
    msg.setAttribute("data-raw", content);
    var userHtml = '';
    if (content) userHtml += escapeHtml(content);
    if (options.files && options.files.length > 0) {
      userHtml += buildFileCardsHtml(options.files);
      msg.setAttribute("data-files", JSON.stringify(options.files));
    }
    msg.innerHTML = userHtml || escapeHtml(content);
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
  if ((role === "user" || role === "assistant") && !options.isStreaming) {
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

function updateStreamingMessage(content) {
  var msg = document.getElementById("chatStreamingMessage");
  if (!msg && content) {
    // First content arrived — create assistant message bubble before the spinner
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
    // Update spinner text to generating
    if (spinner) {
      var span = spinner.querySelector(".chat-loading-spinner");
      if (span) span.childNodes[span.childNodes.length - 1].textContent = "\u751F\u6210\u4E2D\u2026";
    }
  }
  if (!msg) return;

  if (content) {
    var elapsed = Date.now() - _spinnerCreatedAt;
    if (elapsed < _SPINNER_MIN_MS) {
      _pendingContent = content;
      if (!_pendingTimer) {
        _pendingTimer = setTimeout(function() {
          _pendingTimer = null;
          var m = document.getElementById("chatStreamingMessage");
          if (m && _pendingContent) {
            m.innerHTML = renderStreamingContent(_pendingContent);
            m.setAttribute("data-raw", _pendingContent);
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
    msg.innerHTML = renderStreamingContent(content);
    msg.setAttribute("data-raw", content);
  }
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

  if (toolCalls && toolCalls.length > 0) {
    var toolHtml = _buildToolCallsHtml(toolCalls);
    msg.innerHTML = toolHtml + '<div class="chat-assistant-text">' + renderWithCodeBlocks(content) + '</div>';
    msg.setAttribute("data-raw", content);
  } else if (!content) {
    // No tool calls and no text content — clear spinner if still showing
    msg.innerHTML = '';
    msg.setAttribute("data-raw", "");
  } else {
    // Re-render with full code block features (tabs, copy button)
    msg.innerHTML = renderWithCodeBlocks(content);
  }

  appendMessageActions("assistant", msg);
  saveChatState();
}

function escapeHtml(text) {
  var div = document.createElement("div");
  div.textContent = text || "";
  return div.innerHTML;
}

document.addEventListener("click", function(e) {
  // Code block copy button
  var btn = e.target.closest(".chat-codeblock-copy");
  if (btn) {
    var wrapper = btn.closest('.chat-codeblock-wrapper');
    var pre = wrapper ? wrapper.querySelector('.chat-codeblock') : null;
    var idx = pre ? parseInt(pre.getAttribute('data-cb-index'), 10) : -1;
    var raw = (idx >= 0 && idx < _codeBlockStore.length) ? _codeBlockStore[idx] : (pre ? pre.textContent : '');
    navigator.clipboard.writeText(raw).then(function() {
      btn.textContent = "已复制";
      btn.classList.add("is-copied");
      setTimeout(function() {
        btn.textContent = "复制";
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
      if (previewDiv) previewDiv.style.display = 'none';
    } else {
      // preview mode: render HTML in the preview div
      if (pre) pre.style.display = 'none';
      if (previewDiv) {
        previewDiv.style.display = '';
        previewDiv.innerHTML = raw;
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
    copy: { title: "复制", icon:
      '<rect x="9" y="9" width="13" height="13" rx="2"/>' +
      '<path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>' },
    edit: { title: "编辑", icon:
      '<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>' +
      '<path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>' },
    retry: { title: "重新生成", icon:
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
  msg.parentNode.insertBefore(bar, msg.nextSibling);
}

// ========================= Message Action Handlers =========================
document.addEventListener("click", function(e) {
  var btn = e.target.closest(".chat-msg-action");
  if (!btn) return;

  var action = btn.getAttribute("data-action");
  var role = btn.getAttribute("data-role");
  var msg = btn.closest(".chat-msg-actions");
  if (!msg) return;
  var bubble = msg.previousElementSibling;
  if (!bubble || !bubble.classList.contains("chat-message")) return;

  if (action === "copy") {
    var text = bubble.getAttribute("data-raw") || bubble.textContent || "";
    var origSvg = btn.innerHTML;
    navigator.clipboard.writeText(text).then(function() {
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

      var area = document.createElement("div");
      area.className = "chat-msg-edit-area";
      area.innerHTML =
        '<textarea class="chat-msg-edit-input" rows="4" style="background:var(--panel-alt);color:var(--text);border-color:var(--border);">' + escapeHtml(rawText) + '</textarea>' +
        '<div class="chat-msg-edit-actions">' +
        '<button class="chat-msg-edit-send" type="button" style="background:var(--accent);color:#fff;border-color:var(--accent);">确定</button>' +
        '<button class="chat-msg-edit-cancel" type="button" style="background:var(--panel-alt);color:var(--text);border-color:var(--border);">取消</button>' +
        '</div>';

      bubble.textContent = "";
      bubble.appendChild(area);

      var textarea = area.querySelector(".chat-msg-edit-input");
      textarea.focus();
      textarea.setSelectionRange(textarea.value.length, textarea.value.length);

      area.querySelector(".chat-msg-edit-cancel").addEventListener("click", function() {
        bubble.innerHTML = renderWithCodeBlocks(rawText);
      });

      area.querySelector(".chat-msg-edit-send").addEventListener("click", function() {
        var newText = textarea.value;
        bubble.innerHTML = renderWithCodeBlocks(newText);
      });
      return;
    }

    // Edit user message: find the user bubble, open editor, re-send on save
    var userMsg = bubble;
    if (!userMsg || !userMsg.classList.contains("chat-message-user")) return;
    if (userMsg.querySelector(".chat-msg-edit-area")) return;

    var rawText = userMsg.getAttribute("data-raw") || "";
    var histIdx = parseInt(userMsg.getAttribute("data-hist-index"), 10);

    var area = document.createElement("div");
    area.className = "chat-msg-edit-area";
    area.innerHTML =
      '<textarea class="chat-msg-edit-input" rows="2">' + escapeHtml(rawText) + '</textarea>' +
      '<div class="chat-msg-edit-actions">' +
      '<button class="chat-msg-edit-send" type="button">确定</button>' +
      '<button class="chat-msg-edit-cancel" type="button">取消</button>' +
      '</div>';

    userMsg.textContent = "";
    userMsg.appendChild(area);

    var textarea = area.querySelector(".chat-msg-edit-input");
    textarea.focus();
    textarea.setSelectionRange(textarea.value.length, textarea.value.length);

    area.querySelector(".chat-msg-edit-cancel").addEventListener("click", function() {
      userMsg.textContent = rawText;
    });

    area.querySelector(".chat-msg-edit-send").addEventListener("click", function() {
      var newText = textarea.value.trim();
      if (!newText) return;
      var container = document.getElementById("chatMessagesContainer");
      var allMsgs = container.querySelectorAll(".chat-message, .chat-msg-actions");
      var found = false;
      for (var i = 0; i < allMsgs.length; i++) {
        if (allMsgs[i] === userMsg) found = true;
        if (found) allMsgs[i].remove();
      }
      chatConversationHistory = chatConversationHistory.slice(0, histIdx);
      _userMsgCount = histIdx;
      sendChatMessage(newText);
    });
    return;
  }

  if (action === "retry") {
    var targetUserMsg = bubble;
    if (role === "assistant") {
      targetUserMsg = bubble.previousElementSibling;
      while (targetUserMsg && !targetUserMsg.classList.contains("chat-message-user")) {
        targetUserMsg = targetUserMsg.previousElementSibling;
      }
    }
    if (!targetUserMsg) return;

    var rawText = targetUserMsg.getAttribute("data-raw") || "";
    var histIdx = parseInt(targetUserMsg.getAttribute("data-hist-index"), 10);
    if (!rawText) return;

    var removeFrom = targetUserMsg;
    var container = document.getElementById("chatMessagesContainer");
    var allMsgs = container.querySelectorAll(".chat-message, .chat-msg-actions");
    var found = false;
    for (var i = 0; i < allMsgs.length; i++) {
      if (allMsgs[i] === removeFrom) found = true;
      if (found) allMsgs[i].remove();
    }

    chatConversationHistory = chatConversationHistory.slice(0, histIdx);
    _userMsgCount = histIdx;

    sendChatMessage(rawText);
    return;
  }
});

function clearChatMessages() {
  var container = document.getElementById("chatMessagesContainer");
  if (container) {
    container.innerHTML = "";
  }
  _userMsgCount = 0;
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
    if (dropdown) dropdown.setOptions([{ value: '', text: '加载失败' }], false);
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
    if (span) span.textContent = 'Stop';
    if (svg) svg.innerHTML = '<rect x="6" y="6" width="12" height="12" rx="2" fill="currentColor" stroke="none"/>';
    sendBtn.onclick = function() {
      if (_chatAbortController) _chatAbortController.abort();
    };
  } else {
    if (span) span.textContent = 'Send';
    if (svg) svg.innerHTML = '<path d="M6 12L3.269 3.125A59.769 59.769 0 0121.485 12 59.768 59.768 0 013.27 20.875L5.999 12Zm0 0h7.5"/>';
    sendBtn.onclick = function() { window._chatInputBox._doSend(); };
  }
}

function saveChatState() {
  try {
    var container = document.getElementById("chatMessagesContainer");
    var html = container ? container.innerHTML : "";
    var modelSelect = document.getElementById("chatModelSelect");
    var protocolSelect = document.getElementById("chatProtocolSelect");
    var savedModel = modelSelect ? modelSelect.value : "";
    var savedProtocol = protocolSelect ? protocolSelect.value : "xml";
    localStorage.setItem("provider.webui.chatHistory", JSON.stringify(chatConversationHistory));
    localStorage.setItem("provider.webui.chatDom", html);
    localStorage.setItem("provider.webui.userMsgCount", String(_userMsgCount));
    localStorage.setItem("provider.webui.chatModel", savedModel);
    localStorage.setItem("provider.webui.chatProtocol", savedProtocol);
    // Persist to backend
    if (typeof persistSave === 'function') {
      persistSave('chat.json', {
        history: chatConversationHistory,
        userMsgCount: _userMsgCount,
        model: savedModel,
        protocol: savedProtocol
      });
    }
  } catch (e) { console.debug("saveChatState failed:", e); }
}

function _saveModelProtocol() {
  var modelSelect = document.getElementById("chatModelSelect");
  var protocolSelect = document.getElementById("chatProtocolSelect");
  var m = modelSelect ? modelSelect.value : "";
  var p = protocolSelect ? protocolSelect.value : "xml";
  try {
    localStorage.setItem("provider.webui.chatModel", m);
    localStorage.setItem("provider.webui.chatProtocol", p);
    if (typeof persistSave === 'function') {
      persistSave('chat_model.json', { model: m, protocol: p });
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
          chatConversationHistory = persisted.history;
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
          // Re-render messages from history
          var container = document.getElementById("chatMessagesContainer");
          if (container) {
            container.innerHTML = '';
            _userMsgCount = 0;
            for (var i = 0; i < chatConversationHistory.length; i++) {
              var msg = chatConversationHistory[i];
              if (msg.role === "tool") continue;
              try {
                appendChatMessage(msg.role, msg.content || '', {
                  toolCalls: msg.tool_calls,
                  files: msg.files || null
                });
              } catch (renderErr) {
                console.error('[loadChatState] Failed to render message', i, msg.role, renderErr);
              }
            }
          }
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
    // Fallback to localStorage
    var hist = localStorage.getItem("provider.webui.chatHistory");
    var dom = localStorage.getItem("provider.webui.chatDom");
    var count = localStorage.getItem("provider.webui.userMsgCount");
    if (hist) {
      try {
        var parsed = JSON.parse(hist);
        if (Array.isArray(parsed) && parsed.length > 0) {
          chatConversationHistory = parsed;
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

async function sendChatMessage(text, files) {
  if (!text && (!files || files.length === 0)) return;
  // Ensure chat history is loaded before sending
  if (_chatStateLoaded) {
    try { await _chatStateLoaded; } catch (e) { console.debug("sendChatMessage: error awaiting chat state load:", e); }
    _chatStateLoaded = null;
  }

  var model = document.getElementById("chatModelSelect").value;
  var protocol = document.getElementById("chatProtocolSelect").value;
  if (!model) { toast("请先选择模型", "error"); return; }

  // Add user message
  var displayText = text || '';
  var fileMeta = null;
  if (files && files.length > 0) {
    fileMeta = files.map(function(f) { return { name: f.name, size: f.size }; });
  }
  appendChatMessage("user", displayText, { files: fileMeta });
  var histEntry = { role: "user", content: text || '' };
  if (fileMeta) histEntry.files = fileMeta;
  chatConversationHistory.push(histEntry);
  saveChatState();

  try {
    var tools = getToolsDefinition();
    var historySlice = chatConversationHistory.slice(-20);
    var body = {
      model: model,
      messages: historySlice,
      stream: true,
      protocol: protocol
    };
    if (tools.length > 0) {
      body.tools = tools;
    }


    // 创建超时控制器（默认 120 秒）
    var timeoutMs = 120000;
    var abortController = new AbortController();
    _chatAbortController = abortController;
    _setStreaming(true);
    var timeoutId = setTimeout(function() {
      abortController.abort();
    }, timeoutMs);

    // Show loading spinner while waiting for response
    _spinnerCreatedAt = Date.now();
    var container = document.getElementById("chatMessagesContainer");
    var spinnerEl = document.createElement("div");
    spinnerEl.id = "_chatSpinner";
    spinnerEl.style.cssText = "display:inline-flex;align-items:center;gap:10px;margin:6px 0 6px 4px;";
    spinnerEl.innerHTML = '<span class="chat-loading-spinner">\u601D\u8003\u4E2D\u2026</span>';
    if (container) {
      container.appendChild(spinnerEl);
      container.scrollTop = container.scrollHeight;
    }

    var response = await fetch("/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: abortController.signal
    });

    clearTimeout(timeoutId); // 响应已开始，取消超时

    if (!response.ok) {
      _removeChatSpinner();
      var errText = await response.text();
      appendChatMessage("assistant", "Error " + response.status + ": " + errText);
      chatConversationHistory.pop();
      return;
    }

    // 设置流式读取超时（60 秒无数据）
    var streamTimeoutId = setTimeout(function() {
      abortController.abort();
      _removeChatSpinner();
      appendChatMessage("assistant", "流式响应超时（60 秒无数据）");
    }, 60000);

    function resetStreamTimeout() {
      clearTimeout(streamTimeoutId);
      streamTimeoutId = setTimeout(function() {
        abortController.abort();
        _removeChatSpinner();
        appendChatMessage("assistant", "流式响应超时（60 秒无数据）");
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
            _removeChatSpinner();
            appendChatMessage("assistant", "[" + errType + "] " + errMsg);
            chatConversationHistory.pop();
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

            if (choice.finish_reason) {
              finalizeStreamingMessage(toolCalls);
              var assistantMsg = { role: "assistant", content: assistantContent };
              if (reasoningContent) assistantMsg.reasoning_content = reasoningContent;
              if (toolCalls.length > 0) {
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
              assistantAdded = true;
              saveChatState();
            }
          }
        } catch (parseError) {
          // Ignore parse errors for non-JSON data lines
        }
      }
    }

    // 如果流结束但助手消息未添加到历史（某些服务器不发送 finish_reason），手动添加
    if (!assistantAdded && (assistantContent || toolCalls.length > 0)) {
      finalizeStreamingMessage(toolCalls);
      var fallbackMsg = { role: "assistant", content: assistantContent };
      if (reasoningContent) fallbackMsg.reasoning_content = reasoningContent;
      if (toolCalls.length > 0) {
        fallbackMsg.tool_calls = toolCalls;
        chatConversationHistory.push(fallbackMsg);
        for (var ti = 0; ti < toolCalls.length; ti++) {
          chatConversationHistory.push({
            role: "tool",
            tool_call_id: toolCalls[ti].id,
            content: "[WebUI test mode: tool call displayed but not executed]"
          });
        }
      } else {
        chatConversationHistory.push(fallbackMsg);
      }
      saveChatState();
    }

    // 如果流结束但完全没有内容，显示错误提示
    if (!assistantAdded && !assistantContent && toolCalls.length === 0) {
      _removeChatSpinner();
      appendChatMessage("assistant", "[stream_error] response ended with no content from model " + (body.model || "unknown"));
      chatConversationHistory.pop();
    }
  } catch (error) {
    _removeChatSpinner();
    if (error.name === 'AbortError') {
      appendChatMessage("assistant", "请求已取消或超时");
    } else {
      appendChatMessage("assistant", "请求失败: " + String(error));
    }
    chatConversationHistory.pop();
  } finally {
    clearTimeout(timeoutId);
    clearTimeout(streamTimeoutId);
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
      prompts = ["你好，请介绍一下你自己"];
    }
  }

  var report = document.getElementById("chatTestReport");
  if (!report) return;

  report.classList.remove("hidden");
  report.innerHTML = '<div style="padding:8px;"><div style="text-align:center;color:var(--muted);margin-bottom:12px;">批量测试: ' + prompts.length + ' 个 prompt | 模型: ' + escapeHtml(testModel) + ' | 协议: ' + protocol + '</div><div id="batchResultsList"></div></div>';

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
      + '<span class="text-[12px] text-muted" id="' + resultId + '-status">测试中...</span>'
      + '</div>'
      + '<div class="text-[13px] mb-2" style="color:var(--text);">' + escapeHtml(prompt.substring(0, 100) + (prompt.length > 100 ? '...' : '')) + '</div>'
      + '<div class="text-[12px] font-mono" style="color:var(--muted);min-height:20px;" id="' + resultId + '-content">...</div>'
      + '<div class="flex gap-3 mt-2 text-[11px] text-muted" id="' + resultId + '-stats">'
      + '<span>首包: <span id="' + resultId + '-ftt">-</span>ms</span>'
      + '<span>总时: <span id="' + resultId + '-total">-</span>ms</span>'
      + '<span>TPS: <span id="' + resultId + '-tps">-</span></span>'
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
        stream: true,
        protocol: protocol,
        temperature: temperature,
        max_tokens: maxTokens
      };
      if (tools.length > 0) body.tools = tools;

      var response = await fetch("/v1/chat/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(60000)
      });

      if (!response.ok) {
        document.getElementById(resultId + '-status').textContent = '失败: HTTP ' + response.status;
        document.getElementById(resultId + '-status').style.color = 'var(--err)';
        document.getElementById(resultId + '-content').textContent = 'HTTP ' + response.status;
        completedCount++;
        continue;
      }

      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";
      var content = "";
      var hasToolCalls = false;
      var completed = false;
      var contentEl = document.getElementById(resultId + '-content');
      var statusEl = document.getElementById(resultId + '-status');
      var startTime = Date.now();
      var firstTokenTime = null;
      var tokenCount = 0;

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

      var totalTime = Date.now() - startTime;
      var tps = tokenCount > 0 && totalTime > 0 ? (tokenCount / (totalTime / 1000)).toFixed(1) : '0';
      statusEl.textContent = hasToolCalls ? '通过 (有工具调用)' : '通过';
      statusEl.style.color = 'var(--ok)';
      contentEl.textContent = content.substring(0, 200) + (content.length > 200 ? '...' : '');
      resultDiv.dataset.fullContent = content;
      resultDiv.dataset.firstTokenTime = firstTokenTime ? (firstTokenTime - startTime) : '-';
      resultDiv.dataset.totalTime = totalTime;
      resultDiv.dataset.tokenCount = tokenCount;
      resultDiv.dataset.tps = tps;
      passCount++;
    } catch (error) {
      document.getElementById(resultId + '-status').textContent = '失败: ' + String(error).substring(0, 50);
      document.getElementById(resultId + '-status').style.color = 'var(--err)';
      document.getElementById(resultId + '-content').textContent = String(error);
      resultDiv.dataset.fullContent = String(error);
    }
    completedCount++;
  }

  // Add summary
  var summaryDiv = document.createElement('div');
  summaryDiv.style.cssText = 'margin-top:12px;text-align:right;font-size:13px;color:var(--muted);';
  summaryDiv.textContent = '测试完成: ' + passCount + '/' + prompts.length + ' 通过';
  resultsList.appendChild(summaryDiv);

  toast("批量测试完成: " + passCount + "/" + prompts.length + " 通过", passCount === prompts.length ? "ok" : "warn");
}

function showBatchResultDialog(prompt, fullContent, resultDiv) {
  var displayContent = fullContent || '<span style="color:var(--muted);">生成中...</span>';
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
    + '<span style="font-weight:600;font-size:15px;">测试结果详情</span>'
    + '<button style="background:none;border:none;cursor:pointer;font-size:20px;color:var(--muted);" id="batchResultCloseBtn">&times;</button>'
    + '</div>'
    + '<div style="padding:16px 20px;overflow-y:auto;flex:1;">'
    + '<div style="margin-bottom:12px;"><span style="font-size:12px;color:var(--muted);">Prompt:</span><div style="font-size:13px;margin-top:4px;color:var(--text);">' + escapeHtml(prompt) + '</div></div>'
    + '<div id="' + statsId + '" class="flex gap-4 mb-3 text-[12px] text-muted">'
    + '<span>首包: <strong>' + stats.ftt + '</strong>ms</span>'
    + '<span>总时: <strong>' + stats.total + '</strong>ms</span>'
    + '<span>Tokens: <strong>' + stats.tokens + '</strong></span>'
    + '<span>TPS: <strong>' + stats.tps + '</strong></span>'
    + '</div>'
    + '<div><span style="font-size:12px;color:var(--muted);">响应:</span><pre id="' + contentPreId + '" style="font-size:13px;margin-top:4px;white-space:pre-wrap;word-break:break-word;color:var(--text);background:var(--panel-alt);padding:12px;border-radius:8px;max-height:400px;overflow-y:auto;">' + (typeof displayContent === 'string' ? escapeHtml(displayContent) : displayContent) + '</pre></div>'
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
      pre.textContent = currentContent || '生成中...';
      statsEl.innerHTML = '<span>首包: <strong>' + (resultDiv.dataset.firstTokenTime || '-') + '</strong>ms</span>'
        + '<span>总时: <strong>' + (resultDiv.dataset.totalTime || resultDiv.dataset.elapsed || '-') + '</strong>ms</span>'
        + '<span>Tokens: <strong>' + (resultDiv.dataset.tokenCount || '0') + '</strong></span>'
        + '<span>TPS: <strong>' + (resultDiv.dataset.tps || '0') + '</strong></span>';
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
    desc: "获取指定城市的当前天气",
    params: '{\n  "city": {\n    "type": "string",\n    "description": "城市名称"\n  }\n}'
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
    showConfirmDialog("确定要清空所有工具定义吗？").then(function(ok) {
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
  if (modelEl) modelEl.addEventListener("change", function() { if (_chatStateReady) _saveModelProtocol(); });
  if (protocolEl) protocolEl.addEventListener("change", function() { if (_chatStateReady) _saveModelProtocol(); });
})();

