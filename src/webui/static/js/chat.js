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
      toolHtml += '<pre class="chat-tool-args" id="' + toolId + '" hidden>' + escapeHtml(formattedArgs) + '</pre>';
      toolHtml += '</div>';
    }
    toolHtml += '</div>';
    msg.innerHTML = toolHtml + '<div class="chat-assistant-text">' + renderWithCodeBlocks(content) + '</div>';

    // 绑定下拉框事件
    var triggers = msg.querySelectorAll('.chat-tool-dropdown-trigger');
    for (var j = 0; j < triggers.length; j++) {
      triggers[j].addEventListener('click', function() {
        var targetId = this.getAttribute('data-target');
        var argsEl = document.getElementById(targetId);
        var chevron = this.querySelector('.chat-tool-chevron');
        var label = this.querySelector('.chat-tool-dropdown-label');
        if (argsEl) {
          var isHidden = argsEl.hasAttribute('hidden');
          if (isHidden) {
            argsEl.removeAttribute('hidden');
            this.setAttribute('aria-expanded', 'true');
            label.textContent = '收起参数';
            chevron.style.transform = 'rotate(180deg)';
          } else {
            argsEl.setAttribute('hidden', '');
            this.setAttribute('aria-expanded', 'false');
            label.textContent = '查看参数';
            chevron.style.transform = 'rotate(0deg)';
          }
        }
      });
    }
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
    var body = {
      model: model,
      messages: chatConversationHistory.slice(-20),
      stream: true,
      protocol: protocol
    };
    if (tools.length > 0) {
      body.tools = tools;
    }

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
              if (toolCalls.length > 0) {
                chatConversationHistory.push({ role: "assistant", content: assistantContent, tool_calls: toolCalls });
              } else {
                chatConversationHistory.push({ role: "assistant", content: assistantContent });
              }
              assistantAdded = true;
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
      if (toolCalls.length > 0) {
        chatConversationHistory.push({ role: "assistant", content: assistantContent, tool_calls: toolCalls });
      } else {
        chatConversationHistory.push({ role: "assistant", content: assistantContent });
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

// ========================= Batch Test (qwen3.7-max + all protocols) =========================
async function runChatTests() {
  var modelSelect = document.getElementById("chatModelSelect");
  var protocolSelect = document.getElementById("chatProtocolSelect");
  var testModel = modelSelect ? modelSelect.value : "qwen3.7-max";
  var protocols = protocolSelect && protocolSelect.value ? [protocolSelect.value] : ["xml", "antml", "nous", "bracket"];
  var inputText = (window._chatInputBox && window._chatInputBox.getText()) || '';
  var testMessage = inputText.trim() || "请用工具调用测试一下当前协议是否正常工作。调用一个名为 echo 的工具，参数为 {\"text\": \"hello\"}。";

  var report = document.getElementById("chatTestReport");
  if (!report) return;

  report.classList.remove("hidden");
  report.innerHTML = '<div style="text-align:center;padding:12px;color:var(--muted);">正在批量测试...</div>';

  var results = [];

  for (var i = 0; i < protocols.length; i++) {
    var protocol = protocols[i];
    var status = "测试中...";
    report.innerHTML = '<div style="text-align:center;padding:12px;color:var(--muted);">正在测试: ' + protocol + ' (' + (i+1) + '/' + protocols.length + ')</div>';

    try {
      var body = {
        model: testModel,
        messages: [{ role: "user", content: testMessage }],
        stream: true
      };

      var response = await fetch("/v1/chat/completions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(30000)
      });

      if (!response.ok) {
        results.push({ protocol: protocol, status: "fail", error: "HTTP " + response.status });
        continue;
      }

      var reader = response.body.getReader();
      var decoder = new TextDecoder();
      var buffer = "";
      var content = "";
      var hasToolCalls = false;
      var completed = false;

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
              if (delta.content) content += delta.content;
              if (delta.tool_calls && delta.tool_calls.length > 0) hasToolCalls = true;
              if (choices[ci].finish_reason) completed = true;
            }
          } catch(e) {}
        }
        if (completed) break;
      }

      results.push({
        protocol: protocol,
        status: "pass",
        content: content.substring(0, 80) + (content.length > 80 ? "..." : ""),
        toolCalls: hasToolCalls ? "检测到工具调用" : "无工具调用"
      });
    } catch (error) {
      results.push({ protocol: protocol, status: "fail", error: String(error) });
    }
  }

  // Render report
  var tableHtml = '<table class="chat-test-report"><thead><tr><th>协议</th><th>状态</th><th>响应摘要</th><th>工具调用</th></tr></thead><tbody>';
  var passCount = 0;
  for (var r = 0; r < results.length; r++) {
    var row = results[r];
    var cls = row.status === "pass" ? "pass" : "fail";
    var statusIcon = row.status === "pass" ? "通过" : "失败";
    if (row.status === "pass") passCount++;
    tableHtml += '<tr class="' + cls + '"><td>' + escapeHtml(row.protocol) + '</td><td>' + statusIcon + '</td><td>' + escapeHtml(row.content || row.error || "") + '</td><td>' + escapeHtml(row.toolCalls || "") + '</td></tr>';
  }
  tableHtml += '</tbody></table>';
  tableHtml += '<div style="margin-top:8px;text-align:right;font-size:13px;color:var(--muted);">测试完成: ' + passCount + '/' + results.length + ' 通过</div>';
  report.innerHTML = tableHtml;

  toast("批量测试完成: " + passCount + "/" + results.length + " 通过", passCount === results.length ? "ok" : "warn");
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

