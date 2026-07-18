/**
 * Chat attachment part parsers: image, file, text parts and files-meta.
 */
function _pushIfNew(items, seen, item) {
  var key = item.kind + ':' + item.name + ':' + (item.url || item.textContent || '').slice(0, 32);
  if (seen[key]) return;
  seen[key] = true;
  items.push(item);
}

function _collectImagePart(ctx, items, seen, part, metaByName) {
  var imgUrl = part.image_url.url || '';
  var name = ctx.guessNameFromUrl(imgUrl, 'image.png');
  _pushIfNew(items, seen, {
    kind: 'image',
    name: name,
    url: imgUrl,
    mime: 'image/*',
    size: (metaByName[name] || {}).size || 0,
    stripped: ctx.isStripped(imgUrl),
  });
}

function _collectFilePart(ctx, items, seen, part, metaByName) {
  var fn = part.file.filename || part.file.name || 'attachment';
  var data = part.file.data || part.file.file_data || '';
  var parsed = ctx.parseDataUrl(data);
  var mime = parsed.mime || ctx.mimeFromName(fn);
  var kind = ctx.kindFromNameAndMime(fn, mime);
  var blobUrl = (!ctx.isStripped(data) && data.indexOf('data:') === 0) ? data : '';
  if (kind === 'text' && data && data.indexOf('data:') === 0) {
    try {
      var blob = ctx.dataUrlToBlob(data);
      if (blob) {
        _pushIfNew(items, seen, {
          kind: 'text',
          name: fn,
          url: data,
          mime: mime,
          size: blob.size || (metaByName[fn] || {}).size || 0,
          stripped: false,
          textContent: null,
        });
        return;
      }
    } catch (e) { /* fall through */ }
  }
  _pushIfNew(items, seen, {
    kind: kind,
    name: fn,
    url: blobUrl || data,
    mime: mime,
    size: (metaByName[fn] || {}).size || 0,
    stripped: ctx.isStripped(data),
  });
}

function _attachCollectPartsMethods(ctx) {
  function _collectFromMessageContent(items, seen, messageContent, metaByName) {
    if (!Array.isArray(messageContent)) return;
    for (var i = 0; i < messageContent.length; i++) {
      var part = messageContent[i];
      if (!part || typeof part !== 'object') continue;
      if (part.type === 'image_url' && part.image_url) {
        _collectImagePart(ctx, items, seen, part, metaByName);
        continue;
      }
      if (part.type === 'file' && part.file) {
        _collectFilePart(ctx, items, seen, part, metaByName);
        continue;
      }
      if (part.type === 'text' && typeof part.text === 'string' && part.text.indexOf('[file:') === 0) {
        var textAtt = ctx.parseFileTextPart(part.text);
        if (textAtt) _pushIfNew(items, seen, textAtt);
      }
    }
  }

  function _collectFromFilesMeta(items, seen, filesMeta) {
    if (!filesMeta || !filesMeta.length) return;
    for (var f = 0; f < filesMeta.length; f++) {
      var fm = filesMeta[f];
      var fkind = ctx.kindFromNameAndMime(fm.name, '');
      if (fkind === 'image') continue;
      var already = items.some(function(it) { return it.name === fm.name; });
      if (!already) {
        _pushIfNew(items, seen, {
          kind: fkind,
          name: fm.name,
          url: '',
          mime: ctx.mimeFromName(fm.name),
          size: fm.size || 0,
          stripped: true,
        });
      }
    }
  }

  ctx.collectFromMessageContent = _collectFromMessageContent;
  ctx.collectFromFilesMeta = _collectFromFilesMeta;
}
