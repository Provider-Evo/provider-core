/**
 * Chat attachment file preview dialog (text/markdown/html/audio/binary) and details dialog.
 */
function _attachAttachmentsPreviewMethods(ctx) {
  _attachAttachmentsPreviewMarkupMethods(ctx);
  _attachAttachmentsPreviewBodyMethods(ctx);
  _attachAttachmentsPreviewDetailsMethods(ctx);

  function _openFilePreview(att) {
    var overlay = ctx.buildFilePreviewOverlay(att);
    document.body.appendChild(overlay);
    var modesEl = overlay.querySelector('#chatAttPreviewModes');
    var bodyEl = overlay.querySelector('.files-preview-body');
    var previewState = { kind: 'text', viewMode: 'source', content: '' };

    function closeOverlay() {
      ctx.clearHtmlPreviewHost(bodyEl.querySelector('.files-preview-html-host'));
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
      if (att.url) ctx.downloadUrl(att.url, att.name);
      else if (att.textContent != null) {
        var blob = new Blob([att.textContent], { type: 'text/plain;charset=utf-8' });
        var u = URL.createObjectURL(blob);
        ctx.downloadUrl(u, att.name);
        setTimeout(function() { URL.revokeObjectURL(u); }, 1000);
      }
    });

    function renderBody() { ctx.renderFilePreviewBody(bodyEl, att, previewState); }
    function bindModes() { ctx.bindFilePreviewModes(modesEl, previewState, renderBody, bindModes); }

    ctx.loadFilePreviewBody(att, bodyEl, modesEl, previewState, bindModes, renderBody);
  }

  ctx.openFilePreview = _openFilePreview;
}
