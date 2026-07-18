/**
 * Chat attachment collection from message content + tile HTML rendering + DOM mount.
 */
function _attachAttachmentsCollectMethods(ctx) {
  _attachCollectPartsMethods(ctx);
  _attachCollectTilesMethods(ctx);
  _attachCollectRootMethods(ctx);

  function collectAttachments(messageContent, filesMeta) {
    var items = [];
    var seen = {};
    var metaByName = {};
    if (filesMeta && filesMeta.length) {
      for (var m = 0; m < filesMeta.length; m++) {
        metaByName[filesMeta[m].name] = filesMeta[m];
      }
    }
    ctx.collectFromMessageContent(items, seen, messageContent, metaByName);
    ctx.collectFromFilesMeta(items, seen, filesMeta);
    return items;
  }

  function buildHtml(messageContent, filesMeta) {
    return ctx.buildTilesHtml(collectAttachments(messageContent, filesMeta));
  }

  function mountInto(attEl, turnEl, messageContent, filesMeta) {
    if (!attEl || !turnEl) return;
    var items = collectAttachments(messageContent, filesMeta);
    if (!items.length) {
      attEl.innerHTML = '';
      ctx.turnStore.delete(turnEl);
      return;
    }
    ctx.turnStore.set(turnEl, items);
    attEl.innerHTML = ctx.buildTilesHtml(items);
  }

  ctx.collectAttachments = collectAttachments;
  ctx.buildHtml = buildHtml;
  ctx.mountInto = mountInto;
}
