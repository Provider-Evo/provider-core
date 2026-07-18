/**
 * Hydrate-side helpers for ChatMediaPersist: turn stored blob refs back
 * into data: URLs when loading chat history for display.
 * Split out of mediapersist.js; depends on mediapersist_util.js.
 */
async function _chatMediaHydrateDataUrl(url) {
  var U = ChatMediaPersistUtil;
  if (!url || url === '[stripped]') return url;
  if (!U.isRef(url)) return url;
  var id = U.refId(url);
  var resp = await fetch('/v1/webui/chat-media/' + encodeURIComponent(id), { credentials: 'same-origin' });
  if (!resp.ok) return '[stripped]';
  var blob = await resp.blob();
  return await U.blobToDataUrl(blob);
}

/**
 * Hydrate image_url / file sub-parts. Split out of _hydratePart to keep it under the line cap.
 */
async function _chatMediaHydratePartImageOrFile(copy) {
  if (copy.type === 'image_url' && copy.image_url && copy.image_url.url) {
    copy.image_url = Object.assign({}, copy.image_url, {
      url: await _chatMediaHydrateDataUrl(copy.image_url.url),
    });
    return copy;
  }
  if (copy.type === 'file' && copy.file) {
    var data = copy.file.data || copy.file.file_data || '';
    copy.file = Object.assign({}, copy.file, {
      data: await _chatMediaHydrateDataUrl(data),
    });
    return copy;
  }
  return null;
}

/**
 * Hydrate video_url / input_audio sub-parts. Split out of _hydratePart to keep it under the line cap.
 */
async function _chatMediaHydratePartVideoOrAudio(copy) {
  if (copy.type === 'video_url' && copy.video_url && copy.video_url.url) {
    copy.video_url = Object.assign({}, copy.video_url, {
      url: await _chatMediaHydrateDataUrl(copy.video_url.url),
    });
    return copy;
  }
  if (copy.type === 'input_audio' && copy.input_audio && copy.input_audio.data) {
    copy.input_audio = Object.assign({}, copy.input_audio, {
      data: await _chatMediaHydrateDataUrl(copy.input_audio.data),
    });
    return copy;
  }
  return null;
}

async function _chatMediaHydratePart(part) {
  if (!part || typeof part !== 'object') return part;
  var copy = Object.assign({}, part);
  var result = await _chatMediaHydratePartImageOrFile(copy);
  if (result) return result;
  result = await _chatMediaHydratePartVideoOrAudio(copy);
  if (result) return result;
  return copy;
}

var ChatMediaPersistHydrate = (function() {
  'use strict';

  async function _hydrateContent(content) {
    if (typeof content === 'string' || content == null) return content;
    if (!Array.isArray(content)) return content;
    var out = [];
    for (var i = 0; i < content.length; i++) {
      out.push(await _chatMediaHydratePart(content[i]));
    }
    return out;
  }

  async function hydrateHistory(history) {
    if (!history || !history.length) return [];
    var out = [];
    for (var i = 0; i < history.length; i++) {
      var m = history[i];
      var copy = { role: m.role };
      if (m.content !== undefined) {
        copy.content = m.role === 'user'
          ? await _hydrateContent(m.content)
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
    hydrateHistory: hydrateHistory,
  };
})();
