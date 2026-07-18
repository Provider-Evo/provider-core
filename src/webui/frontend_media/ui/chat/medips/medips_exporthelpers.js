/**
 * ChatMediaPersistExport helper builders -- split out of medips_export.js to
 * keep the facade IIFE under the line cap. Attaches methods onto the shared
 * S state object via _attachMedipsExportMethods(S). Split further into
 * _attachMedipsExportUpload/_attachMedipsExportPart so each stays <=50 lines.
 */
function _attachMedipsExportUpload(S) {
  var U = S.U;
  var _uploadCache = S._uploadCache;

  async function _uploadBlob(bytes, name, mime) {
    var id = await U.sha256Hex(bytes);
    if (_uploadCache[id]) return U.makeRef(id);
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
    return U.makeRef(id);
  }

  async function _exportDataUrl(dataUrl, name) {
    if (!dataUrl || dataUrl === '[stripped]') return dataUrl;
    if (U.isRef(dataUrl)) return dataUrl;
    if (dataUrl.indexOf('data:') !== 0) return dataUrl;
    var parsed = U.parseDataUrl(dataUrl);
    if (!parsed) return dataUrl;
    var bytes = U.bytesFromB64(parsed.b64);
    return await _uploadBlob(bytes, name, parsed.mime);
  }

  S._exportDataUrl = _exportDataUrl;
}

function _attachMedipsExportPart(S) {
  var _exportDataUrl = S._exportDataUrl;

  async function _exportImagePart(copy) {
    var imgName = (copy.image_url.detail && copy.image_url.detail.filename) || 'image';
    copy.image_url = Object.assign({}, copy.image_url, {
      url: await _exportDataUrl(copy.image_url.url, imgName),
    });
    return copy;
  }

  async function _exportFilePart(copy) {
    var fn = copy.file.filename || copy.file.name || 'attachment';
    var data = copy.file.data || copy.file.file_data || '';
    copy.file = Object.assign({}, copy.file, {
      data: await _exportDataUrl(data, fn),
    });
    return copy;
  }

  async function _exportVideoPart(copy) {
    copy.video_url = Object.assign({}, copy.video_url, {
      url: await _exportDataUrl(copy.video_url.url, 'video'),
    });
    return copy;
  }

  async function _exportAudioPart(copy) {
    copy.input_audio = Object.assign({}, copy.input_audio, {
      data: await _exportDataUrl(copy.input_audio.data, 'audio'),
    });
    return copy;
  }

  async function _exportPart(part) {
    if (!part || typeof part !== 'object') return part;
    var copy = Object.assign({}, part);
    if (copy.type === 'image_url' && copy.image_url && copy.image_url.url) return _exportImagePart(copy);
    if (copy.type === 'file' && copy.file) return _exportFilePart(copy);
    if (copy.type === 'video_url' && copy.video_url && copy.video_url.url) return _exportVideoPart(copy);
    if (copy.type === 'input_audio' && copy.input_audio && copy.input_audio.data) return _exportAudioPart(copy);
    return copy;
  }

  S._exportPart = _exportPart;
}

function _attachMedipsExportMethods(S) {
  _attachMedipsExportUpload(S);
  _attachMedipsExportPart(S);
}
