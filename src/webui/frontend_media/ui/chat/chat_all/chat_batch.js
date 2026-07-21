// ========================= Batch Test Stream Helper =========================
function _applyBatchChunk(chunk, state, resultDiv, resultId, startTime) {
  var choices = chunk.choices || [];
  for (var ci = 0; ci < choices.length; ci++) {
    var delta = choices[ci].delta || {};
    if (delta.content) {
      if (state.firstTokenTime === null) state.firstTokenTime = Date.now();
      state.content += delta.content;
      state.tokenCount++;
      _updateBatchItemUi(resultDiv, resultId, state.content, startTime, state.firstTokenTime, state.tokenCount);
    }
    if (delta.tool_calls && delta.tool_calls.length > 0) state.hasToolCalls = true;
    if (choices[ci].finish_reason) state.completed = true;
  }
}

function _processBatchSseLines(lines, state, resultDiv, resultId, startTime) {
  for (var li = 0; li < lines.length; li++) {
    var line = lines[li].trim();
    if (!line || !line.startsWith("data: ")) continue;
    var data = line.slice(6);
    if (data === "[DONE]") { state.completed = true; return; }
    try {
      var chunk = JSON.parse(data);
      _applyBatchChunk(chunk, state, resultDiv, resultId, startTime);
    } catch (e) {}
  }
}

async function _readBatchStream(response, resultDiv, resultId, startTime) {
  var reader = response.body.getReader();
  var decoder = new TextDecoder();
  var buffer = "";
  var state = { content: "", hasToolCalls: false, tokenCount: 0, firstTokenTime: null, completed: false };

  while (true) {
    var readResult = await reader.read();
    if (readResult.done) break;
    buffer += decoder.decode(readResult.value, { stream: true });
    var lines = buffer.split("\n");
    buffer = lines.pop() || "";
    _processBatchSseLines(lines, state, resultDiv, resultId, startTime);
    if (state.completed) break;
  }
  return { content: state.content, hasToolCalls: state.hasToolCalls, tokenCount: state.tokenCount, firstTokenTime: state.firstTokenTime };
}

function _updateBatchItemUi(resultDiv, resultId, content, startTime, firstTokenTime, tokenCount) {
  var contentEl = document.getElementById(resultId + '-content');
  var fttEl = document.getElementById(resultId + '-ftt');
  var totalEl = document.getElementById(resultId + '-total');
  var tpsEl = document.getElementById(resultId + '-tps');
  if (contentEl) contentEl.textContent = content.substring(0, 200) + (content.length > 200 ? '...' : '');
  resultDiv.dataset.fullContent = content;
  resultDiv.dataset.firstTokenTime = firstTokenTime - startTime;
  resultDiv.dataset.tokenCount = tokenCount;
  resultDiv.dataset.elapsed = Date.now() - startTime;
  if (fttEl) fttEl.textContent = (firstTokenTime - startTime);
  if (totalEl) totalEl.textContent = (Date.now() - startTime);
  if (tpsEl && tokenCount > 0) {
    var elapsed = (Date.now() - startTime) / 1000;
    tpsEl.textContent = elapsed > 0 ? (tokenCount / elapsed).toFixed(1) : '0';
  }
}

function _makeBatchResultDiv(i, total, prompt) {
  var resultId = 'batch-result-' + i;
  var resultDiv = document.createElement('div');
  resultDiv.id = resultId;
  resultDiv.className = 'border border-border rounded-xl p-3 mb-2 cursor-pointer hover:border-accent transition';
  resultDiv.dataset.fullContent = '';
  resultDiv.dataset.prompt = prompt;
  resultDiv.innerHTML =
    '<div class="flex justify-between items-center mb-2">'
    + '<span class="text-[12px] text-muted">Prompt ' + (i + 1) + '/' + total + '</span>'
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
  return resultDiv;
}

async function _fetchBatchNonStream(response) {
  var payload = await response.json();
  if (payload.error) throw new Error(payload.error.message || "request failed");
  var batchMsg = ((payload.choices || [])[0] || {}).message || {};
  var content = batchMsg.content || "";
  if (batchMsg.reasoning_content) {
    content = t('chat.thinkingPrefix') + batchMsg.reasoning_content.substring(0, 80) + (batchMsg.reasoning_content.length > 80 ? "..." : "") + "\n" + content;
  }
  return {
    content: content,
    hasToolCalls: !!(batchMsg.tool_calls && batchMsg.tool_calls.length > 0),
    tokenCount: content ? Math.max(1, Math.floor(content.length / 4)) : 0,
    firstTokenTime: null
  };
}

async function _runOneBatchItem(prompt, i, prompts, resultDiv, body) {
  var resultId = 'batch-result-' + i;
  var statusEl = document.getElementById(resultId + '-status');
  var contentEl = document.getElementById(resultId + '-content');
  var startTime = Date.now();
  try {
    var itemBody = Object.assign({}, body, { messages: [] });
    if (body.systemPrompt) itemBody.messages.push({ role: "system", content: body.systemPrompt });
    itemBody.messages.push({ role: "user", content: prompt });
    delete itemBody.systemPrompt;
    var response = await fetch("/v1/chat/completions", {
      method: "POST", headers: { "Content-Type": "application/json" },
      credentials: "same-origin", body: JSON.stringify(itemBody),
      signal: AbortSignal.timeout(_getStreamIdleTimeoutMs())
    });
    if (!response.ok) {
      if (statusEl) { statusEl.textContent = t('chat.failedHttp', { status: response.status }); statusEl.style.color = 'var(--err)'; }
      if (contentEl) contentEl.textContent = 'HTTP ' + response.status;
      return null;
    }
    var content, hasToolCalls, tokenCount, firstTokenTime;
    if (!_isChatStreamingEnabled()) {
      var nonStreamResult = await _fetchBatchNonStream(response);
      content = nonStreamResult.content; hasToolCalls = nonStreamResult.hasToolCalls;
      tokenCount = nonStreamResult.tokenCount; firstTokenTime = nonStreamResult.firstTokenTime;
    } else {
      var streamResult = await _readBatchStream(response, resultDiv, resultId, startTime);
      content = streamResult.content; hasToolCalls = streamResult.hasToolCalls;
      tokenCount = streamResult.tokenCount; firstTokenTime = streamResult.firstTokenTime;
    }
    var totalTime = Date.now() - startTime;
    var tps = tokenCount > 0 && totalTime > 0 ? (tokenCount / (totalTime / 1000)).toFixed(1) : '0';
    if (statusEl) { statusEl.textContent = hasToolCalls ? t('chat.passedWithTools') : t('chat.passed'); statusEl.style.color = 'var(--ok)'; }
    if (contentEl) contentEl.textContent = content.substring(0, 200) + (content.length > 200 ? '...' : '');
    resultDiv.dataset.fullContent = content;
    resultDiv.dataset.firstTokenTime = firstTokenTime ? (firstTokenTime - startTime) : '-';
    resultDiv.dataset.totalTime = totalTime;
    resultDiv.dataset.tokenCount = tokenCount;
    resultDiv.dataset.tps = tps;
    return true;
  } catch (error) {
    if (statusEl) { statusEl.textContent = t('chat.failedWithError', { error: String(error).substring(0, 50) }); statusEl.style.color = 'var(--err)'; }
    if (contentEl) contentEl.textContent = String(error);
    resultDiv.dataset.fullContent = String(error);
    return null;
  }
}

// ========================= runChatTests =========================
async function runChatTests() {
  var modelSelect = document.getElementById("chatModelSelect");
  var protocolSelect = document.getElementById("chatProtocolSelect");
  var batchTextarea = document.getElementById("chatBatchPrompts");
  var testModel = modelSelect ? modelSelect.value : "qwen3.7-max";
  var protocol = protocolSelect ? protocolSelect.value : "xml";
  var temperature = (function() { var el = document.getElementById("batchTemperature"); return el ? parseFloat(el.value) || 0.7 : 0.7; })();
  var maxTokens = (function() { var el = document.getElementById("batchMaxTokens"); return el ? parseInt(el.value) || 1024 : 1024; })();
  var sysPrompt = (function() { var el = document.getElementById("batchSystemPrompt"); return el ? el.value.trim() : ""; })();
  var prompts = [];
  if (batchTextarea && batchTextarea.value.trim()) {
    prompts = batchTextarea.value.split('\n').map(function(l) { return l.trim(); }).filter(function(l) { return l.length > 0; });
  } else {
    var inputText = (window._chatInputBox && window._chatInputBox.getText()) || '';
    prompts = [inputText.trim() || t('chat.batchPromptsPlaceholder')];
  }
  var report = document.getElementById("chatTestReport");
  if (!report) return;
  report.classList.remove("hidden");
  report.innerHTML = '<div style="padding:8px;"><div style="text-align:center;color:var(--muted);margin-bottom:12px;">'
    + escapeHtml(t('chat.batchTestSummary', { count: prompts.length, model: testModel, protocol: protocol, thinking: _isChatThinkingEnabled() ? t('common.on') : t('common.off'), streaming: _isChatStreamingEnabled() ? t('common.on') : t('common.off') }))
    + '</div><div id="batchResultsList"></div></div>';
  var resultsList = document.getElementById("batchResultsList");
  var passCount = 0;
  var tools = getToolsDefinition();
  var body = {
    model: testModel,
    stream: _isChatStreamingEnabled(),
    protocol: protocol,
    temperature: temperature,
    max_tokens: maxTokens,
    extra_body: {
      thinking: _isChatThinkingEnabled(),
      include_thinking_in_history: _isChatThinkingEnabled()
    },
    systemPrompt: sysPrompt
  };
  if (tools.length > 0) body.tools = tools;
  for (var i = 0; i < prompts.length; i++) {
    var resultDiv = _makeBatchResultDiv(i, prompts.length, prompts[i]);
    resultsList.appendChild(resultDiv);
    var ok = await _runOneBatchItem(prompts[i], i, prompts, resultDiv, body);
    if (ok) passCount++;
  }
  var summaryDiv = document.createElement('div');
  summaryDiv.style.cssText = 'margin-top:12px;text-align:right;font-size:13px;color:var(--muted);';
  summaryDiv.textContent = t('chat.batchComplete', { passed: passCount, total: prompts.length });
  resultsList.appendChild(summaryDiv);
  toast(t('chat.batchCompleteToast', { passed: passCount, total: prompts.length }), passCount === prompts.length ? "ok" : "warn");
}

// ========================= showBatchResultDialog =========================
function showBatchResultDialog(prompt, fullContent, resultDiv) {
  var displayContent = fullContent || '<span style="color:var(--muted);">' + escapeHtml(t('chat.generating')) + '</span>';
  var stats = resultDiv ? { ftt: resultDiv.dataset.firstTokenTime || '-', total: resultDiv.dataset.totalTime || resultDiv.dataset.elapsed || '-', tokens: resultDiv.dataset.tokenCount || '0', tps: resultDiv.dataset.tps || '0' } : { ftt: '-', total: '-', tokens: '0', tps: '0' };
  var overlay = document.createElement('div');
  overlay.style.cssText = 'position:fixed;inset:0;z-index:100000;background:rgba(0,0,0,0.6);display:flex;align-items:center;justify-content:center;padding:24px;';
  var contentPreId = 'batch-result-content-' + Date.now();
  var statsId = 'batch-result-stats-' + Date.now();
  overlay.innerHTML = _buildBatchDialogHtml(prompt, stats, contentPreId, statsId, displayContent);
  document.body.appendChild(overlay);
  var updateInterval = _startBatchDialogPolling(resultDiv, contentPreId, statsId);
  document.getElementById('batchResultCloseBtn').addEventListener('click', function() {
    if (updateInterval) clearInterval(updateInterval);
    overlay.remove();
  });
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) { if (updateInterval) clearInterval(updateInterval); overlay.remove(); }
  });
}

function _buildBatchDialogHtml(prompt, stats, contentPreId, statsId, displayContent) {
  return '<div style="background:var(--panel);border:1px solid var(--border);border-radius:16px;max-width:700px;width:100%;max-height:80vh;display:flex;flex-direction:column;overflow:hidden;">'
    + '<div style="display:flex;justify-content:space-between;align-items:center;padding:16px 20px;border-bottom:1px solid var(--border);">'
    + '<span style="font-weight:600;font-size:15px;">' + escapeHtml(t('chat.batchResultTitle')) + '</span>'
    + '<button style="background:none;border:none;cursor:pointer;font-size:20px;color:var(--muted);" id="batchResultCloseBtn">&times;</button>'
    + '</div>'
    + '<div style="padding:16px 20px;overflow-y:auto;flex:1;">'
    + '<div style="margin-bottom:12px;"><span style="font-size:12px;color:var(--muted);">Prompt:</span>'
    + '<div style="font-size:13px;margin-top:4px;color:var(--text);">' + escapeHtml(prompt) + '</div></div>'
    + '<div id="' + statsId + '" class="flex gap-4 mb-3 text-[12px] text-muted">'
    + '<span>' + escapeHtml(t('chat.firstToken')) + ': <strong>' + stats.ftt + '</strong>ms</span>'
    + '<span>' + escapeHtml(t('chat.totalTime')) + ': <strong>' + stats.total + '</strong>ms</span>'
    + '<span>' + escapeHtml(t('chat.tokens')) + ': <strong>' + stats.tokens + '</strong></span>'
    + '<span>' + escapeHtml(t('chat.tps')) + ': <strong>' + stats.tps + '</strong></span>'
    + '</div>'
    + '<div><span style="font-size:12px;color:var(--muted);">' + escapeHtml(t('chat.responseLabel')) + '</span>'
    + '<pre id="' + contentPreId + '" style="font-size:13px;margin-top:4px;white-space:pre-wrap;word-break:break-word;color:var(--text);background:var(--panel-alt);padding:12px;border-radius:8px;max-height:400px;overflow-y:auto;">'
    + (typeof displayContent === 'string' ? escapeHtml(displayContent) : displayContent) + '</pre></div>'
    + '</div></div>';
}

function _startBatchDialogPolling(resultDiv, contentPreId, statsId) {
  if (!resultDiv) return null;
  return setInterval(function() {
    var pre = document.getElementById(contentPreId);
    var statsEl = document.getElementById(statsId);
    if (!pre || !statsEl) return;
    pre.textContent = resultDiv.dataset.fullContent || t('chat.generating');
    statsEl.innerHTML =
      '<span>' + escapeHtml(t('chat.firstToken')) + ': <strong>' + (resultDiv.dataset.firstTokenTime || '-') + '</strong>ms</span>'
      + '<span>' + escapeHtml(t('chat.totalTime')) + ': <strong>' + (resultDiv.dataset.totalTime || resultDiv.dataset.elapsed || '-') + '</strong>ms</span>'
      + '<span>' + escapeHtml(t('chat.tokens')) + ': <strong>' + (resultDiv.dataset.tokenCount || '0') + '</strong></span>'
      + '<span>' + escapeHtml(t('chat.tps')) + ': <strong>' + (resultDiv.dataset.tps || '0') + '</strong></span>';
  }, 200);
}
