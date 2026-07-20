/**
 * File Manager -- inline preview rendering helpers (HTML iframe sandbox,
 * lightweight markdown renderer).
 *
 * Part of the files.js split. Depends on state.js.
 */

function _isHtmlPreviewFile(name) {
  var ext = (name || '').split('.').pop().toLowerCase();
  return ext === 'html' || ext === 'htm';
}

function _isMarkdownPreviewFile(name) {
  return /\.(md|mdx)$/i.test(name || '');
}

function _escapePreviewHtml(text) {
  if (typeof escapeHtml === 'function') return escapeHtml(text);
  var d = document.createElement('div');
  d.textContent = String(text || '');
  return d.innerHTML;
}

function _renderPreviewInlineMarkdown(text) {
  var inlineCodes = [];
  text = text.replace(/`([^`\n]+)`/g, function(m, code) {
    var idx = inlineCodes.length;
    inlineCodes.push(code);
    return '\x00IC' + idx + '\x00';
  });
  text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  text = text.replace(/\*([^*\n]+)\*/g, '<em>$1</em>');
  text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g,
    '<a href="$2" target="_blank" rel="noopener noreferrer">$1</a>');
  for (var i = 0; i < inlineCodes.length; i++) {
    text = text.replace('\x00IC' + i + '\x00',
      '<code class="files-preview-inline-code">' + inlineCodes[i] + '</code>');
  }
  return text;
}

function _renderMarkdownPreviewHtml(content) {
  var codeBlocks = [];
  var sentinel = '\x00CB';
  var processed = String(content || '').replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
    var idx = codeBlocks.length;
    codeBlocks.push({ lang: lang, code: code });
    return sentinel + idx + sentinel;
  });
  processed = _escapePreviewHtml(processed);
  var lines = processed.split('\n');
  var resultLines = [];
  for (var i = 0; i < lines.length; i++) {
    var line = lines[i];
    var hMatch = line.match(/^(#{1,6})\s+(.+)$/);
    if (hMatch) {
      var level = hMatch[1].length;
      resultLines.push('<h' + level + '>' + _renderPreviewInlineMarkdown(hMatch[2]) + '</h' + level + '>');
      continue;
    }
    var ulMatch = line.match(/^(\s*)[*-]\s+(.+)$/);
    if (ulMatch) {
      resultLines.push('<div class="files-preview-md-li">• ' + _renderPreviewInlineMarkdown(ulMatch[2]) + '</div>');
      continue;
    }
    if (!line.trim()) {
      resultLines.push('<div class="files-preview-md-gap"></div>');
      continue;
    }
    resultLines.push('<p>' + _renderPreviewInlineMarkdown(line) + '</p>');
  }
  processed = resultLines.join('');
  for (var j = 0; j < codeBlocks.length; j++) {
    var cb = codeBlocks[j];
    var escapedCode = _escapePreviewHtml(cb.code);
    var langLabel = cb.lang ? _escapePreviewHtml(cb.lang) : 'code';
    processed = processed.replace(
      sentinel + j + sentinel,
      '<pre class="files-preview-md-pre"><code class="language-' + langLabel + '">' + escapedCode + '</code></pre>'
    );
  }
  return processed;
}

