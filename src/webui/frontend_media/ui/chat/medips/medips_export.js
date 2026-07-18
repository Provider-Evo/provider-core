/**
 * Export-side helpers for ChatMediaPersist: turn data: URLs embedded in
 * chat history into uploaded /v1/webui/chat-media blob refs.
 * Split out of mediapersist.js; depends on mediapersist_util.js.
 */
var ChatMediaPersistExport = (function() {
  'use strict';

  var S = {
    U: ChatMediaPersistUtil,
    _uploadCache: {},
  };

  // _exportPart attached from medips_exporthelpers.js (must load before
  // this file, see lazy_assets.js chat resource list).
  _attachMedipsExportMethods(S);
  var _exportPart = S._exportPart;

  async function _exportContent(content) {
    if (typeof content === 'string' || content == null) return content;
    if (!Array.isArray(content)) return content;
    var out = [];
    for (var i = 0; i < content.length; i++) {
      out.push(await _exportPart(content[i]));
    }
    return out;
  }

  async function exportHistory(history) {
    if (!history || !history.length) return [];
    var out = [];
    for (var i = 0; i < history.length; i++) {
      var m = history[i];
      var copy = { role: m.role };
      if (m.content !== undefined) {
        copy.content = m.role === 'user'
          ? await _exportContent(m.content)
          : (typeof m.content === 'string' ? m.content : JSON.parse(JSON.stringify(m.content)));
      }
      if (m.reasoning_content) copy.reasoning_content = m.reasoning_content;
      if (m.tool_calls) copy.tool_calls = m.tool_calls;
      if (m.tool_call_id) copy.tool_call_id = m.tool_call_id;
      if (m.files) copy.files = m.files;
      out.push(copy);
    }
    return out;
  }

  return {
    exportHistory: exportHistory,
  };
})();
