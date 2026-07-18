/**
 * Chat attachment image overlay viewer (zoom, pan, navigation).
 */
function _buildImageViewerOverlay() {
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
  return overlay;
}

function _renderImageViewer(overlay, state) {
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

function _bindImageViewerNav(state, render) {
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
  state.zoomIn = function() { state.zoom = Math.min(4, state.zoom + 0.25); render(); };
  state.zoomOut = function() { state.zoom = Math.max(0.5, state.zoom - 0.25); render(); };
  state.resetZoom = function() { state.zoom = 1; state.pan = { x: 0, y: 0 }; render(); };
}

function _bindImageViewerEvents(ctx, overlay, state, render) {
  overlay.addEventListener('click', function(e) {
    if (e.target === overlay) { ctx.closeViewer(); return; }
    var act = e.target.closest('[data-act]');
    if (!act) return;
    var action = act.getAttribute('data-act');
    if (action === 'close') ctx.closeViewer();
    if (action === 'prev') state.prev();
    if (action === 'next') state.next();
    if (action === 'zoom-in') state.zoomIn();
    if (action === 'zoom-out') state.zoomOut();
    if (action === 'reset') state.resetZoom();
    if (action === 'download') ctx.downloadUrl(state.images[state.index].url, state.images[state.index].name);
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
}

function _attachAttachmentsViewerImageMethods(ctx) {
  function _openImageViewer(images, index) {
    ctx.closeViewer();
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
    var overlay = _buildImageViewerOverlay();
    document.body.appendChild(overlay);
    state.overlay = overlay;
    function render() { _renderImageViewer(overlay, state); }
    _bindImageViewerNav(state, render);
    _bindImageViewerEvents(ctx, overlay, state, render);
    ctx.setViewerState(state);
    ctx.bindViewerKeydown();
    render();
  }

  ctx.openImageViewer = _openImageViewer;
}
