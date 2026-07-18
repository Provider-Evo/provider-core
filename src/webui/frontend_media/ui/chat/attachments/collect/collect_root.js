/**
 * Chat attachment item retrieval from a mounted turn's stored items.
 */
function _attachCollectRootMethods(ctx) {
  function _getItemsFromRoot(root) {
    var turn = root.closest('.chat-user-turn');
    if (turn && ctx.turnStore.has(turn)) return ctx.turnStore.get(turn);
    return [];
  }

  function _collectImagesFromRoot(root, items) {
    items = items || ctx.getItemsFromRoot(root);
    var images = items.filter(function(it) {
      return it.kind === 'image' && !it.stripped && it.url;
    }).map(function(it) { return { url: it.url, name: it.name }; });
    if (images.length) return images;
    root.querySelectorAll('.chat-att-image').forEach(function(tile) {
      var img = tile.querySelector('img');
      var url = img && img.src ? img.src : '';
      if (url && !ctx.isStripped(url)) {
        images.push({ url: url, name: tile.getAttribute('data-name') || 'image' });
      }
    });
    return images;
  }

  function _collectVideosFromRoot(root, items) {
    items = items || ctx.getItemsFromRoot(root);
    return items.filter(function(it) {
      return it.kind === 'video' && !it.stripped && it.url;
    }).map(function(it) { return { url: it.url, name: it.name, mime: it.mime }; });
  }

  ctx.getItemsFromRoot = _getItemsFromRoot;
  ctx.collectImagesFromRoot = _collectImagesFromRoot;
  ctx.collectVideosFromRoot = _collectVideosFromRoot;
}
