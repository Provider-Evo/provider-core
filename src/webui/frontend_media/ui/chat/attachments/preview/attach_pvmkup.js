/**
 * Chat attachment preview markup helpers (html/markdown detection, rendering, text pane).
 */
function _attachAttachmentsPreviewMarkupMethods(ctx) {
  _attachAttachmentsPreviewMarkupMethodsSubDetect(ctx);
  _attachAttachmentsPreviewMarkupMethodsSubMarkdown(ctx);
  _attachAttachmentsPreviewMarkupMethodsSubHtml(ctx);
  _attachAttachmentsPreviewMarkupMethodsSubText(ctx);
}

function _attachAttachmentsPreviewMarkupMethodsSubDetect(ctx) {
  function _isHtmlFile(name) {
    var ext = ctx.ext(name);
    return ext === 'html' || ext === 'htm';
  }

  function _isMarkdownFile(name) {
    return /\.(md|mdx)$/i.test(name || '');
  }

  ctx.isHtmlFile = _isHtmlFile;
  ctx.isMarkdownFile = _isMarkdownFile;
}

function _attachAttachmentsPreviewMarkupMethodsSubMarkdown(ctx) {
  function _renderMarkdownPreviewHtml(content) {
    var codeBlocks = [];
    var sentinel = '\x00CB';
    var processed = String(content || '').replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
      var idx = codeBlocks.length;
      codeBlocks.push({ lang: lang, code: code });
      return sentinel + idx + sentinel;
    });
    processed = ctx.esc(processed);
    var lines = processed.split('\n');
    var resultLines = [];
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var h3 = line.match(/^###\s+(.+)$/);
      if (h3) { resultLines.push('<h3>' + h3[1] + '</h3>'); continue; }
      var h2 = line.match(/^##\s+(.+)$/);
      if (h2) { resultLines.push('<h2>' + h2[1] + '</h2>'); continue; }
      var h1 = line.match(/^#\s+(.+)$/);
      if (h1) { resultLines.push('<h1>' + h1[1] + '</h1>'); continue; }
      var ul = line.match(/^[-*]\s+(.+)$/);
      if (ul) { resultLines.push('<div class="files-preview-md-li">• ' + ul[1] + '</div>'); continue; }
      if (!line.trim()) { resultLines.push('<div class="files-preview-md-gap"></div>'); continue; }
      resultLines.push('<p>' + line + '</p>');
    }
    var html = resultLines.join('\n');
    for (var c = 0; c < codeBlocks.length; c++) {
      var block = codeBlocks[c];
      var langLabel = ctx.esc(block.lang || 'text');
      var escapedCode = ctx.esc(block.code);
      html = html.replace(sentinel + c + sentinel,
        '<pre class="files-preview-md-pre"><code class="language-' + langLabel + '">' + escapedCode + '</code></pre>');
    }
    return html;
  }

  ctx.renderMarkdownPreviewHtml = _renderMarkdownPreviewHtml;
}

function _attachAttachmentsPreviewMarkupMethodsSubHtml(ctx) {
  function _mountHtmlPreview(host, htmlContent) {
    host.innerHTML = '';
    var frame = document.createElement('iframe');
    frame.className = 'files-preview-html-frame';
    frame.setAttribute('sandbox', 'allow-scripts');
    frame.setAttribute('referrerpolicy', 'no-referrer');
    frame.setAttribute('title', 'HTML preview');
    var blob = new Blob([htmlContent], { type: 'text/html;charset=utf-8' });
    var blobUrl = URL.createObjectURL(blob);
    host.setAttribute('data-preview-blob', blobUrl);
    frame.src = blobUrl;
    host.appendChild(frame);
  }

  function _clearHtmlPreviewHost(host) {
    if (!host) return;
    var oldUrl = host.getAttribute('data-preview-blob');
    if (oldUrl) {
      URL.revokeObjectURL(oldUrl);
      host.removeAttribute('data-preview-blob');
    }
    host.innerHTML = '';
  }

  ctx.mountHtmlPreview = _mountHtmlPreview;
  ctx.clearHtmlPreviewHost = _clearHtmlPreviewHost;
}

function _attachAttachmentsPreviewMarkupMethodsSubText(ctx) {
  function _renderTextPane(bodyEl, content, name) {
    var wrap = document.createElement('div');
    wrap.className = 'files-preview-text-wrap';
    var gutter = document.createElement('div');
    gutter.className = 'files-preview-gutter';
    var pre = document.createElement('pre');
    pre.className = 'files-preview-code-pane';
    var code = document.createElement('code');
    var lines = String(content || '').split('\n');
    for (var i = 0; i < lines.length; i++) {
      var ln = document.createElement('span');
      ln.className = 'line';
      ln.textContent = String(i + 1);
      gutter.appendChild(ln);
    }
    code.textContent = content || '';
    var ext = ctx.ext(name);
    code.className = 'language-' + (ext || 'text');
    pre.appendChild(code);
    wrap.appendChild(gutter);
    wrap.appendChild(pre);
    bodyEl.innerHTML = '';
    bodyEl.appendChild(wrap);
    if (window.hljs) {
      try { window.hljs.highlightElement(code); } catch (e) { /* ignore */ }
    }
  }

  ctx.renderTextPane = _renderTextPane;
}
