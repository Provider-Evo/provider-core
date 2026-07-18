/**
 * Chat attachment video overlay viewer (playback, navigation).
 */
function _buildVideoViewerOverlay() {
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
  return overlay;
}

function _renderVideoViewer(overlay, state) {
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

function _bindVideoViewerEvents(ctx, overlay, state, render) {
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) { ctx.closeViewer(); return; }
    var act = e.target.closest('[data-act]');
    if (!act) return;
    var action = act.getAttribute('data-act');
    if (action === 'close') ctx.closeViewer();
    if (action === 'prev') state.prev();
    if (action === 'next') state.next();
    if (action === 'download') ctx.downloadUrl(state.videos[state.index].url, state.videos[state.index].name);
  });
  overlay.querySelector('[data-video]').addEventListener('click', function(e) { e.stopPropagation(); });
}

function _attachAttachmentsViewerVideoMethods(ctx) {
  function _openVideoViewer(videos, index) {
    ctx.closeViewer();
    if (!videos.length) return;
    var state = {
      mode: 'video',
      videos: videos,
      index: Math.max(0, Math.min(index, videos.length - 1)),
    };
    var overlay = _buildVideoViewerOverlay();
    document.body.appendChild(overlay);
    state.overlay = overlay;
    function render() { _renderVideoViewer(overlay, state); }
    state.next = function() { state.index = (state.index + 1) % state.videos.length; render(); };
    state.prev = function() { state.index = (state.index - 1 + state.videos.length) % state.videos.length; render(); };
    _bindVideoViewerEvents(ctx, overlay, state, render);
    ctx.setViewerState(state);
    ctx.bindViewerKeydown();
    render();
  }

  ctx.openVideoViewer = _openVideoViewer;
}
