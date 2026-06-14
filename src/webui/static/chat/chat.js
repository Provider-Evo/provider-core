// Chat input handled by InputBox component (input-box.js)


// ========================= Code Block Rendering =========================
/**
 * 将包含 ```code``` 块的文本转换为 HTML，保持代码缩进。
 * @param {string} text - 原始文本
 * @returns {string} HTML 字符串
 */
function renderWithCodeBlocks(text) {
  var escaped = escapeHtml(text);
  var codeBlocks = [];
  var sentinel = '\x00CB';
  var codeBlockRegex = /```(\w*)\n([\s\S]*?)```/g;
  var result = escaped.replace(codeBlockRegex, function(match, lang, code) {
    var langClass = lang ? ' class="language-' + lang.toLowerCase() + '"' : '';
    var langLabel = lang ? lang.toLowerCase() : 'code';
    var idx = codeBlocks.length;
    codeBlocks.push(
      '<div class="chat-codeblock-wrapper">' +
      '<div class="chat-codeblock-header">' +
      '<span class="chat-codeblock-lang">' + langLabel + '</span>' +
      '<button class="chat-codeblock-copy" type="button">复制</button>' +
      '</div>' +
      '<pre class="chat-codeblock"><code' + langClass + '>' + code + '</code></pre>' +
      '</div>'
    );
    return sentinel + idx + sentinel;
  });
  result = result.replace(/\n/g, '<br>');
  for (var i = 0; i < codeBlocks.length; i++) {
    result = result.replace(sentinel + i + sentinel, codeBlocks[i]);
  }
  return result;
}

// ========================= Chat Message Rendering =========================
var _userMsgCount = 0;

function appendChatMessage(role, content, options) {
  options = options || {};
  var container = document.getElementById("chatMessagesContainer");
  if (!container) return;
  var msg = document.createElement("div");
  msg.className = "chat-message chat-message-" + role;
  if (options.toolCalls && options.toolCalls.length > 0) {
    var toolHtml = '<div style="margin-bottom:6px;">';
    for (var i = 0; i < options.toolCalls.length; i++) {
      var tc = options.toolCalls[i];
      var name = (tc.function && tc.function.name) || "unknown";
      toolHtml += '<span class="chat-tool-btn">' + escapeHtml(name) + '</span> ';
    }
    toolHtml += '</div>';
    msg.innerHTML = toolHtml + renderWithCodeBlocks(content);
  } else if (role === "assistant") {
    msg.innerHTML = renderWithCodeBlocks(content);
  } else if (role === "user") {
    var histIdx = _userMsgCount++;
    msg.setAttribute("data-hist-index", histIdx);
    msg.setAttribute("data-raw", content);
    msg.textContent = content;
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

function updateStreamingMessage(content) {
  var msg = document.getElementById("chatStreamingMessage");
  if (!msg) {
    msg = appendChatMessage("assistant", "", { isStreaming: true });
  }
  // Only update innerHTML if there's actual content (preserve tool calls structure if present)
  if (content) {
    msg.innerHTML = renderWithCodeBlocks(content);
  }
  var container = document.getElementById("chatMessagesContainer");
  if (container) container.scrollTop = container.scrollHeight;
}

var _toolIdCounter = 0;

function finalizeStreamingMessage(toolCalls) {
  var msg = document.getElementById("chatStreamingMessage");
  // If no message element exists but there are tool calls, create one
  if (!msg && toolCalls && toolCalls.length > 0) {
    msg = appendChatMessage("assistant", "", { isStreaming: false });
  }
  if (!msg) return;
  msg.removeAttribute("id");

  if (toolCalls && toolCalls.length > 0) {
    var msgUid = ++_toolIdCounter;
    var content = msg.textContent || msg.innerText || "";
    var toolHtml = '<div class="chat-tools-container">';
    for (var i = 0; i < toolCalls.length; i++) {
      var tc = toolCalls[i];
      var name = (tc.function && tc.function.name) || "unknown";
      var args = (tc.function && tc.function.arguments) || "";
      var toolId = "tool-" + msgUid + "-" + i;
      // 尝试解析参数为格式化 JSON
      var formattedArgs = "";
      try {
        formattedArgs = JSON.stringify(JSON.parse(args), null, 2);
      } catch(e) {
        formattedArgs = args || "{}";
      }
      // 使用下拉框样式
      toolHtml += '<div class="chat-tool-dropdown">';
      toolHtml += '<div class="chat-tool-dropdown-trigger" data-target="' + toolId + '">';
      toolHtml += '<span class="chat-tool-btn">' + escapeHtml(name) + '</span> ';
      toolHtml += '<span class="chat-tool-dropdown-label">查看参数</span>';
      toolHtml += '<svg class="chat-tool-chevron" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg>';
      toolHtml += '</div>';
      toolHtml += '<pre class="chat-tool-args" id="' + toolId + '" style="display:none;">' + escapeHtml(formattedArgs) + '</pre>';
      toolHtml += '</div>';
    }
    toolHtml += '</div>';
    msg.innerHTML = toolHtml + '<div class="chat-assistant-text">' + renderWithCodeBlocks(content) + '</div>';

    // 使用事件委托绑定下拉框事件（更可靠）
    msg.addEventListener('click', function(e) {
      var trigger = e.target.closest('.chat-tool-dropdown-trigger');
      if (!trigger) return;
      var targetId = trigger.getAttribute('data-target');
      var argsEl = document.getElementById(targetId);
      var chevron = trigger.querySelector('.chat-tool-chevron');
      var label = trigger.querySelector('.chat-tool-dropdown-label');
      if (argsEl) {
        var isHidden = argsEl.style.display === 'none';
        argsEl.style.display = isHidden ? 'block' : 'none';
        trigger.setAttribute('aria-expanded', isHidden ? 'true' : 'false');
        if (label) label.textContent = isHidden ? '收起参数' : '查看参数';
        if (chevron) chevron.style.transform = isHidden ? 'rotate(180deg)' : 'rotate(0deg)';
      }
    });
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
  var btn = e.target.closest(".chat-codeblock-copy");
  if (!btn) return;
  var codeEl = btn.parentElement.nextElementSibling;
  if (!codeEl) return;
  var code = (codeEl.querySelector("code") || codeEl).textContent;
  navigator.clipboard.writeText(code).then(function() {
    btn.textContent = "已复制";
    btn.classList.add("is-copied");
    setTimeout(function() {
      btn.textContent = "复制";
      btn.classList.remove("is-copied");
    }, 2000);
  });
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
      var rawText = bubble.textContent || "";

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
      opts.push({ value: models[i].id, text: models[i].id });
      if (models[i].id === "qwen3.7-max") autoSelect = models[i].id;
    }
    dropdown.setOptions(opts, false);
    if (autoSelect) dropdown.setValue(autoSelect);
    else if (opts.length > 0) dropdown.setValue(opts[0].value);
  } catch (error) {
    var dropdown = window._dropdowns && window._dropdowns["chatModelSelect"];
    if (dropdown) dropdown.setOptions([{ value: '', text: '加载失败' }], false);
  }
}

// ========================= Send Chat Message (Streaming) =========================
var chatConversationHistory = [];

function saveChatState() {
  try {
    var container = document.getElementById("chatMessagesContainer");
    var html = container ? container.innerHTML : "";
    localStorage.setItem("provider.webui.chatHistory", JSON.stringify(chatConversationHistory));
    localStorage.setItem("provider.webui.chatDom", html);
    localStorage.setItem("provider.webui.userMsgCount", String(_userMsgCount));
  } catch (e) { /* quota exceeded or private mode */ }
}

function loadChatState() {
  try {
    var hist = localStorage.getItem("provider.webui.chatHistory");
    var dom = localStorage.getItem("provider.webui.chatDom");
    var count = localStorage.getItem("provider.webui.userMsgCount");
    if (hist) chatConversationHistory = JSON.parse(hist);
    if (count) _userMsgCount = parseInt(count, 10) || 0;
    if (dom) {
      var container = document.getElementById("chatMessagesContainer");
      if (container) container.innerHTML = dom;
    }
  } catch (e) { /* corrupt data */ }
}

async function sendChatMessage(text, files) {
  if (!text && (!files || files.length === 0)) return;

  var model = document.getElementById("chatModelSelect").value;
  var protocol = document.getElementById("chatProtocolSelect").value;
  if (!model) { toast("请先选择模型", "error"); return; }

  // Add user message
  var displayText = text || '';
  if (files && files.length > 0) {
    displayText += (displayText ? '\n' : '') + '[' + files.length + ' file(s) attached]';
  }
  appendChatMessage("user", displayText);
  chatConversationHistory.push({ role: "user", content: text || '' });
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

    // Debug: log conversation history state
    var roleSummary = historySlice.map(function(m) { return m.role; }).join(', ');
    log('发送 ' + historySlice.length + ' 条消息 [' + roleSummary + ']');

    // 创建超时控制器（默认 120 秒）
    var timeoutMs = 120000;
    var abortController = new AbortController();
    var timeoutId = setTimeout(function() {
      abortController.abort();
    }, timeoutMs);

    var response = await fetch("/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: abortController.signal
    });

    clearTimeout(timeoutId); // 响应已开始，取消超时

    if (!response.ok) {
      var errText = await response.text();
      appendChatMessage("system", "Error " + response.status + ": " + errText);
      chatConversationHistory.pop();
      return;
    }

    // 设置流式读取超时（60 秒无数据）
    var streamTimeoutId = setTimeout(function() {
      abortController.abort();
      appendChatMessage("system", "流式响应超时（60 秒无数据）");
    }, 60000);

    function resetStreamTimeout() {
      clearTimeout(streamTimeoutId);
      streamTimeoutId = setTimeout(function() {
        abortController.abort();
        appendChatMessage("system", "流式响应超时（60 秒无数据）");
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
            appendChatMessage("system", "[" + errType + "] " + errMsg);
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
                // Inject synthetic tool results (WebUI doesn't execute tools)
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
              log('助手回复已保存 (' + assistantContent.length + ' chars' + (reasoningContent ? ', ' + reasoningContent.length + ' thinking' : '') + ')');
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
    }

    // 如果流结束但完全没有内容，显示错误提示
    if (!assistantAdded && !assistantContent && toolCalls.length === 0) {
      appendChatMessage("system", "[stream_error] response ended with no content from model " + (body.model || "unknown"));
      chatConversationHistory.pop();
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      appendChatMessage("system", "请求已取消或超时");
    } else {
      appendChatMessage("system", "请求失败: " + String(error));
    }
    chatConversationHistory.pop();
  } finally {
    clearTimeout(timeoutId);
    clearTimeout(streamTimeoutId);
    sendBtn.disabled = false;
    btnText.textContent = "发送";
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
    });

    toolsList.appendChild(clone);
  });

  clearBtn.addEventListener("click", function() {
    if (toolsList.children.length === 0) return;
    showConfirmDialog("确定要清空所有工具定义吗？").then(function(ok) {
      if (ok) toolsList.innerHTML = "";
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

