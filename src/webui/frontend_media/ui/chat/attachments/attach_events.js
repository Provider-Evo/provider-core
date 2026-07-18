/**
 * Chat attachment click delegation and global install binding.
 */
function _notifyAttachmentUnavailable(ctx) {
  if (typeof toast === 'function') toast(ctx.t('chat.mediaNotRestored', '附件未从持久化恢复，请重新上传'), 'warn');
}

function _handleAttachmentImageClick(ctx, tile, root, items) {
  var images = ctx.collectImagesFromRoot(root, items);
  if (!images.length) { _notifyAttachmentUnavailable(ctx); return; }
  var imgEl = tile.querySelector('img');
  var curUrl = imgEl && imgEl.src ? imgEl.src : '';
  var imgIndex = images.findIndex(function(it) { return it.url === curUrl; });
  ctx.openImageViewer(images, imgIndex >= 0 ? imgIndex : 0);
}

function _handleAttachmentVideoClick(ctx, items, index, root) {
  var videos = ctx.collectVideosFromRoot(root, items);
  if (!videos.length) { _notifyAttachmentUnavailable(ctx); return; }
  var videoItems = items.filter(function(it) {
    return it.kind === 'video' && !it.stripped && it.url;
  });
  var attAt = items[index];
  var vidIndex = videoItems.indexOf(attAt);
  ctx.openVideoViewer(videos, vidIndex >= 0 ? vidIndex : 0);
}

function _handleAttachmentFileClick(ctx, att) {
  if (!att) { _notifyAttachmentUnavailable(ctx); return; }
  if (att.kind === 'audio') {
    ctx.openFilePreview(att);
    return;
  }
  if (att.kind === 'text' || att.textContent != null || ctx.kindFromNameAndMime(att.name, att.mime) === 'text') {
    ctx.openFilePreview(att);
  } else {
    ctx.openFileDetails(att);
  }
}

/**
 * Chat attachment click delegation and global install binding.
 */
function _attachAttachmentsEventsMethods(ctx) {
  function _handleClick(e) {
    var tile = e.target.closest('[data-chat-att]');
    if (!tile) return;
    var root = tile.closest('.chat-user-attachments');
    if (!root) return;
    var items = ctx.getItemsFromRoot(root);
    var kind = tile.getAttribute('data-chat-att');
    var index = parseInt(tile.getAttribute('data-att-index') || '0', 10);
    var att = items[index];

    if (kind === 'unavailable') { _notifyAttachmentUnavailable(ctx); return; }
    if (kind === 'image') { _handleAttachmentImageClick(ctx, tile, root, items); return; }
    if (kind === 'video') { _handleAttachmentVideoClick(ctx, items, index, root); return; }
    if (kind === 'file') { _handleAttachmentFileClick(ctx, att); }
  }

  function install() {
    if (ctx.isInstalled()) return;
    var container = document.getElementById('chatMessagesContainer');
    if (!container) return;
    container.addEventListener('click', _handleClick);
    ctx.setInstalled(true);
  }

  ctx.handleClick = _handleClick;
  ctx.install = install;
}
