/**
 * Terminal link detection -- strips ConPTY DA-response garbage from output
 * and provides clickable URL/path links inside the xterm buffer.
 *
 * Exposes via _attachLinksMethods(ctx):
 * - ctx.stripDecResponses(data)
 * - ctx.installTerminalLinkProvider(xterm)
 */
function _attachLinksMethods(ctx) {
  _attachLinksSubStrip(ctx);
  _attachLinksSubProvider(ctx);
}

function _attachLinksSubStrip(ctx) {
  // Strip complete Device Attribute (DA) responses leaked by ConPTY.
  var _DA_RESPONSE = /\x1b\[\?[0-9;]*c/g;

  /**
   * Strip Device Attribute (DA) responses that leak through ConPTY as
   * visible garbage.  xterm.js handles these internally; they must never
   * reach xterm.write() as visible text.
   *
   * DA responses end with 'c' (e.g. ^[[?6c, ^[[?1;2c, ^[[?62;1;2;6c).
   * This function does NOT strip DEC private mode SET/RESET sequences
   * (e.g. ^[[?25h, ^[[?25l, ^[[?1049h) because those control cursor
   * visibility, alternate screen buffer, mouse tracking, etc. — xterm.js
   * must receive them to function correctly with TUI applications.
   * Applied to ALL output — live stream, offline replay, and status messages.
   * Handles cross-message splitting by tracking pending escape sequences.
   */
  function _stripDecResponses(data) {
    if (typeof data !== 'string') return data;
    return data.replace(_DA_RESPONSE, '');
  }

  ctx.stripDecResponses = _stripDecResponses;
}

var _TERMINAL_URL_RE = /https?:\/\/[^\s"'`<>]+/g;
var _TERMINAL_PATH_RE = /(?:~\/|\.{1,2}\/|\/|[A-Za-z]:[\\/]|\\\\)[^\s"'`<>]+/g;

function _trimTerminalLinkText(value) {
  return String(value || '').replace(/[.,;!?]+$/, '');
}

function _collectUrlLinks(text, pushLink) {
  var urlMatch;
  _TERMINAL_URL_RE.lastIndex = 0;
  while ((urlMatch = _TERMINAL_URL_RE.exec(text)) !== null) {
    (function (url, start) {
      pushLink(url, start, function (event) {
        event.preventDefault();
        window.open(url, '_blank', 'noopener,noreferrer');
      });
    })(urlMatch[0], urlMatch.index);
  }
}

function _collectPathLinks(text, pushLink) {
  var pathMatch;
  _TERMINAL_PATH_RE.lastIndex = 0;
  while ((pathMatch = _TERMINAL_PATH_RE.exec(text)) !== null) {
    (function (path, start) {
      pushLink(path, start, function (event) {
        event.preventDefault();
        if (typeof FileManager !== 'undefined' && typeof FileManager.openPath === 'function') {
          FileManager.openPath(path);
        } else if (typeof toast === 'function') {
          toast(path, 'info');
        }
      });
    })(pathMatch[0], pathMatch.index);
  }
}

/**
 * Build the push-link closure that dedupes overlapping matches and appends
 * to the links array. Split out of _collectLineLinks to keep it under the
 * line cap.
 */
function _makeTerminalPushLink(links, used, bufferLineNumber) {
  function overlaps(start, end) {
    for (var i = 0; i < used.length; i++) {
      if (start < used[i].end && end > used[i].start) return true;
    }
    return false;
  }

  return function pushLink(matchText, start, activate) {
    var trimmed = _trimTerminalLinkText(matchText);
    if (!trimmed) return;
    var end = start + trimmed.length;
    if (overlaps(start, end)) return;
    used.push({ start: start, end: end });
    links.push({
      text: trimmed,
      range: {
        start: { x: start, y: bufferLineNumber },
        end: { x: end, y: bufferLineNumber },
      },
      activate: activate,
    });
  };
}

function _collectLineLinks(text, bufferLineNumber) {
  var links = [];
  var used = [];
  var pushLink = _makeTerminalPushLink(links, used, bufferLineNumber);

  _collectUrlLinks(text, pushLink);
  _collectPathLinks(text, pushLink);

  return links;
}

function _makeTerminalLineLinkCollector() {
  return _collectLineLinks;
}

function _attachLinksSubProvider(ctx) {
  var _collectLineLinks = _makeTerminalLineLinkCollector();

  function _installTerminalLinkProvider(xterm) {
    if (!xterm || typeof xterm.registerLinkProvider !== 'function') return;

    xterm.registerLinkProvider({
      provideLinks: function (bufferLineNumber, callback) {
        var line = xterm.buffer.active.getLine(bufferLineNumber);
        if (!line) {
          callback(undefined);
          return;
        }
        var text = line.translateToString(true);
        var links = _collectLineLinks(text, bufferLineNumber);
        callback(links.length ? links : undefined);
      },
    });
  }

  ctx.installTerminalLinkProvider = _installTerminalLinkProvider;
}
