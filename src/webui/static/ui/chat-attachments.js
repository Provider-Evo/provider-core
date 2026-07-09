/**
 * Chat attachment tiles + media/file preview (NavoIM viewer + files preview patterns).
 */
var ChatAttachments = (function() {
  'use strict';

  var IMAGE_EXT = { jpg: 1, jpeg: 1, png: 1, gif: 1, webp: 1, bmp: 1, svg: 1, avif: 1 };
  var VIDEO_EXT = { mp4: 1, webm: 1, mov: 1, mkv: 1, avi: 1, m4v: 1 };
  var AUDIO_EXT = { mp3: 1, wav: 1, ogg: 1, flac: 1, m4a: 1, aac: 1 };
  var TEXT_EXT = {
    txt: 1, md: 1, mdx: 1, json: 1, js: 1, ts: 1, py: 1, html: 1, htm: 1, css: 1,
    xml: 1, yaml: 1, yml: 1, toml: 1, ini: 1, log: 1, sh: 1, bat: 1, ps1: 1,
    java: 1, go: 1, rs: 1, c: 1, cpp: 1, h: 1, sql: 1,
  };

  var IMAGE_MIMES = {
    jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', gif: 'image/gif',
    webp: 'image/webp', bmp: 'image/bmp', svg: 'image/svg+xml',
  };

  var _installed = false;
  var _viewerState = null;
  var _turnStore = new WeakMap();

  function _t(key, fallback, vars) {
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

  function _esc(text) {
    if (typeof escapeHtml === 'function') return escapeHtml(text);
    var d = document.createElement('div');
    d.textContent = String(text || '');
    return d.innerHTML;
  }

  function _ext(name) {
    return (name || '').split('.').pop().toLowerCase();
  }

  function _isStripped(url) {
    return !url || url === '[stripped]';
  }

  function _mimeFromName(name) {
    var ext = _ext(name);
    if (IMAGE_MIMES[ext]) return IMAGE_MIMES[ext];
    if (VIDEO_EXT[ext]) return 'video/' + (ext === 'mov' ? 'quicktime' : ext);
    if (AUDIO_EXT[ext]) return 'audio/' + (ext === 'mp3' ? 'mpeg' : ext);
    if (ext === 'pdf') return 'application/pdf';
    if (TEXT_EXT[ext]) return 'text/plain';
    return 'application/octet-stream';
  }

  function _kindFromNameAndMime(name, mime) {
    if (mime && mime.indexOf('image/') === 0) return 'image';
    if (mime && mime.indexOf('video/') === 0) return 'video';
    if (mime && mime.indexOf('audio/') === 0) return 'audio';
    var ext = _ext(name);
    if (IMAGE_EXT[ext]) return 'image';
    if (VIDEO_EXT[ext]) return 'video';
    if (AUDIO_EXT[ext]) return 'audio';
    if (TEXT_EXT[ext] || ext === 'pdf') return 'text';
    return 'file';
  }

  function _parseDataUrl(data) {
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

  function _dataUrlToBlob(dataUrl) {
    var parsed = _parseDataUrl(dataUrl);
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

  function _parseFileTextPart(text) {
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
      mime: _mimeFromName(name),
      size: body.length,
      stripped: false,
    };
  }

  function _guessNameFromUrl(url, fallback) {
    if (!url || url.indexOf('data:') === 0) return fallback || 'image';
    try {
      var u = new URL(url, window.location.origin);
      var seg = u.pathname.split('/').pop();
      if (seg) return decodeURIComponent(seg);
    } catch (e) { /* ignore */ }
    return fallback || 'file';
  }

  function collectAttachments(messageContent, filesMeta) {
    var items = [];
    var seen = {};
    var metaByName = {};
    if (filesMeta && filesMeta.length) {
      for (var m = 0; m < filesMeta.length; m++) {
        metaByName[filesMeta[m].name] = filesMeta[m];
      }
    }

    function push(item) {
      var key = item.kind + ':' + item.name + ':' + (item.url || item.textContent || '').slice(0, 32);
      if (seen[key]) return;
      seen[key] = true;
      items.push(item);
    }

    if (Array.isArray(messageContent)) {
      for (var i = 0; i < messageContent.length; i++) {
        var part = messageContent[i];
        if (!part || typeof part !== 'object') continue;

        if (part.type === 'image_url' && part.image_url) {
          var imgUrl = part.image_url.url || '';
          push({
            kind: 'image',
            name: _guessNameFromUrl(imgUrl, 'image.png'),
            url: imgUrl,
            mime: 'image/*',
            size: (metaByName[_guessNameFromUrl(imgUrl, 'image.png')] || {}).size || 0,
            stripped: _isStripped(imgUrl),
          });
          continue;
        }

        if (part.type === 'file' && part.file) {
          var fn = part.file.filename || part.file.name || 'attachment';
          var data = part.file.data || part.file.file_data || '';
          var parsed = _parseDataUrl(data);
          var mime = parsed.mime || _mimeFromName(fn);
          var kind = _kindFromNameAndMime(fn, mime);
          var blobUrl = (!_isStripped(data) && data.indexOf('data:') === 0) ? data : '';
          if (kind === 'text' && data && data.indexOf('data:') === 0) {
            try {
              var blob = _dataUrlToBlob(data);
              if (blob) {
                push({
                  kind: 'text',
                  name: fn,
                  url: data,
                  mime: mime,
                  size: blob.size || (metaByName[fn] || {}).size || 0,
                  stripped: false,
                  textContent: null,
                });
                continue;
              }
            } catch (e) { /* fall through */ }
          }
          push({
            kind: kind,
            name: fn,
            url: blobUrl || data,
            mime: mime,
            size: (metaByName[fn] || {}).size || 0,
            stripped: _isStripped(data),
          });
          continue;
        }

        if (part.type === 'text' && typeof part.text === 'string' && part.text.indexOf('[file:') === 0) {
          var textAtt = _parseFileTextPart(part.text);
          if (textAtt) push(textAtt);
        }
      }
    }

    if (filesMeta && filesMeta.length) {
      for (var f = 0; f < filesMeta.length; f++) {
        var fm = filesMeta[f];
        var fkind = _kindFromNameAndMime(fm.name, '');
        if (fkind === 'image') continue;
        var already = items.some(function(it) { return it.name === fm.name; });
        if (!already) {
          push({
            kind: fkind,
            name: fm.name,
            url: '',
            mime: _mimeFromName(fm.name),
            size: fm.size || 0,
            stripped: true,
          });
        }
      }
    }

    return items;
  }

  function _formatSize(bytes) {
    if (typeof formatFileSize === 'function') return formatFileSize(bytes || 0);
    var n = bytes || 0;
    if (n < 1024) return n + ' B';
    if (n < 1048576) return (n / 1024).toFixed(1) + ' KB';
    return (n / 1048576).toFixed(1) + ' MB';
  }

  function _fileIcon(name) {
    if (typeof getFileIcon === 'function') return getFileIcon(name);
    return '\u{1F4CE}';
  }

  function buildTilesHtml(items) {
    if (!items.length) return '';

    var html = '<div class="chat-att-grid">';
    for (var i = 0; i < items.length; i++) {
      var a = items[i];
      var idx = String(i);
      if (a.stripped) {
        html += '<div class="chat-att-tile chat-att-unavailable" data-chat-att="unavailable" data-att-index="' + idx + '">'
          + '<span class="chat-att-unavailable-icon">' + _fileIcon(a.name) + '</span>'
          + '<span class="chat-att-unavailable-text">' + _esc(a.name) + '</span>'
          + '<span class="chat-att-unavailable-hint">' + _esc(_t('chat.mediaNotRestored', '附件未从持久化恢复')) + '</span>'
          + '</div>';
        continue;
      }

      if (a.kind === 'image' && a.url) {
        html += '<button type="button" class="chat-att-tile chat-att-image" data-chat-att="image" data-att-index="' + idx + '"'
          + ' data-name="' + _esc(a.name) + '">'
          + '<img src="' + _esc(a.url) + '" alt="' + _esc(a.name) + '" loading="lazy" draggable="false">'
          + '</button>';
        continue;
      }

      if (a.kind === 'video' && a.url) {
        html += '<button type="button" class="chat-att-tile chat-att-video" data-chat-att="video" data-att-index="' + idx + '"'
          + ' data-name="' + _esc(a.name) + '">'
          + '<span class="chat-att-video-play" aria-hidden="true">'
          + '<svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>'
          + '</span>'
          + '<span class="chat-att-video-name">' + _esc(a.name) + '</span>'
          + '<span class="chat-att-video-size">' + _esc(_formatSize(a.size)) + '</span>'
          + '</button>';
        continue;
      }

      html += '<button type="button" class="chat-att-tile chat-file-card chat-att-file" data-chat-att="file" data-att-index="' + idx + '"'
        + ' data-name="' + _esc(a.name) + '"'
        + (a.textContent != null ? ' data-has-text="1"' : '')
        + '>'
        + '<span class="chat-file-icon">' + _fileIcon(a.name) + '</span>'
        + '<span class="chat-file-info">'
        + '<span class="chat-file-name">' + _esc(a.name) + '</span>'
        + '<span class="chat-file-size">' + _esc(_formatSize(a.size)) + '</span>'
        + '</span>'
        + '<span class="chat-att-open-icon" aria-hidden="true">'
        + '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>'
        + '</span>'
        + '</button>';
    }
    html += '</div>';
    return html;
  }

  function buildHtml(messageContent, filesMeta) {
    return buildTilesHtml(collectAttachments(messageContent, filesMeta));
  }

  function mountInto(attEl, turnEl, messageContent, filesMeta) {
    if (!attEl || !turnEl) return;
    var items = collectAttachments(messageContent, filesMeta);
    if (!items.length) {
      attEl.innerHTML = '';
      _turnStore.delete(turnEl);
      return;
    }
    _turnStore.set(turnEl, items);
    attEl.innerHTML = buildTilesHtml(items);
  }

  function _getItemsFromRoot(root) {
    var turn = root.closest('.chat-user-turn');
    if (turn && _turnStore.has(turn)) return _turnStore.get(turn);
    return [];
  }

  function _collectImagesFromRoot(root, items) {
    items = items || _getItemsFromRoot(root);
    var images = items.filter(function(it) {
      return it.kind === 'image' && !it.stripped && it.url;
    }).map(function(it) { return { url: it.url, name: it.name }; });
    if (images.length) return images;
    root.querySelectorAll('.chat-att-image').forEach(function(tile) {
      var img = tile.querySelector('img');
      var url = img && img.src ? img.src : '';
      if (url && !_isStripped(url)) {
        images.push({ url: url, name: tile.getAttribute('data-name') || 'image' });
      }
    });
    return images;
  }

  function _collectVideosFromRoot(root, items) {
    items = items || _getItemsFromRoot(root);
    return items.filter(function(it) {
      return it.kind === 'video' && !it.stripped && it.url;
    }).map(function(it) { return { url: it.url, name: it.name, mime: it.mime }; });
  }

  function _downloadUrl(url, name) {
    var a = document.createElement('a');
    a.href = url;
    a.download = name || 'download';
    a.rel = 'noopener';
    document.body.appendChild(a);
    a.click();
    a.remove();
  }

  function _closeViewer() {
    if (_viewerState && _viewerState.overlay) {
      _viewerState.overlay.remove();
      _viewerState = null;
    }
    document.removeEventListener('keydown', _onViewerKey);
  }

  function _onViewerKey(e) {
    if (!_viewerState) return;
    if (e.key === 'Escape') _closeViewer();
    if (_viewerState.mode === 'image') {
      if (e.key === 'ArrowRight') _viewerState.next();
      if (e.key === 'ArrowLeft') _viewerState.prev();
      if (e.key === '+' || e.key === '=') _viewerState.zoomIn();
      if (e.key === '-') _viewerState.zoomOut();
      if (e.key === '0') _viewerState.resetZoom();
    } else if (_viewerState.mode === 'video') {
      if (e.key === 'ArrowRight') _viewerState.next();
      if (e.key === 'ArrowLeft') _viewerState.prev();
    }
  }

  function _openImageViewer(images, index) {
    _closeViewer();
    if (!images.length) return;
    var state = {
      mode: 'image',
      images: images,
      index: Math.max(0, Math.min(index, images.length - 1)),
      zoom: 1,
      pan: { x: 0, y: 0 },
      dragging: false,
      dragStart: null,
    };

    var overlay = document.createElement('div');
    overlay.className = 'chat-media-viewer';
    overlay.innerHTML =
      '<div class="chat-media-viewer-toolbar">'
      + '<button type="button" class="chat-media-btn" data-act="zoom-out" title="Zoom out">-</button>'
      + '<span class="chat-media-zoom-label" data-zoom-label>100%</span>'
      + '<button type="button" class="chat-media-btn" data-act="zoom-in" title="Zoom in">+</button>'
      + '<button type="button" class="chat-media-btn" data-act="reset" title="Reset">'
      + '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M3 12a9 9 0 1 0 9-9"/><path d="M3 3v5h5"/></svg>'
      + '</button>'
      + '<button type="button" class="chat-media-btn" data-act="download" title="Download">'
      + '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
      + '</button>'
      + '<button type="button" class="chat-media-btn" data-act="close" title="Close">'
      + '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg>'
      + '</button>'
      + '</div>'
      + '<button type="button" class="chat-media-nav chat-media-nav-prev" data-act="prev" hidden>'
      + '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 18l-6-6 6-6"/></svg>'
      + '</button>'
      + '<button type="button" class="chat-media-nav chat-media-nav-next" data-act="next" hidden>'
      + '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M9 18l6-6-6-6"/></svg>'
      + '</button>'
      + '<div class="chat-media-stage" data-stage>'
      + '<img class="chat-media-image" data-image alt="">'
      + '</div>'
      + '<div class="chat-media-caption" data-caption></div>';

    document.body.appendChild(overlay);
    state.overlay = overlay;

    function render() {
      var cur = state.images[state.index];
      var img = overlay.querySelector('[data-image]');
      var cap = overlay.querySelector('[data-caption]');
      var zl = overlay.querySelector('[data-zoom-label]');
      img.src = cur.url;
      img.alt = cur.name || '';
      img.style.transform = 'scale(' + state.zoom + ') translate('
        + (state.pan.x / state.zoom) + 'px,' + (state.pan.y / state.zoom) + 'px)';
      cap.textContent = cur.name + (state.images.length > 1 ? '  ' + (state.index + 1) + '/' + state.images.length : '');
      zl.textContent = Math.round(state.zoom * 100) + '%';
      overlay.querySelector('[data-act="prev"]').hidden = state.images.length <= 1;
      overlay.querySelector('[data-act="next"]').hidden = state.images.length <= 1;
    }

    state.next = function() {
      state.index = (state.index + 1) % state.images.length;
      state.zoom = 1;
      state.pan = { x: 0, y: 0 };
      render();
    };
    state.prev = function() {
      state.index = (state.index - 1 + state.images.length) % state.images.length;
      state.zoom = 1;
      state.pan = { x: 0, y: 0 };
      render();
    };
    state.zoomIn = function() {
      state.zoom = Math.min(4, state.zoom + 0.25);
      render();
    };
    state.zoomOut = function() {
      state.zoom = Math.max(0.5, state.zoom - 0.25);
      render();
    };
    state.resetZoom = function() {
      state.zoom = 1;
      state.pan = { x: 0, y: 0 };
      render();
    };

    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) { _closeViewer(); return; }
      var act = e.target.closest('[data-act]');
      if (!act) return;
      var action = act.getAttribute('data-act');
      if (action === 'close') _closeViewer();
      if (action === 'prev') state.prev();
      if (action === 'next') state.next();
      if (action === 'zoom-in') state.zoomIn();
      if (action === 'zoom-out') state.zoomOut();
      if (action === 'reset') state.resetZoom();
      if (action === 'download') _downloadUrl(state.images[state.index].url, state.images[state.index].name);
    });

    var stage = overlay.querySelector('[data-stage]');
    stage.addEventListener('wheel', function(e) {
      e.preventDefault();
      var delta = e.deltaY > 0 ? -0.25 : 0.25;
      state.zoom = Math.max(0.5, Math.min(4, state.zoom + delta));
      render();
    }, { passive: false });

    stage.addEventListener('pointerdown', function(e) {
      if (state.zoom <= 1) return;
      state.dragging = true;
      state.dragStart = { x: e.clientX, y: e.clientY, px: state.pan.x, py: state.pan.y };
      stage.setPointerCapture(e.pointerId);
    });
    stage.addEventListener('pointermove', function(e) {
      if (!state.dragging || !state.dragStart) return;
      state.pan.x = state.dragStart.px + (e.clientX - state.dragStart.x);
      state.pan.y = state.dragStart.py + (e.clientY - state.dragStart.y);
      render();
    });
    stage.addEventListener('pointerup', function(e) {
      state.dragging = false;
      state.dragStart = null;
      try { stage.releasePointerCapture(e.pointerId); } catch (err) { /* ignore */ }
    });

    _viewerState = state;
    document.addEventListener('keydown', _onViewerKey);
    render();
  }

  function _openVideoViewer(videos, index) {
    _closeViewer();
    if (!videos.length) return;
    var state = {
      mode: 'video',
      videos: videos,
      index: Math.max(0, Math.min(index, videos.length - 1)),
    };

    var overlay = document.createElement('div');
    overlay.className = 'chat-media-viewer chat-media-viewer-video';
    overlay.innerHTML =
      '<div class="chat-media-viewer-toolbar">'
      + '<button type="button" class="chat-media-btn" data-act="download">'
      + '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
      + '</button>'
      + '<button type="button" class="chat-media-btn" data-act="close">'
      + '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 6 6 18M6 6l12 12"/></svg>'
      + '</button>'
      + '</div>'
      + '<button type="button" class="chat-media-nav chat-media-nav-prev" data-act="prev" hidden></button>'
      + '<button type="button" class="chat-media-nav chat-media-nav-next" data-act="next" hidden></button>'
      + '<video class="chat-media-video" controls playsinline data-video></video>'
      + '<div class="chat-media-caption" data-caption></div>';

    document.body.appendChild(overlay);
    state.overlay = overlay;

    function render() {
      var cur = state.videos[state.index];
      var video = overlay.querySelector('[data-video]');
      var cap = overlay.querySelector('[data-caption]');
      video.src = cur.url;
      if (cur.mime) video.type = cur.mime;
      cap.textContent = cur.name + (state.videos.length > 1 ? '  ' + (state.index + 1) + '/' + state.videos.length : '');
      overlay.querySelector('[data-act="prev"]').hidden = state.videos.length <= 1;
      overlay.querySelector('[data-act="next"]').hidden = state.videos.length <= 1;
      try { video.currentTime = 0; video.play(); } catch (e) { /* ignore */ }
    }

    state.next = function() {
      state.index = (state.index + 1) % state.videos.length;
      render();
    };
    state.prev = function() {
      state.index = (state.index - 1 + state.videos.length) % state.videos.length;
      render();
    };

    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) { _closeViewer(); return; }
      var act = e.target.closest('[data-act]');
      if (!act) return;
      var action = act.getAttribute('data-act');
      if (action === 'close') _closeViewer();
      if (action === 'prev') state.prev();
      if (action === 'next') state.next();
      if (action === 'download') _downloadUrl(state.videos[state.index].url, state.videos[state.index].name);
    });

    overlay.querySelector('[data-video]').addEventListener('click', function(e) { e.stopPropagation(); });

    _viewerState = state;
    document.addEventListener('keydown', _onViewerKey);
    render();
  }

  function _isHtmlFile(name) {
    var ext = _ext(name);
    return ext === 'html' || ext === 'htm';
  }

  function _isMarkdownFile(name) {
    return /\.(md|mdx)$/i.test(name || '');
  }

  function _renderMarkdownPreviewHtml(content) {
    var codeBlocks = [];
    var sentinel = '\x00CB';
    var processed = String(content || '').replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
      var idx = codeBlocks.length;
      codeBlocks.push({ lang: lang, code: code });
      return sentinel + idx + sentinel;
    });
    processed = _esc(processed);
    var lines = processed.split('\n');
    var resultLines = [];
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var h3 = line.match(/^###\s+(.+)$/);
      if (h3) { resultLines.push('<h3>' + h3[1] + '</h3>'); continue; }
      var h2 = line.match(/^##\s+(.+)$/);
      if (h2) { resultLines.push('<h2>' + h2[1] + '</h2>'); continue; }
      var h1 = line.match(/^#\s+(.+)$/);
      if (h1) { resultLines.push('<h1>' + h1[1] + '</h1>'); continue; }
      var ul = line.match(/^[-*]\s+(.+)$/);
      if (ul) { resultLines.push('<div class="files-preview-md-li">\u2022 ' + ul[1] + '</div>'); continue; }
      if (!line.trim()) { resultLines.push('<div class="files-preview-md-gap"></div>'); continue; }
      resultLines.push('<p>' + line + '</p>');
    }
    var html = resultLines.join('\n');
    for (var c = 0; c < codeBlocks.length; c++) {
      var block = codeBlocks[c];
      var langLabel = _esc(block.lang || 'text');
      var escapedCode = _esc(block.code);
      html = html.replace(sentinel + c + sentinel,
        '<pre class="files-preview-md-pre"><code class="language-' + langLabel + '">' + escapedCode + '</code></pre>');
    }
    return html;
  }

  function _mountHtmlPreview(host, htmlContent) {
    host.innerHTML = '';
    var frame = document.createElement('iframe');
    frame.className = 'files-preview-html-frame';
    frame.setAttribute('sandbox', 'allow-scripts');
    frame.setAttribute('referrerpolicy', 'no-referrer');
    frame.setAttribute('title', 'HTML preview');
    var blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' });
    var blobUrl = URL.createObjectURL(blob);
    host.setAttribute('data-preview-blob', blobUrl);
    frame.src = blobUrl;
    host.appendChild(frame);
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

  function _renderTextPane(bodyEl, content, name) {
    var wrap = document.createElement('div');
    wrap.className = 'files-preview-text-wrap';
    var gutter = document.createElement('div');
    gutter.className = 'files-preview-gutter';
    var pre = document.createElement('pre');
    pre.className = 'files-preview-code-pane';
    var code = document.createElement('code');
    var lines = String(content || '').split('\n');
    for (var i = 0; i < lines.length; i++) {
      var ln = document.createElement('span');
      ln.className = 'line';
      ln.textContent = String(i + 1);
      gutter.appendChild(ln);
    }
    code.textContent = content || '';
    var ext = _ext(name);
    code.className = 'language-' + (ext || 'text');
    pre.appendChild(code);
    wrap.appendChild(gutter);
    wrap.appendChild(pre);
    bodyEl.innerHTML = '';
    bodyEl.appendChild(wrap);
    if (window.hljs) {
      try { window.hljs.highlightElement(code); } catch (e) { /* ignore */ }
    }
  }

  async function _loadAttachmentContent(att) {
    if (att.textContent != null) return att.textContent;
    if (!att.url) return '';
    if (att.url.indexOf('data:') === 0) {
      var blob = _dataUrlToBlob(att.url);
      if (!blob) return '';
      if (att.kind === 'text' || _kindFromNameAndMime(att.name, att.mime) === 'text') {
        return await blob.text();
      }
      return '';
    }
    var res = await fetch(att.url);
    return await res.text();
  }

  function _openFilePreview(att) {
    var overlay = document.createElement('div');
    overlay.className = 'files-preview-overlay chat-att-preview-overlay';
    overlay.innerHTML =
      '<div class="files-preview-dialog">'
      + '<div class="files-preview-header">'
      + '<div class="files-preview-title">' + _esc(att.name) + '</div>'
      + '<div class="files-preview-modes" id="chatAttPreviewModes" hidden></div>'
      + '<div class="files-preview-actions">'
      + '<button type="button" class="files-preview-btn" id="chatAttPreviewDownload">' + _t('files.download', '下载') + '</button>'
      + '<button type="button" class="files-preview-btn" id="chatAttPreviewClose">' + _t('common.close', '关闭') + '</button>'
      + '</div></div>'
      + '<div class="files-preview-body"><div class="files-loading">' + _t('files.loading', '加载中...') + '</div></div>'
      + '</div>';

    document.body.appendChild(overlay);
    var modesEl = overlay.querySelector('#chatAttPreviewModes');
    var bodyEl = overlay.querySelector('.files-preview-body');
    var previewState = { kind: 'text', viewMode: 'source', content: '' };

    function closeOverlay() {
      _clearHtmlPreviewHost(bodyEl.querySelector('.files-preview-html-host'));
      overlay.remove();
      document.removeEventListener('keydown', onKey);
    }

    function onKey(e) {
      if (e.key === 'Escape') closeOverlay();
    }
    document.addEventListener('keydown', onKey);

    overlay.querySelector('#chatAttPreviewClose').addEventListener('click', closeOverlay);
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) closeOverlay();
    });
    overlay.querySelector('#chatAttPreviewDownload').addEventListener('click', function() {
      if (att.url) _downloadUrl(att.url, att.name);
      else if (att.textContent != null) {
        var blob = new Blob([att.textContent], { type: 'text/plain;charset=utf-8' });
        var u = URL.createObjectURL(blob);
        _downloadUrl(u, att.name);
        setTimeout(function() { URL.revokeObjectURL(u); }, 1000);
      }
    });

    function bindModes() {
      if (!modesEl) return;
      modesEl.hidden = false;
      if (previewState.kind === 'html') {
        modesEl.innerHTML =
          '<button type="button" class="files-preview-mode' + (previewState.viewMode === 'source' ? ' is-active' : '') + '" data-mode="source">' + _t('files.viewSource', '源码') + '</button>'
          + '<button type="button" class="files-preview-mode' + (previewState.viewMode === 'rendered' ? ' is-active' : '') + '" data-mode="rendered">' + _t('files.viewPreview', '预览') + '</button>';
      } else if (previewState.kind === 'markdown') {
        modesEl.innerHTML =
          '<button type="button" class="files-preview-mode' + (previewState.viewMode === 'source' ? ' is-active' : '') + '" data-mode="source">' + _t('files.viewSource', '源码') + '</button>'
          + '<button type="button" class="files-preview-mode' + (previewState.viewMode === 'rendered' ? ' is-active' : '') + '" data-mode="rendered">' + _t('files.viewRendered', '渲染') + '</button>';
      } else {
        modesEl.hidden = true;
        modesEl.innerHTML = '';
      }
      modesEl.querySelectorAll('.files-preview-mode').forEach(function(btn) {
        btn.addEventListener('click', function() {
          var mode = btn.getAttribute('data-mode');
          if (!mode || previewState.viewMode === mode) return;
          previewState.viewMode = mode;
          renderBody();
          bindModes();
        });
      });
    }

    function renderBody() {
      _clearHtmlPreviewHost(bodyEl.querySelector('.files-preview-html-host'));
      bodyEl.className = 'files-preview-body';
      var content = previewState.content;

      if (previewState.kind === 'html' && previewState.viewMode === 'rendered') {
        bodyEl.className = 'files-preview-body files-preview-body-html';
        var htmlHost = document.createElement('div');
        htmlHost.className = 'files-preview-html-host';
        bodyEl.appendChild(htmlHost);
        _mountHtmlPreview(htmlHost, content);
        return;
      }
      if (previewState.kind === 'markdown' && previewState.viewMode === 'rendered') {
        bodyEl.className = 'files-preview-body files-preview-body-markdown';
        bodyEl.innerHTML = '<div class="files-preview-markdown">' + _renderMarkdownPreviewHtml(content) + '</div>';
        return;
      }
      if (previewState.kind === 'audio' && att.url) {
        bodyEl.innerHTML = '<div class="chat-att-audio-wrap"><audio controls src="' + _esc(att.url) + '"></audio></div>';
        return;
      }
      _renderTextPane(bodyEl, content, att.name);
    }

    (async function() {
      try {
        if (att.kind === 'image' && att.url) {
          bodyEl.innerHTML = '<div class="files-preview-image"><img src="' + _esc(att.url) + '" alt="' + _esc(att.name) + '"></div>';
          return;
        }
        if (att.kind === 'video' && att.url) {
          bodyEl.innerHTML = '<div class="chat-att-video-wrap"><video controls playsinline src="' + _esc(att.url) + '"></video></div>';
          return;
        }
        if (att.kind === 'file' && att.url && att.url.indexOf('data:') === 0) {
          bodyEl.innerHTML =
            '<div class="files-preview-binary">'
            + '<div>' + _esc(_t('files.binaryFile', '二进制文件', { size: _formatSize(att.size) })) + '</div>'
            + '<button type="button" class="files-preview-btn" id="chatAttBinaryDl">' + _t('files.download', '下载') + '</button>'
            + '</div>';
          bodyEl.querySelector('#chatAttBinaryDl').addEventListener('click', function() {
            _downloadUrl(att.url, att.name);
          });
          return;
        }

        var content = await _loadAttachmentContent(att);
        previewState.content = content || '';
        if (_isHtmlFile(att.name)) {
          previewState.kind = 'html';
          previewState.viewMode = 'source';
        } else if (_isMarkdownFile(att.name)) {
          previewState.kind = 'markdown';
          previewState.viewMode = 'source';
        } else if (att.kind === 'audio') {
          previewState.kind = 'audio';
        } else {
          previewState.kind = 'text';
        }
        bindModes();
        renderBody();
      } catch (e) {
        bodyEl.innerHTML = '<div class="files-preview-binary"><div>' + _esc(_t('files.loadFileFailed', '加载失败', { error: e.message || String(e) })) + '</div></div>';
      }
    })();
  }

  function _openFileDetails(att) {
    var overlay = document.createElement('div');
    overlay.className = 'chat-att-details-overlay';
    overlay.innerHTML =
      '<div class="chat-att-details-dialog" role="dialog" aria-modal="true">'
      + '<div class="chat-att-details-header">'
      + '<div class="chat-att-details-title">' + _t('chat.fileDetailsTitle', '文件详情') + '</div>'
      + '<button type="button" class="chat-att-details-close" data-act="close">&times;</button>'
      + '</div>'
      + '<div class="chat-att-details-body">'
      + '<div class="chat-att-details-card">'
      + '<span class="chat-file-icon">' + _fileIcon(att.name) + '</span>'
      + '<div class="chat-att-details-meta">'
      + '<div class="chat-att-details-name">' + _esc(att.name) + '</div>'
      + '<div class="chat-att-details-mime">' + _esc(att.mime || _mimeFromName(att.name)) + '</div>'
      + '</div></div>'
      + '<div class="chat-att-details-grid">'
      + '<div class="chat-att-details-stat"><span>' + _t('chat.fileDetailsSize', '大小') + '</span><strong>' + _esc(_formatSize(att.size)) + '</strong></div>'
      + '<div class="chat-att-details-stat"><span>' + _t('chat.fileDetailsType', '类型') + '</span><strong>' + _esc(att.kind) + '</strong></div>'
      + '</div></div>'
      + '<div class="chat-att-details-footer">'
      + '<button type="button" class="btn btn-secondary" data-act="cancel">' + _t('common.cancel', '取消') + '</button>'
      + '<button type="button" class="btn btn-primary" data-act="preview">' + _t('files.preview', '预览') + '</button>'
      + '<button type="button" class="btn btn-primary" data-act="download">' + _t('files.download', '下载') + '</button>'
      + '</div></div>';

    document.body.appendChild(overlay);

    function close() {
      overlay.remove();
      document.removeEventListener('keydown', onKey);
    }
    function onKey(e) {
      if (e.key === 'Escape') close();
    }
    document.addEventListener('keydown', onKey);

    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) close();
      var act = e.target.closest('[data-act]');
      if (!act) return;
      var action = act.getAttribute('data-act');
      if (action === 'close' || action === 'cancel') close();
      if (action === 'preview') { close(); _openFilePreview(att); }
      if (action === 'download' && att.url) { _downloadUrl(att.url, att.name); close(); }
    });
  }

  function _handleClick(e) {
    var tile = e.target.closest('[data-chat-att]');
    if (!tile) return;
    var root = tile.closest('.chat-user-attachments');
    if (!root) return;
    var items = _getItemsFromRoot(root);
    var kind = tile.getAttribute('data-chat-att');
    var index = parseInt(tile.getAttribute('data-att-index') || '0', 10);
    var att = items[index];

    if (kind === 'unavailable') {
      if (typeof toast === 'function') toast(_t('chat.mediaNotRestored', '附件未从持久化恢复，请重新上传'), 'warn');
      return;
    }

    if (kind === 'image') {
      var images = _collectImagesFromRoot(root, items);
      if (!images.length) {
        if (typeof toast === 'function') toast(_t('chat.mediaNotRestored', '附件未从持久化恢复，请重新上传'), 'warn');
        return;
      }
      var imgEl = tile.querySelector('img');
      var curUrl = imgEl && imgEl.src ? imgEl.src : '';
      var imgIndex = images.findIndex(function(it) { return it.url === curUrl; });
      _openImageViewer(images, imgIndex >= 0 ? imgIndex : 0);
      return;
    }

    if (kind === 'video') {
      var videos = _collectVideosFromRoot(root, items);
      if (!videos.length) {
        if (typeof toast === 'function') toast(_t('chat.mediaNotRestored', '附件未从持久化恢复，请重新上传'), 'warn');
        return;
      }
      var videoItems = items.filter(function(it) {
        return it.kind === 'video' && !it.stripped && it.url;
      });
      var attAt = items[index];
      var vidIndex = videoItems.indexOf(attAt);
      _openVideoViewer(videos, vidIndex >= 0 ? vidIndex : 0);
      return;
    }

    if (kind === 'file') {
      if (!att) {
        if (typeof toast === 'function') toast(_t('chat.mediaNotRestored', '附件未从持久化恢复，请重新上传'), 'warn');
        return;
      }
      if (att.kind === 'audio') {
        _openFilePreview(att);
        return;
      }
      if (att.kind === 'text' || att.textContent != null || _kindFromNameAndMime(att.name, att.mime) === 'text') {
        _openFilePreview(att);
      } else {
        _openFileDetails(att);
      }
    }
  }

  function install() {
    if (_installed) return;
    var container = document.getElementById('chatMessagesContainer');
    if (!container) return;
    container.addEventListener('click', _handleClick);
    _installed = true;
  }

  return {
    collectAttachments: collectAttachments,
    buildHtml: buildHtml,
    mountInto: mountInto,
    install: install,
  };
})();
