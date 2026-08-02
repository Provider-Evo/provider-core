// SSE stream parsing for chat send
function _applySseDelta(delta, state) {
  if (delta.content) { state.assistantContent += delta.content; updateStreamingMessage(state.assistantContent); }
  if (delta.reasoning) { state.reasoningContent += delta.reasoning; updateStreamingReasoning(state.reasoningContent); }
  if (!delta.tool_calls || !delta.tool_calls.length) return;
  for (var k = 0; k < delta.tool_calls.length; k++) {
    var tc = delta.tool_calls[k];
    if (tc.id !== undefined && tc.id !== null) {
      state.currentToolCall = { id: tc.id, index: tc.index || 0, function: { name: tc.function.name, arguments: "" } };
      state.toolCalls.push(state.currentToolCall);
    } else if (state.currentToolCall && tc.function && tc.function.arguments) {
      state.currentToolCall.function.arguments += tc.function.arguments;
    }
  }
}

function _processSseLines(lines, state) {
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i].trim();
    if (!line || !line.startsWith("data: ")) continue;
    var data = line.slice(6);
    if (data === "[DONE]") { state.finished = true; return; }
    try {
      var chunk = JSON.parse(data);
      if (chunk.error) { state.error = chunk.error; state.finished = true; return; }
      var choices = chunk.choices || [];
      for (var j = 0; j < choices.length; j++) {
        _applySseDelta(choices[j].delta || {}, state);
        if (choices[j].finish_reason) state.finished = true;
      }
    } catch (e) {}
  }
}

async function _readSendStream(response, resetTimeoutFn) {
  var reader = response.body.getReader();
  var decoder = new TextDecoder();
  var state = { assistantContent: "", reasoningContent: "", toolCalls: [], currentToolCall: null, finished: false, error: null };
  var buffer = "";
  while (true) {
    var result = await reader.read();
    if (result.done) break;
    resetTimeoutFn();
    buffer += decoder.decode(result.value, { stream: true });
    var lines = buffer.split("\n");
    buffer = lines.pop() || "";
    _processSseLines(lines, state);
    if (state.finished) break;
  }
  return state;
}

async function _handleSendNonStream(response) {
  var payload = await response.json();
  if (payload.error) {
    var perr = payload.error;
    _appendErrorAssistantMessage("[" + (perr.type || "error") + "] " + (perr.message || "unknown error"));
    return null;
  }
  var choice = (payload.choices || [])[0] || {};
  var message = choice.message || {};
  return { assistantContent: message.content || "", reasoningContent: message.reasoning || "", toolCalls: message.tool_calls || [] };
}
