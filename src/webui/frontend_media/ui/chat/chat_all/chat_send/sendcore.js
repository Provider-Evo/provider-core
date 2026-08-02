async function sendChatMessage(text, files, options) {
  options = options || {};
  if (!text && (!files || files.length === 0) && options.presetContent === undefined) return;
  if (_chatStateLoaded) {
    try { await _chatStateLoaded; } catch (e) { console.debug("sendChatMessage: error awaiting chat state load:", e); }
    _chatStateLoaded = null;
  }
  var model = document.getElementById("chatModelSelect").value;
  var protocol = document.getElementById("chatProtocolSelect").value;
  if (!model) { toast(t('chat.selectModelFirst'), "error"); return; }
  var messageContent;
  try {
    messageContent = options.presetContent !== undefined ? options.presetContent : await _buildUserMessageContent(text, files);
  } catch (e) { toast(t('chat.error', { error: e.message || String(e) }), 'error'); return; }
  var displayText = _userDisplayText(messageContent) || text || "";
  var fileMeta = _buildSendFileMeta(files, options);
  var historyIndex = chatConversationHistory.length;
  chatConversationHistory.push({ role: "user", content: messageContent, ...(fileMeta ? { files: fileMeta } : {}) });
  appendChatMessage("user", displayText, { files: fileMeta, historyIndex: historyIndex, messageContent: messageContent });
  if (_contentHasMedia(messageContent)) await flushSaveChatState(); else saveChatState();
  await _executeSendRequest(model, protocol);
}

function _buildSendFileMeta(files, options) {
  if (options.presetFiles !== undefined) return options.presetFiles || null;
  if (!files || !files.length) return null;
  var meta = files.filter(function(f) { return !_isImageAttachment(f.name, f.file && f.file.type); })
    .map(function(f) { return { name: f.name, size: _fileItemSize(f) }; });
  return meta.length ? meta : null;
}

function _finalizeSendStream(state, body) {
  if (state.error) {
    _cancelActiveStreaming();
    _appendErrorAssistantMessage("[" + (state.error.type || "error") + "] " + (state.error.message || "unknown error"));
    return;
  }
  if (state.assistantContent || state.reasoningContent || state.toolCalls.length) {
    finalizeStreamingMessage(state.toolCalls);
    _appendAssistantToHistory(state.assistantContent, state.reasoningContent, state.toolCalls);
    return;
  }
  _cancelActiveStreaming();
  _appendErrorAssistantMessage("[stream_error] response ended with no content from model " + (body.model || "unknown"));
}

async function _handleSendResponse(response, streamEnabled, body, abortController) {
  if (!response.ok) {
    _removeChatSpinner();
    if (response.status === 401) { window.location.href = "/login?next=" + encodeURIComponent(window.location.pathname); return; }
    _appendErrorAssistantMessage("Error " + response.status + ": " + (await response.text()));
    return;
  }
  if (!streamEnabled) {
    _removeChatSpinner();
    var result = await _handleSendNonStream(response);
    if (result) { appendChatMessage("assistant", result.assistantContent, { reasoning_content: result.reasoningContent, toolCalls: result.toolCalls }); _appendAssistantToHistory(result.assistantContent, result.reasoningContent, result.toolCalls); }
    return;
  }
  var streamIdleMs = _getStreamIdleTimeoutMs();
  var streamTimeoutId = setTimeout(function() { _chatAbortReason = 'timeout'; abortController.abort(); }, streamIdleMs);
  var state = await _readSendStream(response, function() {
    clearTimeout(streamTimeoutId);
    streamTimeoutId = setTimeout(function() { _chatAbortReason = 'timeout'; abortController.abort(); }, streamIdleMs);
  });
  clearTimeout(streamTimeoutId);
  _finalizeSendStream(state, body);
}

async function _executeSendRequest(model, protocol) {
  var tools = getToolsDefinition();
  var thinkingEnabled = _isChatThinkingEnabled();
  var historySlice = _prepareMessagesForApi(chatConversationHistory.slice(-20), thinkingEnabled);
  var streamEnabled = _isChatStreamingEnabled();
  var body = {
    model: model,
    messages: historySlice,
    stream: streamEnabled,
    protocol: protocol,
    extra_body: {
      thinking: thinkingEnabled,
      include_thinking_in_history: thinkingEnabled
    }
  };
  if (tools.length > 0) body.tools = tools;
  var abortController = new AbortController();
  _chatAbortController = abortController;
  _chatAbortReason = null;
  _setStreaming(true);
  var timeoutId = setTimeout(function() { abortController.abort(); }, 120000);
  _spinnerCreatedAt = Date.now();
  _showSendSpinner();
  try {
    var response = await fetch("/v1/turns", {
      method: "POST", headers: { "Content-Type": "application/json" },
      credentials: "same-origin", body: JSON.stringify(body), signal: abortController.signal
    });
    clearTimeout(timeoutId);
    await _handleSendResponse(response, streamEnabled, body, abortController);
  } catch (error) {
    _cancelActiveStreaming();
    if (error.name === 'AbortError') {
      _appendErrorAssistantMessage(_chatAbortReason === 'timeout' ? _streamTimeoutMessage() : t('chat.requestCancelled'));
    } else {
      _appendErrorAssistantMessage(t('chat.error', { error: String(error) }));
    }
  } finally {
    clearTimeout(timeoutId);
    _chatAbortReason = null;
    _setStreaming(false);
    _chatAbortController = null;
  }
}

function _showSendSpinner() {
  var chatContainer = document.getElementById("chatMessagesContainer");
  var spinnerEl = document.createElement("div");
  spinnerEl.id = "_chatSpinner";
  spinnerEl.style.cssText = "display:inline-flex;align-items:center;gap:10px;margin:6px 0 6px 4px;";
  spinnerEl.innerHTML = '<span class="chat-loading-spinner">' + escapeHtml(t('chat.thinkingInProgress')) + '</span>';
  if (chatContainer) { chatContainer.appendChild(spinnerEl); chatContainer.scrollTop = chatContainer.scrollHeight; }
}
