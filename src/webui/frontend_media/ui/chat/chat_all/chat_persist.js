// ========================= Media Persistence Helpers =========================
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

function _prepareMessagesForApi(messages, includeThinking) {
  var out = [];
  var passThinking = includeThinking !== false;
  for (var i = 0; i < messages.length; i++) {
    var m = messages[i];
    var msg = { role: m.role, content: m.content };
    if (m.role === 'assistant' && m.tool_calls && m.tool_calls.length) {
      msg.tool_calls = m.tool_calls;
    }
    if (passThinking && m.role === 'assistant' && m.reasoning_content) {
      msg.reasoning = m.reasoning_content;
      msg.reasoning_content = m.reasoning_content;
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

// ========================= State Variables =========================
var chatConversationHistory = [];
var _chatAbortController = null;
var _chatStateLoaded = null;
var _savedChatModel = null;
window._savedChatModel = null;
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
    sendBtn.onclick = function() { _chatAbortReason = 'user'; if (_chatAbortController) _chatAbortController.abort(); };
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
      chatConversationHistory.push({ role: "tool", tool_call_id: toolCalls[ti].id, content: "[WebUI test mode: tool call displayed but not executed]" });
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
  _saveChatStateTimer = setTimeout(function() { _saveChatStateTimer = null; flushSaveChatState(); }, 400);
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
      persistSave('chat.json', { history: persistHistory, userMsgCount: _userMsgCount, model: savedModel, protocol: savedProtocol, thinking: savedThinking, streaming: savedStreaming });
    }
  } catch (e) { console.debug("flushSaveChatState failed:", e); }
}

function _saveModelProtocol() {
  var modelSelect = document.getElementById("chatModelSelect");
  var protocolSelect = document.getElementById("chatProtocolSelect");
  try {
    var m = modelSelect ? modelSelect.value : "";
    var p = protocolSelect ? protocolSelect.value : "";
    var thinking = _isChatThinkingEnabled();
    var streaming = _isChatStreamingEnabled();
    localStorage.setItem("provider.webui.chatModel", m);
    localStorage.setItem("provider.webui.chatProtocol", p);
    localStorage.setItem("provider.webui.chatThinking", thinking ? "1" : "0");
    localStorage.setItem("provider.webui.chatStreaming", streaming ? "1" : "0");
    if (typeof persistSave === 'function') {
      persistSave('chat_model.json', { model: m, protocol: p, thinking: thinking, streaming: streaming });
    }
  } catch (e) { console.debug("_saveModelProtocol failed:", e); }
}

// ========================= loadChatState helpers =========================
async function _loadThinkingPref() {
  if (typeof persistLoad !== 'function') return;
  try {
    var mp = await persistLoad("chat_model.json");
    if (mp && typeof mp.thinking === "boolean") _applyChatThinkingEnabled(mp.thinking);
  } catch (e) { console.debug("loadChatState: failed to load chat_model.json thinking pref:", e); }
}

async function _loadStreamingPref() {
  if (typeof persistLoad !== 'function') return;
  try {
    var sp = await persistLoad("chat_model.json");
    if (sp && typeof sp.streaming === "boolean") _applyChatStreamingEnabled(sp.streaming);
  } catch (e) { console.debug("loadChatState: failed to load chat_model.json streaming pref:", e); }
}

async function _loadChatStateFromBackend() {
  if (typeof persistLoad !== 'function') return false;
  try {
    var persisted = await persistLoad('chat.json');
    if (!persisted || !persisted.history || !persisted.history.length) return false;
    chatConversationHistory = await _hydrateHistoryForDisplay(persisted.history);
    _userMsgCount = persisted.userMsgCount || 0;
    if (persisted.model) {
      _savedChatModel = persisted.model;
      window._savedChatModel = persisted.model;
      await loadModelsList();
    }
    if (persisted.protocol) {
      var protocolSelect = document.getElementById("chatProtocolSelect");
      if (protocolSelect) protocolSelect.value = persisted.protocol;
    }
    if (typeof persisted.thinking === "boolean") _applyChatThinkingEnabled(persisted.thinking);
    else await _loadThinkingPref();
    if (typeof persisted.streaming === "boolean") _applyChatStreamingEnabled(persisted.streaming);
    else await _loadStreamingPref();
    _renderChatHistoryFromMemory();
    return true;
  } catch (e) {
    console.debug("loadChatState backend path failed, falling back to localStorage:", e);
    chatConversationHistory = [];
    return false;
  }
}

async function _loadChatStateFromLocalStorage() {
  var savedModel = localStorage.getItem("provider.webui.chatModel");
  var savedProtocol = localStorage.getItem("provider.webui.chatProtocol");
  if (savedModel) {
    _savedChatModel = savedModel;
    window._savedChatModel = savedModel;
    var dd = window._dropdowns && window._dropdowns["chatModelSelect"];
    if (dd) dd.setValue(savedModel);
  }
  if (savedProtocol) {
    var ps = document.getElementById("chatProtocolSelect");
    if (ps) ps.value = savedProtocol;
  }
  var savedThinking = localStorage.getItem("provider.webui.chatThinking");
  if (savedThinking === "1" || savedThinking === "0") _applyChatThinkingEnabled(savedThinking === "1");
  else await _loadThinkingPref();
  var savedStreaming = localStorage.getItem("provider.webui.chatStreaming");
  if (savedStreaming === "1" || savedStreaming === "0") _applyChatStreamingEnabled(savedStreaming === "1");
  else await _loadStreamingPref();
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
    var containerEl = document.getElementById("chatMessagesContainer");
    if (containerEl && (!chatConversationHistory || !chatConversationHistory.length)) {
      containerEl.innerHTML = dom;
    }
  }
}

async function loadChatState() {
  _chatStateLoaded = (async function() {
    try {
      var loaded = await _loadChatStateFromBackend();
      if (!loaded) await _loadChatStateFromLocalStorage();
    } catch (e) { console.debug("loadChatState: unexpected error during state restoration:", e); }
    finally { _chatStateReady = true; }
  })();
  return _chatStateLoaded;
}
