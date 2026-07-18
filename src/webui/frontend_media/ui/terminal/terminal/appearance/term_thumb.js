// ========================= Terminal: Thumbnail Capture (Canvas Addon) =========================
// Split from terminal.js. Attaches thumbnail-capture related methods onto the
// shared ctx object used across all terminal.js submodules.

function _attachThumbnailMethodsSubCanvas(ctx) {
  /**
   * Try to load the CanvasAddon onto an xterm instance so its content is
   * rendered onto a real <canvas> element that can be captured for
   * thumbnails. Falls back silently (xterm keeps using its default DOM
   * renderer) if the addon is unavailable or fails to activate -- this
   * must never block terminal initialization.
   */
  function _loadCanvasAddon(xterm) {
    if (typeof CanvasAddon === 'undefined' || !CanvasAddon || typeof CanvasAddon.CanvasAddon !== 'function') {
      return;
    }
    try {
      xterm.loadAddon(new CanvasAddon.CanvasAddon());
    } catch (e) {
      // Canvas addon unsupported in this environment (e.g. no 2D canvas
      // context available) -- degrade gracefully, no thumbnails for this tab.
    }
  }

  /**
   * Find the <canvas> element that the CanvasAddon renders terminal
   * content onto, inside the given xterm container. The addon creates
   * several stacked layers (xterm-text-layer, xterm-selection-layer,
   * xterm-link-layer, xterm-cursor-layer) inside a `.xterm-screen`
   * wrapper; the text layer holds the actual glyph pixels we want.
   */
  function _findRenderCanvas(container) {
    if (!container) return null;
    var textLayer = container.querySelector('canvas.xterm-text-layer');
    if (textLayer) return textLayer;
    // Fallback: any canvas inside .xterm-screen (covers renderer variations)
    var screen = container.querySelector('.xterm-screen');
    if (screen) {
      var anyCanvas = screen.querySelector('canvas');
      if (anyCanvas) return anyCanvas;
    }
    return null;
  }

  ctx.loadCanvasAddon = _loadCanvasAddon;
  ctx._findRenderCanvas = _findRenderCanvas;
}

function _attachThumbnailMethodsSubCapture(ctx) {
  var _THUMBNAIL_MIN_INTERVAL_MS = 800;
  var _THUMBNAIL_WIDTH = 160;

  function _drawThumbnail(sourceCanvas) {
    var scale = _THUMBNAIL_WIDTH / sourceCanvas.width;
    var thumbW = _THUMBNAIL_WIDTH;
    var thumbH = Math.max(1, Math.round(sourceCanvas.height * scale));

    var tmpCanvas = document.createElement('canvas');
    tmpCanvas.width = thumbW;
    tmpCanvas.height = thumbH;
    var drawCtx = tmpCanvas.getContext('2d');
    if (!drawCtx) return null;
    drawCtx.drawImage(sourceCanvas, 0, 0, thumbW, thumbH);
    return tmpCanvas.toDataURL('image/jpeg', 0.6);
  }

  /**
   * Capture a downscaled thumbnail of a tab's terminal content and push
   * it into the TabBar's thumbnail cache. Throttled per-tab so rapid
   * hover movement across the compressed sidebar doesn't trigger a
   * capture burst; the first capture for a tab (no cache yet) always
   * runs immediately.
   */
  function _captureThumbnail(tab) {
    if (!tab || !tab._container || !ctx.bar) return;

    var now = Date.now();
    var last = tab._lastThumbnailAt || 0;
    if (last !== 0 && (now - last) < _THUMBNAIL_MIN_INTERVAL_MS) return;

    var sourceCanvas = ctx._findRenderCanvas(tab._container);
    if (!sourceCanvas || !sourceCanvas.width || !sourceCanvas.height) return;

    try {
      var dataUrl = _drawThumbnail(sourceCanvas);
      if (!dataUrl) return;
      tab._lastThumbnailAt = now;
      ctx.bar.setThumbnail(tab.id, dataUrl);
    } catch (e) {
      // Canvas may be tainted or unavailable in some environments;
      // skip this capture rather than breaking the hover interaction.
    }
  }

  ctx.captureThumbnail = _captureThumbnail;
}

function _attachThumbnailMethods(ctx) {
  _attachThumbnailMethodsSubCanvas(ctx);
  _attachThumbnailMethodsSubCapture(ctx);
}
