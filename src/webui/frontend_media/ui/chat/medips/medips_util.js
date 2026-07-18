/**
 * Shared low-level helpers for ChatMediaPersist (hashing, data-url parsing,
 * ref-id encoding). Split out of mediapersist.js as a data/util sibling
 * file; must load before mediapersist_export.js / mediapersist_hydrate.js /
 * mediapersist.js.
 */
/**
 * 无 SubtleCrypto 环境下的哈希兜底路径。拆分自 ChatMediaPersistUtil 的 IIFE
 * 以控制函数行数。
 */
function _chatMediaPersistWeakHashFallback(bytes) {
  var s = '';
  for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
  var h = 0;
  for (var j = 0; j < s.length; j++) h = ((h << 5) - h + s.charCodeAt(j)) | 0;
  return ('00000000' + (h >>> 0).toString(16)).slice(-8) + ('00000000' + bytes.length.toString(16)).slice(-8);
}

var CHAT_MEDIA_PERSIST_REF_PREFIX = 'pv2-media://';

function _chatMediaParseDataUrl(dataUrl) {
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

function _chatMediaBytesFromB64(b64) {
  var bin = atob(b64);
  var arr = new Uint8Array(bin.length);
  for (var i = 0; i < bin.length; i++) arr[i] = bin.charCodeAt(i);
  return arr;
}

async function _chatMediaSha256Hex(bytes) {
  if (!window.crypto || !window.crypto.subtle) {
    return _chatMediaPersistWeakHashFallback(bytes);
  }
  var digest = await window.crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest)).map(function(b) {
    return b.toString(16).padStart(2, '0');
  }).join('').slice(0, 32);
}

function _chatMediaBlobToDataUrl(blob) {
  return new Promise(function(resolve, reject) {
    var reader = new FileReader();
    reader.onload = function() { resolve(String(reader.result || '')); };
    reader.onerror = function() { reject(new Error('read blob failed')); };
    reader.readAsDataURL(blob);
  });
}

var ChatMediaPersistUtil = (function() {
  'use strict';

  var REF_PREFIX = CHAT_MEDIA_PERSIST_REF_PREFIX;

  function _isRef(url) {
    return typeof url === 'string' && url.indexOf(REF_PREFIX) === 0;
  }

  function _refId(url) {
    return url.slice(REF_PREFIX.length);
  }

  function _makeRef(id) {
    return REF_PREFIX + id;
  }

  return {
    REF_PREFIX: REF_PREFIX,
    parseDataUrl: _chatMediaParseDataUrl,
    bytesFromB64: _chatMediaBytesFromB64,
    sha256Hex: _chatMediaSha256Hex,
    isRef: _isRef,
    refId: _refId,
    makeRef: _makeRef,
    blobToDataUrl: _chatMediaBlobToDataUrl,
  };
})();
