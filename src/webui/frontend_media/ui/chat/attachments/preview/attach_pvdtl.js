/**
 * Chat attachment file details dialog.
 */
function _buildFileDetailsHtml(ctx, att) {
  return '<div class="chat-att-details-dialog" role="dialog" aria-modal="true">'
    + '<div class="chat-att-details-header">'
    + '<div class="chat-att-details-title">' + ctx.t('chat.fileDetailsTitle', '文件详情') + '</div>'
    + '<button type="button" class="chat-att-details-close" data-act="close">&times;</button>'
    + '</div>'
    + '<div class="chat-att-details-body">'
    + '<div class="chat-att-details-card">'
    + '<span class="chat-file-icon">' + ctx.fileIcon(att.name) + '</span>'
    + '<div class="chat-att-details-meta">'
    + '<div class="chat-att-details-name">' + ctx.esc(att.name) + '</div>'
    + '<div class="chat-att-details-mime">' + ctx.esc(att.mime || ctx.mimeFromName(att.name)) + '</div>'
    + '</div></div>'
    + '<div class="chat-att-details-grid">'
    + '<div class="chat-att-details-stat"><span>' + ctx.t('chat.fileDetailsSize', '大小') + '</span><strong>' + ctx.esc(ctx.formatSize(att.size)) + '</strong></div>'
    + '<div class="chat-att-details-stat"><span>' + ctx.t('chat.fileDetailsType', '类型') + '</span><strong>' + ctx.esc(att.kind) + '</strong></div>'
    + '</div></div>'
    + '<div class="chat-att-details-footer">'
    + '<button type="button" class="btn btn-secondary" data-act="cancel">' + ctx.t('common.cancel', '取消') + '</button>'
    + '<button type="button" class="btn btn-primary" data-act="preview">' + ctx.t('files.preview', '预览') + '</button>'
    + '<button type="button" class="btn btn-primary" data-act="download">' + ctx.t('files.download', '下载') + '</button>'
    + '</div></div>';
}

function _wireFileDetailsEvents(ctx, overlay, att) {
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
    if (action === 'preview') { close(); ctx.openFilePreview(att); }
    if (action === 'download' && att.url) { ctx.downloadUrl(att.url, att.name); close(); }
  });
}

function _attachAttachmentsPreviewDetailsMethods(ctx) {
  function _openFileDetails(att) {
    var overlay = document.createElement('div');
    overlay.className = 'chat-att-details-overlay';
    overlay.innerHTML = _buildFileDetailsHtml(ctx, att);

    document.body.appendChild(overlay);

    _wireFileDetailsEvents(ctx, overlay, att);
  }

  ctx.openFileDetails = _openFileDetails;
}
