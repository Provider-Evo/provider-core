/**
 * Chat attachment viewer shared helpers (download, close, keyboard nav) used by
 * both the image and video overlay viewers.
 */
function _attachAttachmentsViewerSharedMethods(ctx) {
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
    var state = ctx.getViewerState();
    if (state && state.overlay) {
      state.overlay.remove();
      ctx.setViewerState(null);
    }
    document.removeEventListener('keydown', _onViewerKey);
  }

  function _onViewerKey(e) {
    var state = ctx.getViewerState();
    if (!state) return;
    if (e.key === 'Escape') _closeViewer();
    if (state.mode === 'image') {
      if (e.key === 'ArrowRight') state.next();
      if (e.key === 'ArrowLeft') state.prev();
      if (e.key === '+' || e.key === '=') state.zoomIn();
      if (e.key === '-') state.zoomOut();
      if (e.key === '0') state.resetZoom();
    } else if (state.mode === 'video') {
      if (e.key === 'ArrowRight') state.next();
      if (e.key === 'ArrowLeft') state.prev();
    }
  }

  function _bindViewerKeydown() {
    document.addEventListener('keydown', _onViewerKey);
  }

  ctx.downloadUrl = _downloadUrl;
  ctx.closeViewer = _closeViewer;
  ctx.bindViewerKeydown = _bindViewerKeydown;
}
