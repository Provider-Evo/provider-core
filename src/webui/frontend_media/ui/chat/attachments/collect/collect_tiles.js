/**
 * Chat attachment tile HTML builders.
 */
function _buildUnavailableTile(ctx, a, idx) {
  return '<div class="chat-att-tile chat-att-unavailable" data-chat-att="unavailable" data-att-index="' + idx + '">'
    + '<span class="chat-att-unavailable-icon">' + ctx.fileIcon(a.name) + '</span>'
    + '<span class="chat-att-unavailable-text">' + ctx.esc(a.name) + '</span>'
    + '<span class="chat-att-unavailable-hint">' + ctx.esc(ctx.t('chat.mediaNotRestored', '附件未从持久化恢复')) + '</span>'
    + '</div>';
}

function _buildImageTile(ctx, a, idx) {
  return '<button type="button" class="chat-att-tile chat-att-image" data-chat-att="image" data-att-index="' + idx + '"'
    + ' data-name="' + ctx.esc(a.name) + '">'
    + '<img src="' + ctx.esc(a.url) + '" alt="' + ctx.esc(a.name) + '" loading="lazy" draggable="false">'
    + '</button>';
}

function _buildVideoTile(ctx, a, idx) {
  return '<button type="button" class="chat-att-tile chat-att-video" data-chat-att="video" data-att-index="' + idx + '"'
    + ' data-name="' + ctx.esc(a.name) + '">'
    + '<span class="chat-att-video-play" aria-hidden="true">'
    + '<svg width="28" height="28" viewBox="0 0 24 24" fill="currentColor"><path d="M8 5v14l11-7z"/></svg>'
    + '</span>'
    + '<span class="chat-att-video-name">' + ctx.esc(a.name) + '</span>'
    + '<span class="chat-att-video-size">' + ctx.esc(ctx.formatSize(a.size)) + '</span>'
    + '</button>';
}

function _buildFileTile(ctx, a, idx) {
  return '<button type="button" class="chat-att-tile chat-file-card chat-att-file" data-chat-att="file" data-att-index="' + idx + '"'
    + ' data-name="' + ctx.esc(a.name) + '"'
    + (a.textContent != null ? ' data-has-text="1"' : '')
    + '>'
    + '<span class="chat-file-icon">' + ctx.fileIcon(a.name) + '</span>'
    + '<span class="chat-file-info">'
    + '<span class="chat-file-name">' + ctx.esc(a.name) + '</span>'
    + '<span class="chat-file-size">' + ctx.esc(ctx.formatSize(a.size)) + '</span>'
    + '</span>'
    + '<span class="chat-att-open-icon" aria-hidden="true">'
    + '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M10 14 21 3M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></svg>'
    + '</span>'
    + '</button>';
}

function _attachCollectTilesMethods(ctx) {
  function buildTilesHtml(items) {
    if (!items.length) return '';
    var html = '<div class="chat-att-grid">';
    for (var i = 0; i < items.length; i++) {
      var a = items[i];
      var idx = String(i);
      if (a.stripped) { html += _buildUnavailableTile(ctx, a, idx); continue; }
      if (a.kind === 'image' && a.url) { html += _buildImageTile(ctx, a, idx); continue; }
      if (a.kind === 'video' && a.url) { html += _buildVideoTile(ctx, a, idx); continue; }
      html += _buildFileTile(ctx, a, idx);
    }
    html += '</div>';
    return html;
  }

  ctx.buildTilesHtml = buildTilesHtml;
}
