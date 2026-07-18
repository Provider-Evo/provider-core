/**
 * Chat attachments helper primitives extracted from attachments.js IIFE.
 * Free-standing helpers; _attachAttachmentsHelperMethods only wires references onto ctx.
 */

var ATTACH_IMAGE_EXT = { jpg: 1, jpeg: 1, png: 1, gif: 1, webp: 1, bmp: 1, svg: 1, avif: 1 };
var ATTACH_VIDEO_EXT = { mp4: 1, webm: 1, mov: 1, mkv: 1, avi: 1, m4v: 1 };
var ATTACH_AUDIO_EXT = { mp3: 1, wav: 1, ogg: 1, flac: 1, m4a: 1, aac: 1 };
var ATTACH_TEXT_EXT = {
  txt: 1, md: 1, mdx: 1, json: 1, js: 1, ts: 1, py: 1, html: 1, htm: 1, css: 1,
  xml: 1, yaml: 1, yml: 1, toml: 1, ini: 1, log: 1, sh: 1, bat: 1, ps1: 1,
  java: 1, go: 1, rs: 1, c: 1, cpp: 1, h: 1, sql: 1,
};
var ATTACH_IMAGE_MIMES = {
  jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', gif: 'image/gif',
  webp: 'image/webp', bmp: 'image/bmp', svg: 'image/svg+xml',
};

function _attach_t(key, fallback, vars) {
  if (typeof t === 'function') {
    try { return t(key, vars || {}); } catch (e) { /* ignore */ }
  }
  var s = fallback || key;
  if (vars) {
    Object.keys(vars).forEach(function(k) {
      s = s.replace('{{' + k + '}}', String(vars[k]));
    });
  }
  return s;
}

function _attach_esc(text) {
  if (typeof escapeHtml === 'function') return escapeHtml(text);
  var d = document.createElement('div');
  d.textContent = String(text || '');
  return d.innerHTML;
}

function _attach_ext(name) {
  return (name || '').split('.').pop().toLowerCase();
}

function _attach_isStripped(url) {
  return !url || url === '[stripped]';
}

function _attach_mimeFromName(name) {
  var ext = _attach_ext(name);
  if (ATTACH_IMAGE_MIMES[ext]) return ATTACH_IMAGE_MIMES[ext];
  if (ATTACH_VIDEO_EXT[ext]) return 'video/' + (ext === 'mov' ? 'quicktime' : ext);
  if (ATTACH_AUDIO_EXT[ext]) return 'audio/' + (ext === 'mp3' ? 'mpeg' : ext);
  if (ext === 'pdf') return 'application/pdf';
  if (ATTACH_TEXT_EXT[ext]) return 'text/plain';
  return 'application/octet-stream';
}

function _attach_kindFromNameAndMime(name, mime) {
  if (mime && mime.indexOf('image/') === 0) return 'image';
  if (mime && mime.indexOf('video/') === 0) return 'video';
  if (mime && mime.indexOf('audio/') === 0) return 'audio';
  var ext = _attach_ext(name);
  if (ATTACH_IMAGE_EXT[ext]) return 'image';
  if (ATTACH_VIDEO_EXT[ext]) return 'video';
  if (ATTACH_AUDIO_EXT[ext]) return 'audio';
  if (ATTACH_TEXT_EXT[ext] || ext === 'pdf') return 'text';
  return 'file';
}

function _attach_parseDataUrl(data) {
  var s = String(data || '');
  if (s.indexOf('data:') !== 0) return { mime: '', b64: s };
  var comma = s.indexOf(',');
  if (comma < 0) return { mime: '', b64: '' };
  var header = s.slice(0, comma);
  var mime = '';
  var m = header.match(/^data:([^;,]+)/);
  if (m) mime = m[1];
  return { mime: mime, b64: s.slice(comma + 1), full: s };
}

function _attach_dataUrlToBlob(dataUrl) {
  var parsed = _attach_parseDataUrl(dataUrl);
  if (parsed.full) {
    try {
      var bin = atob(parsed.b64);
      var arr = new Uint8Array(bin.length);
      for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
      return new Blob([arr], { type: parsed.mime || 'application/octet-stream' });
    } catch (e) { return null; }
  }
  return null;
}

function _attach_parseFileTextPart(text) {
  if (typeof text !== 'string' || text.indexOf('[file:') !== 0) return null;
  var nl = text.indexOf('\n');
  var header = nl >= 0 ? text.slice(0, nl) : text;
  var body = nl >= 0 ? text.slice(nl + 1) : '';
  var m = header.match(/^\[file:\s*([^\]]+)\]/);
  if (!m) return null;
  var name = m[1].trim() || 'file.txt';
  return {
    kind: 'text',
    name: name,
    url: '',
    textContent: body,
    mime: _attach_mimeFromName(name),
    size: body.length,
    stripped: false,
  };
}

function _attach_guessNameFromUrl(url, fallback) {
  if (!url || url.indexOf('data:') === 0) return fallback || 'image';
  try {
    var u = new URL(url, window.location.origin);
    var seg = u.pathname.split('/').pop();
    if (seg) return decodeURIComponent(seg);
  } catch (e) { /* ignore */ }
  return fallback || 'file';
}

function _attach_formatSize(bytes) {
  if (typeof formatFileSize === 'function') return formatFileSize(bytes || 0);
  var n = bytes || 0;
  if (n < 1024) return n + ' B';
  if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
  return (n / 1048576).toFixed(1) + ' MB';
}

function _attach_fileIcon(name) {
  if (typeof getFileIcon === 'function') return getFileIcon(name);
  return '\u{1F4CE}';
}

function _attachAttachmentsHelperMethods(ctx) {
  ctx.t = _attach_t;
  ctx.esc = _attach_esc;
  ctx.ext = _attach_ext;
  ctx.isStripped = _attach_isStripped;
  ctx.mimeFromName = _attach_mimeFromName;
  ctx.kindFromNameAndMime = _attach_kindFromNameAndMime;
  ctx.parseDataUrl = _attach_parseDataUrl;
  ctx.dataUrlToBlob = _attach_dataUrlToBlob;
  ctx.parseFileTextPart = _attach_parseFileTextPart;
  ctx.guessNameFromUrl = _attach_guessNameFromUrl;
  ctx.formatSize = _attach_formatSize;
  ctx.fileIcon = _attach_fileIcon;
}
