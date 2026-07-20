function _wrapHtmlPreviewDoc(raw) {
  var trimmed = String(raw || '').replace(/^﻿/, '').trim();
  if (/^<!DOCTYPE\s+html/i.test(trimmed) || /^<html[\s>]/i.test(trimmed)) {
    return trimmed;
  }
  return '<!DOCTYPE html><html><head><meta charset="utf-8">' +
    '<meta name="viewport" content="width=device-width,initial-scale=1">' +
    '<style>html,body{margin:0;padding:12px;overflow:auto;background:#fff;color:#111;word-wrap:break-word;}' +
    'img,video,canvas,svg,table{max-width:100%;height:auto;}</style></head><body>' +
    trimmed + '</body></html>';
}

function _clearHtmlPreviewHost(host) {
  if (!host) return;
  var oldUrl = host.getAttribute('data-preview-blob');
  if (oldUrl) {
    URL.revokeObjectURL(oldUrl);
    host.removeAttribute('data-preview-blob');
  }
  host.innerHTML = '';
}

function _renderHtmlPreviewHost(host, content) {
  _clearHtmlPreviewHost(host);
  var frame = document.createElement('iframe');
  frame.className = 'files-preview-html-frame';
  frame.setAttribute('sandbox', '');
  frame.setAttribute('referrerpolicy', 'no-referrer');
  frame.setAttribute('title', 'HTML preview');
  var blob = new Blob([_wrapHtmlPreviewDoc(content)], { type: 'text/html;charset=utf-8' });
  var blobUrl = URL.createObjectURL(blob);
  host.setAttribute('data-preview-blob', blobUrl);
  frame.src = blobUrl;
  host.appendChild(frame);
}

