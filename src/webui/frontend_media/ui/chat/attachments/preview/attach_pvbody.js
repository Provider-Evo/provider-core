/**
 * Chat attachment preview body loading/rendering (overlay body, mode switch, content load).
 */
function _attachAttachmentsPreviewBodyMethods(ctx) {
  var _loadAttachmentContent = _attachAttachmentsPreviewBodySubLoad(ctx);
  var _buildFilePreviewOverlay = _attachAttachmentsPreviewBodySubOverlay(ctx);
  var _bindFilePreviewModes = _attachAttachmentsPreviewBodySubModes(ctx);
  var _renderFilePreviewBody = _attachAttachmentsPreviewBodySubRender(ctx);
  var _loadFilePreviewBody = _attachAttachmentsPreviewBodySubLoadBody(ctx, _loadAttachmentContent);

  ctx.buildFilePreviewOverlay = _buildFilePreviewOverlay;
  ctx.bindFilePreviewModes = _bindFilePreviewModes;
  ctx.renderFilePreviewBody = _renderFilePreviewBody;
  ctx.loadFilePreviewBody = _loadFilePreviewBody;
}

function _attachAttachmentsPreviewBodySubLoad(ctx) {
  async function _loadAttachmentContent(att) {
    if (att.textContent != null) return att.textContent;
    if (!att.url) return '';
    if (att.url.indexOf('data:') === 0) {
      var blob = ctx.dataUrlToBlob(att.url);
      if (!blob) return '';
      if (att.kind === 'text' || ctx.kindFromNameAndMime(att.name, att.mime) === 'text') {
        return await blob.text();
      }
      return '';
    }
    var res = await fetch(att.url);
    return await res.text();
  }

  return _loadAttachmentContent;
}

function _attachAttachmentsPreviewBodySubOverlay(ctx) {
  function _buildFilePreviewOverlay(att) {
    var overlay = document.createElement('div');
    overlay.className = 'files-preview-overlay chat-att-preview-overlay';
    overlay.innerHTML =
      '<div class="files-preview-dialog">'
      + '<div class="files-preview-header">'
      + '<div class="files-preview-title">' + ctx.esc(att.name) + '</div>'
      + '<div class="files-preview-modes" id="chatAttPreviewModes" hidden></div>'
      + '<div class="files-preview-actions">'
      + '<button type="button" class="files-preview-btn" id="chatAttPreviewDownload">' + ctx.t('files.download', '下载') + '</button>'
      + '<button type="button" class="files-preview-btn" id="chatAttPreviewClose">' + ctx.t('common.close', '关闭') + '</button>'
      + '</div></div>'
      + '<div class="files-preview-body"><div class="files-loading">' + ctx.t('files.loading', '加载中...') + '</div></div>'
      + '</div>';
    return overlay;
  }

  return _buildFilePreviewOverlay;
}

function _attachAttachmentsPreviewBodySubModes(ctx) {
  function _bindFilePreviewModes(modesEl, previewState, renderBody, bindModes) {
    if (!modesEl) return;
    modesEl.hidden = false;
    if (previewState.kind === 'html') {
      modesEl.innerHTML =
        '<button type="button" class="files-preview-mode' + (previewState.viewMode === 'source' ? ' is-active' : '') + '" data-mode="source">' + ctx.t('files.viewSource', '源码') + '</button>'
        + '<button type="button" class="files-preview-mode' + (previewState.viewMode === 'rendered' ? ' is-active' : '') + '" data-mode="rendered">' + ctx.t('files.viewPreview', '预览') + '</button>';
    } else if (previewState.kind === 'markdown') {
      modesEl.innerHTML =
        '<button type="button" class="files-preview-mode' + (previewState.viewMode === 'source' ? ' is-active' : '') + '" data-mode="source">' + ctx.t('files.viewSource', '源码') + '</button>'
        + '<button type="button" class="files-preview-mode' + (previewState.viewMode === 'rendered' ? ' is-active' : '') + '" data-mode="rendered">' + ctx.t('files.viewRendered', '渲染') + '</button>';
    } else {
      modesEl.hidden = true;
      modesEl.innerHTML = '';
    }
    modesEl.querySelectorAll('.files-preview-mode').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var mode = btn.getAttribute('data-mode');
        if (!mode || previewState.viewMode === mode) return;
        previewState.viewMode = mode;
        renderBody();
        bindModes();
      });
    });
  }

  return _bindFilePreviewModes;
}

function _attachAttachmentsPreviewBodySubRender(ctx) {
  function _renderFilePreviewBody(bodyEl, att, previewState) {
    ctx.clearHtmlPreviewHost(bodyEl.querySelector('.files-preview-html-host'));
    bodyEl.className = 'files-preview-body';
    var content = previewState.content;

    if (previewState.kind === 'html' && previewState.viewMode === 'rendered') {
      bodyEl.className = 'files-preview-body files-preview-body-html';
      var htmlHost = document.createElement('div');
      htmlHost.className = 'files-preview-html-host';
      bodyEl.appendChild(htmlHost);
      ctx.mountHtmlPreview(htmlHost, content);
      return;
    }
    if (previewState.kind === 'markdown' && previewState.viewMode === 'rendered') {
      bodyEl.className = 'files-preview-body files-preview-body-markdown';
      bodyEl.innerHTML = '<div class="files-preview-markdown">' + ctx.renderMarkdownPreviewHtml(content) + '</div>';
      return;
    }
    if (previewState.kind === 'audio' && att.url) {
      bodyEl.innerHTML = '<div class="chat-att-audio-wrap"><audio controls src="' + ctx.esc(att.url) + '"></audio></div>';
      return;
    }
    ctx.renderTextPane(bodyEl, content, att.name);
  }

  return _renderFilePreviewBody;
}

function _attachAttachmentsPreviewBodySubLoadBody(ctx, _loadAttachmentContent) {
  async function _loadFilePreviewBody(att, bodyEl, modesEl, previewState, bindModes, renderBody) {
    try {
      if (att.kind === 'image' && att.url) {
        bodyEl.innerHTML = '<div class="files-preview-image"><img src="' + ctx.esc(att.url) + '" alt="' + ctx.esc(att.name) + '"></div>';
        return;
      }
      if (att.kind === 'video' && att.url) {
        bodyEl.innerHTML = '<div class="chat-att-video-wrap"><video controls playsinline src="' + ctx.esc(att.url) + '"></video></div>';
        return;
      }
      if (att.kind === 'file' && att.url && att.url.indexOf('data:') === 0) {
        bodyEl.innerHTML =
          '<div class="files-preview-binary">'
          + '<div>' + ctx.esc(ctx.t('files.binaryFile', '二进制文件', { size: ctx.formatSize(att.size) })) + '</div>'
          + '<button type="button" class="files-preview-btn" id="chatAttBinaryDl">' + ctx.t('files.download', '下载') + '</button>'
          + '</div>';
        bodyEl.querySelector('#chatAttBinaryDl').addEventListener('click', function() {
          ctx.downloadUrl(att.url, att.name);
        });
        return;
      }

      var content = await _loadAttachmentContent(att);
      previewState.content = content || '';
      if (ctx.isHtmlFile(att.name)) {
        previewState.kind = 'html';
        previewState.viewMode = 'source';
      } else if (ctx.isMarkdownFile(att.name)) {
        previewState.kind = 'markdown';
        previewState.viewMode = 'source';
      } else if (att.kind === 'audio') {
        previewState.kind = 'audio';
      } else {
        previewState.kind = 'text';
      }
      bindModes();
      renderBody();
    } catch (e) {
      bodyEl.innerHTML = '<div class="files-preview-binary"><div>' + ctx.esc(ctx.t('files.loadFileFailed', '加载失败', { error: e.message || String(e) })) + '</div></div>';
    }
  }

  return _loadFilePreviewBody;
}
