// ========================= User Turn / History Helpers =========================
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
  if (options.files && options.files.length) html += buildFileCardsHtml(options.files);
  if (options.messageContent != null) html += _buildUserImagesHtml(options.messageContent);
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
    var actionsEl = turn.querySelector(".chat-msg-actions");
    if (actionsEl) turn.insertBefore(att, actionsEl);
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
    turn.innerHTML = displayText ? escapeHtml(displayText) : '';
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

// ========================= Spinner / Streaming =========================
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
  if (spinner && container) container.insertBefore(msg, spinner);
  else if (container) container.appendChild(msg);
  if (spinner) {
    var span = spinner.querySelector(".chat-loading-spinner");
    if (span) span.childNodes[span.childNodes.length - 1].textContent = t('chat.generating');
  }
  return msg;
}

function _ensureAssistantTextEl(msg) {
  var el = msg.querySelector(".chat-assistant-text");
  if (!el) { el = document.createElement("div"); el.className = "chat-assistant-text"; msg.appendChild(el); }
  return el;
}

function _applyStreamingContent(msg, content) {
  if (!msg || !content) return;
  _ensureAssistantTextEl(msg).innerHTML = renderStreamingContent(content);
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
        if (m && _pendingContent) _applyStreamingContent(m, _pendingContent);
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
    if (node) msg.insertBefore(node, msg.firstChild);
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
  if (!msg && toolCalls && toolCalls.length > 0) msg = appendChatMessage("assistant", "", { isStreaming: false });
  if (!msg) { _removeChatSpinner(); return; }
  msg.removeAttribute("id");
  _removeChatSpinner();
  var content = msg.getAttribute("data-raw") || "";
  var reasoning = msg.getAttribute("data-reasoning") || "";
  msg.innerHTML = _assistantMessageHtml(content, { reasoning_content: reasoning, toolCalls: toolCalls && toolCalls.length ? toolCalls : [] });
  msg.setAttribute("data-raw", content);
  if (reasoning) msg.setAttribute("data-reasoning", reasoning);
  appendMessageActions("assistant", msg);
  saveChatState();
}

// ========================= Message Actions Component =========================
function appendMessageActions(role, msg) {
  var bar = document.createElement("div");
  bar.className = "chat-msg-actions chat-msg-actions-" + role;
  var allButtons = {
    copy: { title: t('common.copy'), icon: '<rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/>' },
    edit: { title: t('files.edit'), icon: '<path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>' },
    retry: { title: t('chat.retry'), icon: '<polyline points="23 4 23 10 17 10"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>' },
    speak: { title: t('voice.speak'), icon: '<polygon points="11 5 6 9 2 9 2 15 6 15 11 19 11 5"/><path d="M15.54 8.46a5 5 0 010 7.07"/><path d="M19.07 4.93a10 10 0 010 14.14"/>' }
  };
  var actions = (role === "user") ? ["copy", "edit"] : ["copy", "edit", "speak", "retry"];
  var html = "";
  for (var i = 0; i < actions.length; i++) {
    var key = actions[i];
    var b = allButtons[key];
    html += '<button class="chat-msg-action" data-action="' + key + '" data-role="' + role + '" type="button" title="' + b.title + '"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' + b.icon + '</svg></button>';
  }
  bar.innerHTML = html;
  if (role === "user" && msg.classList.contains("chat-user-turn")) msg.appendChild(bar);
  else msg.parentNode.insertBefore(bar, msg.nextSibling);
}

// ========================= Message Action Handlers =========================
function _handleCopyAction(actionBtn, bubble, role, userTurn) {
  var copyText = (userTurn ? userTurn.getAttribute("data-raw") : bubble.getAttribute("data-raw")) || bubble.textContent || "";
  if (role === "assistant") {
    var reasoning = bubble.getAttribute("data-reasoning") || "";
    if (reasoning) copyText = reasoning + (copyText ? "\n\n" + copyText : "");
  }
  var origSvg = actionBtn.innerHTML;
  _chatCopyToClipboard(copyText).then(function() {
    actionBtn.innerHTML = '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>';
    actionBtn.classList.add("is-active");
    setTimeout(function() { actionBtn.innerHTML = origSvg; actionBtn.classList.remove("is-active"); }, 1500);
  });
}

function _handleEditAssistantAction(bubble) {
  if (bubble.querySelector(".chat-msg-edit-area")) return;
  var rawText = bubble.getAttribute("data-raw") || bubble.textContent || "";
  var reasoningText = bubble.getAttribute("data-reasoning") || "";
  var area = document.createElement("div");
  area.className = "chat-msg-edit-area";
  area.innerHTML = '<textarea class="chat-msg-edit-input" rows="4" style="background:var(--panel-alt);color:var(--text);border-color:var(--border);">' + escapeHtml(rawText) + '</textarea>'
    + '<div class="chat-msg-edit-actions"><button class="chat-msg-edit-send" type="button" style="background:var(--accent);color:#fff;border-color:var(--accent);">' + escapeHtml(t('dialog.ok')) + '</button>'
    + '<button class="chat-msg-edit-cancel" type="button" style="background:var(--panel-alt);color:var(--text);border-color:var(--border);">' + escapeHtml(t('dialog.cancel')) + '</button></div>';
  bubble.textContent = "";
  bubble.appendChild(area);
  var ta = area.querySelector(".chat-msg-edit-input");
  ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length);
  area.querySelector(".chat-msg-edit-cancel").addEventListener("click", function() {
    bubble.innerHTML = _assistantMessageHtml(rawText, { reasoning_content: reasoningText });
    bubble.setAttribute("data-raw", rawText);
    if (reasoningText) bubble.setAttribute("data-reasoning", reasoningText);
  });
  area.querySelector(".chat-msg-edit-send").addEventListener("click", function() {
    var newText = ta.value;
    bubble.innerHTML = _assistantMessageHtml(newText, { reasoning_content: reasoningText });
    bubble.setAttribute("data-raw", newText);
    if (reasoningText) bubble.setAttribute("data-reasoning", reasoningText);
  });
}

function _handleEditUserAction(userTurn, actionsBar, userAnchor) {
  var editHost = userTurn ? userTurn.querySelector(".chat-message-user") : userAnchor;
  if (!editHost && userTurn) {
    editHost = document.createElement("div"); editHost.className = "chat-message chat-message-user";
    var attBlock = userTurn.querySelector(".chat-user-attachments");
    if (attBlock) userTurn.insertBefore(editHost, attBlock.nextSibling); else userTurn.insertBefore(editHost, actionsBar);
  }
  if (!editHost || editHost.querySelector(".chat-msg-edit-area")) return;
  var rawText2 = userAnchor.getAttribute("data-raw") || "";
  var resolved = _resolveUserHistoryEntry(userTurn || userAnchor);
  if (!resolved) return;
  var filesJson = userAnchor.getAttribute("data-files") || "";
  var msgContent = resolved.entry.content;
  var area2 = document.createElement("div"); area2.className = "chat-msg-edit-area";
  area2.innerHTML = '<textarea class="chat-msg-edit-input" rows="2">' + escapeHtml(rawText2) + '</textarea>'
    + '<div class="chat-msg-edit-actions"><button class="chat-msg-edit-send" type="button">' + escapeHtml(t('dialog.ok')) + '</button>'
    + '<button class="chat-msg-edit-cancel" type="button">' + escapeHtml(t('dialog.cancel')) + '</button></div>';
  editHost.textContent = ""; editHost.appendChild(area2);
  var ta2 = area2.querySelector(".chat-msg-edit-input");
  ta2.focus(); ta2.setSelectionRange(ta2.value.length, ta2.value.length);
  area2.querySelector(".chat-msg-edit-cancel").addEventListener("click", function() {
    _restoreUserMessageHtml(userAnchor, rawText2, filesJson, msgContent);
  });
  area2.querySelector(".chat-msg-edit-send").addEventListener("click", function() {
    var newTxt = ta2.value.trim();
    var merged = _mergeUserTextContent(newTxt, resolved.entry.content);
    if (!newTxt && !_contentHasMedia(merged)) return;
    _removeMessagesFromDom(userAnchor);
    _truncateHistoryFrom(resolved.historyIndex);
    _resendUserHistoryEntry(resolved.entry, newTxt);
  });
}

document.addEventListener("click", function(e) {
  var actionBtn = e.target.closest(".chat-msg-action");
  if (!actionBtn) return;
  var action = actionBtn.getAttribute("data-action");
  var role = actionBtn.getAttribute("data-role");
  var actionsBar = actionBtn.closest(".chat-msg-actions");
  if (!actionsBar) return;
  var userTurn = actionsBar.closest(".chat-user-turn");
  var bubble = userTurn ? (userTurn.querySelector(".chat-message-user") || userTurn) : actionsBar.previousElementSibling;
  if (!userTurn && (!bubble || !bubble.classList.contains("chat-message"))) return;
  if (action === "copy") { _handleCopyAction(actionBtn, bubble, role, userTurn); return; }
  if (action === "speak" && role === "assistant") { speakAssistantText(bubble.getAttribute("data-raw") || bubble.textContent || "", actionBtn); return; }
  if (action === "edit") {
    if (role === "assistant") { _handleEditAssistantAction(bubble); return; }
    _handleEditUserAction(userTurn, actionsBar, userTurn || bubble);
    return;
  }
  if (action === "retry") {
    var targetTurn = (role === "assistant") ? _findPrevUserTurn(actionsBar) : userTurn;
    if (!targetTurn) return;
    var resolved2 = _resolveUserHistoryEntry(targetTurn);
    if (!resolved2) { toast(_tOr('chat.retryNoHistory', '无法重试：找不到对应的历史消息'), 'warn'); return; }
    _removeMessagesFromDom(targetTurn);
    _truncateHistoryFrom(resolved2.historyIndex);
    _resendUserHistoryEntry(resolved2.entry, null);
  }
});
