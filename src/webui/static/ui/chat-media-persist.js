/**
 * Persist chat multimodal blobs to /v1/webui/chat-media and hydrate on load.
 */
var ChatMediaPersist = (function() {
  'use strict';

  var REF_PREFIX = 'pv2-media://';
  var _uploadCache = {};

  function _parseDataUrl(dataUrl) {
    var s = String(dataUrl || '');
    if (s.indexOf('data:') !== 0) return null;
    var comma = s.indexOf(',');
    if (comma < 0) return null;
    var header = s.slice(0, comma);
    var mime = 'application/octet-stream';
    var m = header.match(/^data:([^;,]+)/);
    if (m) mime = m[1];
    return { mime: mime, b64: s.slice(comma + 1) };
  }

  function _bytesFromB64(b64) {
    var bin = atob(b64);
    var arr = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
    return arr;
  }

  async function _sha256Hex(bytes) {
    if (!window.crypto || !window.crypto.subtle) {
      var s = '';
      for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
      var h = 0;
      for (var j = 0; j < s.length; j++) h = ((h << 5) - h + s.charCodeAt(j)) | 0;
      return ('00000000' + (h >>> 0).toString(16)).slice(-8) + ('00000000' + bytes.length.toString(16)).slice(-8);
    }
    var digest = await window.crypto.subtle.digest('SHA-256', bytes);
    return Array.from(new Uint8Array(digest)).map(function(b) {
      return b.toString(16).padStart(2, '0');
    }).join('').slice(0, 32);
  }

  function _isRef(url) {
    return typeof url === 'string' && url.indexOf(REF_PREFIX) === 0;
  }

  function _refId(url) {
    return url.slice(REF_PREFIX.length);
  }

  function _makeRef(id) {
    return REF_PREFIX + id;
  }

  async function _uploadBlob(bytes, name, mime) {
    var id = await _sha256Hex(bytes);
    if (_uploadCache[id]) return _makeRef(id);
    var b64 = '';
    var chunk = 0x8000;
    for (var i = 0; i < bytes.length; i += chunk) {
      b64 += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
    }
    b64 = btoa(b64);
    var resp = await fetch('/v1/webui/chat-media', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id: id, name: name || 'attachment', mime: mime || 'application/octet-stream', data_b64: b64 }),
    });
    if (!resp.ok) {
      var detail = await resp.text();
      throw new Error('chat media upload failed: ' + resp.status + ' ' + detail.slice(0, 200));
    }
    _uploadCache[id] = true;
    return _makeRef(id);
  }

  async function _exportDataUrl(dataUrl, name) {
    if (!dataUrl || dataUrl === '[stripped]') return dataUrl;
    if (_isRef(dataUrl)) return dataUrl;
    if (dataUrl.indexOf('data:') !== 0) return dataUrl;
    var parsed = _parseDataUrl(dataUrl);
    if (!parsed) return dataUrl;
    var bytes = _bytesFromB64(parsed.b64);
    return await _uploadBlob(bytes, name, parsed.mime);
  }

  async function _exportPart(part) {
    if (!part || typeof part !== 'object') return part;
    var copy = Object.assign({}, part);
    if (copy.type === 'image_url' && copy.image_url && copy.image_url.url) {
      var imgName = (copy.image_url.detail && copy.image_url.detail.filename) || 'image';
      copy.image_url = Object.assign({}, copy.image_url, {
        url: await _exportDataUrl(copy.image_url.url, imgName),
      });
      return copy;
    }
    if (copy.type === 'file' && copy.file) {
      var fn = copy.file.filename || copy.file.name || 'attachment';
      var data = copy.file.data || copy.file.file_data || '';
      copy.file = Object.assign({}, copy.file, {
        data: await _exportDataUrl(data, fn),
      });
      return copy;
    }
    if (copy.type === 'video_url' && copy.video_url && copy.video_url.url) {
      copy.video_url = Object.assign({}, copy.video_url, {
        url: await _exportDataUrl(copy.video_url.url, 'video'),
      });
      return copy;
    }
    if (copy.type === 'input_audio' && copy.input_audio && copy.input_audio.data) {
      copy.input_audio = Object.assign({}, copy.input_audio, {
        data: await _exportDataUrl(copy.input_audio.data, 'audio'),
      });
      return copy;
    }
    return copy;
  }

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

  function _blobToDataUrl(blob) {
    return new Promise(function(resolve, reject) {
      var reader = new FileReader();
      reader.onload = function() { resolve(String(reader.result || '')); };
      reader.onerror = function() { reject(new Error('read blob failed')); };
      reader.readAsDataURL(blob);
    });
  }

  async function _hydrateDataUrl(url) {
    if (!url || url === '[stripped]') return url;
    if (!_isRef(url)) return url;
    var id = _refId(url);
    var resp = await fetch('/v1/webui/chat-media/' + encodeURIComponent(id), { credentials: 'same-origin' });
    if (!resp.ok) return '[stripped]';
    var blob = await resp.blob();
    return await _blobToDataUrl(blob);
  }

  async function _hydratePart(part) {
    if (!part || typeof part !== 'object') return part;
    var copy = Object.assign({}, part);
    if (copy.type === 'image_url' && copy.image_url && copy.image_url.url) {
      copy.image_url = Object.assign({}, copy.image_url, {
        url: await _hydrateDataUrl(copy.image_url.url),
      });
      return copy;
    }
    if (copy.type === 'file' && copy.file) {
      var data = copy.file.data || copy.file.file_data || '';
      copy.file = Object.assign({}, copy.file, {
        data: await _hydrateDataUrl(data),
      });
      return copy;
    }
    if (copy.type === 'video_url' && copy.video_url && copy.video_url.url) {
      copy.video_url = Object.assign({}, copy.video_url, {
        url: await _hydrateDataUrl(copy.video_url.url),
      });
      return copy;
    }
    if (copy.type === 'input_audio' && copy.input_audio && copy.input_audio.data) {
      copy.input_audio = Object.assign({}, copy.input_audio, {
        data: await _hydrateDataUrl(copy.input_audio.data),
      });
      return copy;
    }
    return copy;
  }

  async function _hydrateContent(content) {
    if (typeof content === 'string' || content == null) return content;
    if (!Array.isArray(content)) return content;
    var out = [];
    for (var i = 0; i < content.length; i++) {
      out.push(await _hydratePart(content[i]));
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
    REF_PREFIX: REF_PREFIX,
    isRef: _isRef,
    exportHistory: exportHistory,
    hydrateHistory: hydrateHistory,
  };
})();
