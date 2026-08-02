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
async function _loadChatModelPrefs() {
  var savedModel = null;
  var savedProtocol = null;
  if (typeof persistLoad === 'function') {
    try {
      var mp = await persistLoad('chat_model.json');
      if (mp) {
        if (mp.model) savedModel = mp.model;
        if (mp.protocol) savedProtocol = mp.protocol;
      }
    } catch (e) { console.debug('loadChatState: failed to load chat_model.json:', e); }
  }
  if (!savedModel) {
    try { savedModel = localStorage.getItem('provider.webui.chatModel'); } catch (e) { /* ignore */ }
  }
  if (!savedProtocol) {
    try { savedProtocol = localStorage.getItem('provider.webui.chatProtocol'); } catch (e) { /* ignore */ }
  }
  if (savedModel) {
    _savedChatModel = savedModel;
    window._savedChatModel = savedModel;
  }
  if (savedProtocol) {
    var protocolSelect = document.getElementById('chatProtocolSelect');
    if (protocolSelect) protocolSelect.value = savedProtocol;
    var protocolDropdown = window._dropdowns && window._dropdowns['chatProtocolSelect'];
    if (protocolDropdown) protocolDropdown.setValue(savedProtocol);
  }
}

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
      await _loadChatModelPrefs();
      var savedThinking = localStorage.getItem("provider.webui.chatThinking");
      if (savedThinking === "1" || savedThinking === "0") _applyChatThinkingEnabled(savedThinking === "1");
      else await _loadThinkingPref();
      var savedStreaming = localStorage.getItem("provider.webui.chatStreaming");
      if (savedStreaming === "1" || savedStreaming === "0") _applyChatStreamingEnabled(savedStreaming === "1");
      else await _loadStreamingPref();
      var loaded = await _loadChatStateFromBackend();
      if (!loaded) await _loadChatStateFromLocalStorage();
    } catch (e) { console.debug("loadChatState: unexpected error during state restoration:", e); }
    finally { _chatStateReady = true; }
  })();
  return _chatStateLoaded;
}
