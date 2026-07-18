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
    desc: t('chat.sampleToolDesc'),
    params: '{\n  "city": {\n    "type": "string",\n    "description": "' + t('chat.sampleCityDesc') + '"\n  }\n}'
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
    showConfirmDialog(t('chat.clearToolsConfirm')).then(function(ok) {
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

// ========================= Voice (TTS) =========================
var _chatTtsAudio = null;
var _chatTtsObjectUrl = null;
var _chatTtsButton = null;

function _stopChatTts() {
  if (_chatTtsAudio) {
    try { _chatTtsAudio.pause(); } catch (e) {}
    _chatTtsAudio = null;
  }
  if (_chatTtsObjectUrl) {
    URL.revokeObjectURL(_chatTtsObjectUrl);
    _chatTtsObjectUrl = null;
  }
  if (_chatTtsButton) {
    _chatTtsButton.classList.remove('is-active');
    _chatTtsButton = null;
  }
}

function _buildTtsInput(text) {
  var vs = typeof loadVoiceSettings === 'function' ? loadVoiceSettings() : {};
  var input = String(text || '').trim();
  if (!input) return '';
  var prompt = (vs.ttsPrompt || '').trim();
  if (prompt) return prompt + '\n\n' + input;
  return input;
}

async function speakAssistantText(text, button) {
  var vs = typeof loadVoiceSettings === 'function' ? loadVoiceSettings() : {};
  if (!vs.ttsModel) {
    toast(t('voice.ttsNotConfigured'), 'warning');
    return;
  }
  var plain = String(text || '').trim();
  if (!plain) return;

  if (_chatTtsButton === button && _chatTtsAudio && !_chatTtsAudio.paused) {
    _stopChatTts();
    return;
  }

  _stopChatTts();
  _chatTtsButton = button || null;
  if (_chatTtsButton) _chatTtsButton.classList.add('is-active');

  try {
    toast(t('voice.speaking'), 'info');
    var resp = await fetch('/v1/audio/speech', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: vs.ttsModel,
        input: _buildTtsInput(plain),
        response_format: 'mp3',
      }),
    });
    if (!resp.ok) {
      var errData = null;
      try { errData = await resp.json(); } catch (e) {}
      throw new Error((errData && errData.error) || resp.statusText || 'TTS failed');
    }
    var blob = await resp.blob();
    _chatTtsObjectUrl = URL.createObjectURL(blob);
    _chatTtsAudio = new Audio(_chatTtsObjectUrl);
    _chatTtsAudio.onended = function() { _stopChatTts(); };
    _chatTtsAudio.onerror = function() {
      toast(t('voice.ttsFailed', { error: 'playback error' }), 'error');
      _stopChatTts();
    };
    await _chatTtsAudio.play();
  } catch (err) {
    toast(t('voice.ttsFailed', { error: err.message || String(err) }), 'error');
    _stopChatTts();
  }
}
