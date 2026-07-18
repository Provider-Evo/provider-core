/**
 * TabBar hover preview tooltip methods (compressed sidebar mode).
 * Depends on tabbar_core.js.
 */
'use strict';

function _attachPreviewMethods(instance) {
  _attachPreviewSubShowMethods(instance);
  _attachPreviewSubPositionMethods(instance);
  _attachPreviewSubLifecycleMethods(instance);
}

/**
 * Attach the preview element creation/show helpers.
 * Split out of _attachPreviewMethods to keep it under the line cap.
 */
function _attachPreviewSubShowMethods(instance) {
  instance._ensurePreview = function () {
    if (this._previewEl) return this._previewEl;
    var el = document.createElement('div');
    el.className = 'tabbar-preview';
    el.innerHTML = '<div class="tabbar-preview-thumb"></div><div class="tabbar-preview-title"></div><div class="tabbar-preview-meta"></div>';
    document.body.appendChild(el);
    this._previewEl = el;
    return el;
  };

  instance._showPreview = function (tab, mouseX, mouseY) {
    if (!tab) return;
    var el = this._ensurePreview();
    var thumbEl = el.querySelector('.tabbar-preview-thumb');
    var titleEl = el.querySelector('.tabbar-preview-title');
    var metaEl = el.querySelector('.tabbar-preview-meta');
    // Thumbnail is read synchronously from the cache -- no capture work
    // happens here, so display stays instant on hover.
    var thumb = this._thumbnails[tab.id];
    if (thumbEl) {
      if (thumb) {
        thumbEl.innerHTML = '<img src="' + thumb + '" alt="">';
        thumbEl.style.display = '';
      } else {
        thumbEl.innerHTML = '';
        thumbEl.style.display = 'none';
      }
    }
    if (titleEl) titleEl.textContent = tab.title || tab.id;
    if (metaEl) metaEl.textContent = tab.status || tab.type || '';
    this._positionPreview(el, mouseX, mouseY);
    el.classList.add('visible');
  };
}

/**
 * Attach the preview positioning/movement helpers.
 * Split out of _attachPreviewMethods to keep it under the line cap.
 */
function _attachPreviewSubPositionMethods(instance) {
  instance._positionPreview = function (el, mouseX, mouseY) {
    var left = mouseX + 12;
    var top = mouseY - 8;
    el.style.left = left + 'px';
    el.style.top = top + 'px';
    // Clamp to viewport after render
    var self = this;
    if (self._previewRaf) cancelAnimationFrame(self._previewRaf);
    self._previewRaf = requestAnimationFrame(function () {
      self._previewRaf = null;
      var rect = el.getBoundingClientRect();
      if (rect.right > window.innerWidth) {
        el.style.left = (mouseX - rect.width - 8) + 'px';
      }
      if (rect.bottom > window.innerHeight) {
        el.style.top = (window.innerHeight - rect.height - 8) + 'px';
      }
      if (rect.top < 0) {
        el.style.top = '8px';
      }
    });
  };

  instance._movePreview = function (mouseX, mouseY) {
    if (!this._previewEl) return;
    this._positionPreview(this._previewEl, mouseX, mouseY);
  };
}

/**
 * Attach the thumbnail storage, hide, and dispose lifecycle helpers.
 * Split out of _attachPreviewMethods to keep it under the line cap.
 */
function _attachPreviewSubLifecycleMethods(instance) {
  /**
   * Store (or clear) a cached thumbnail image for a tab, used by the
   * hover preview panel in collapsed sidebar mode. Callers (terminal.js,
   * files.js) are responsible for generating the image at a low frequency
   * (debounce/interval) -- this method only stores it, it never captures
   * anything itself, so reads at hover time stay instant.
   * @param {string} id - Tab ID
   * @param {string|null} dataUrl - Image data URL (e.g. from canvas.toDataURL()), or falsy to clear
   */
  instance.setThumbnail = function (id, dataUrl) {
    if (dataUrl) {
      this._thumbnails[id] = dataUrl;
    } else {
      delete this._thumbnails[id];
    }
  };

  instance._hidePreview = function () {
    if (!this._previewEl) return;
    this._previewEl.classList.remove('visible');
  };

  instance._disposePreview = function () {
    if (this._previewEl && this._previewEl.parentNode) {
      this._previewEl.parentNode.removeChild(this._previewEl);
    }
    this._previewEl = null;
  };
}
