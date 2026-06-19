/**
 * Terminal Tab -- Custom-rendered terminal with local and SSH support.
 * No external dependencies (no xterm.js, no FitAddon).
 *
 * Features:
 * - Custom ANSI escape sequence parser and renderer
 * - Horizontal tab bar with add/close/rename
 * - Local terminal via WebSocket to backend
 * - SSH remote terminal via paramiko on backend
 * - Resize handling
 * - Right-click context menu
 * - SSH dialog with quick-parse (user@host:port, user:pass@host:port)
 * - Saved SSH connections via persist API
 */

// ========================= TerminalRenderer =========================
// Replaces xterm.js with a lightweight custom ANSI terminal renderer.
// Renders into a <pre> element, captures input via a hidden <textarea>.

function TerminalRenderer(container, cols, rows) {
  var _lines = [[]];           // scrollback buffer: arrays of {char, fg, bg, bold}
  var _cursorRow = 0;
  var _cursorCol = 0;
  var _attrs = { fg: 37, bg: -1, bold: false };
  var _maxScrollback = 5000;
  var _cols = cols || 80;
  var _rows = rows || 24;
  var _onDataCb = null;
  var _savedCursor = { row: 0, col: 0 };
  var _csiMode = false;
  var _csiParams = '';
  var _escMode = false;
  var _charWidth = 8.4;
  var _charHeight = 16;
  var _disposed = false;
  var _composing = false;
  var _renderPending = false;

  // Path detection regex for clickable file/directory paths in terminal output
  // Matches: absolute Windows paths (C:\foo\bar), absolute Unix paths (/home/user/...),
  // and common relative paths with extensions (src/foo.py, ./bar.js, ../lib/utils.ts)
  var _PATH_REGEX = /(?:[A-Z]:\\(?:[^\s<>|"*?>]+\\)*[^\s<>|"*?>]+)|(?:\/(?:[\w.-]+\/)*[\w.-]+(?:\.[\w]+)?)|(?:(?:\.{0,2}\/[\w.-]+)+\.[\w]+)/gi;

  function _escapeAttr(text) {
    return String(text).replace(/&/g, '&amp;').replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  // DOM: wrapper div (focusable) > pre.terminal-output
  var _wrapper = document.createElement('div');
  _wrapper.style.cssText =
    'width:100%;height:100%;position:relative;overflow:hidden;outline:none;';
  _wrapper.tabIndex = 0;

  var _pre = document.createElement('pre');
  _pre.className = 'terminal-output';
  _pre.style.cssText =
    'margin:0;padding:4px 8px;overflow:hidden;' +
    'font-family:"Cascadia Code","Fira Code","JetBrains Mono",Menlo,Monaco,monospace;' +
    'font-size:14px;line-height:16px;background:#1e1e1e;color:#d4d4d4;' +
    'white-space:pre;user-select:text;-webkit-user-select:text;' +
    'width:100%;height:100%;box-sizing:border-box;pointer-events:none;';

  _wrapper.appendChild(_pre);
  container.appendChild(_wrapper);

  // --- Document-level keyboard capture ---
  // Captures ALL keydown events when this terminal is the active tab,
  // regardless of which element has focus. Skips events targeting other
  // input elements (text inputs, selects, etc.)

  function _handleKeydown(e) {
    // Only capture when this terminal's tab panel is visible
    var panel = _wrapper.closest('.tab-panel');
    if (!panel || panel.classList.contains('hidden')) return;

    // Don't steal input from other form elements on the page
    var active = document.activeElement;
    if (active && active !== _wrapper && active !== document.body) {
      var tag = active.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    }

    // Ctrl+key (A-Z)
    if (e.ctrlKey && !e.altKey && !e.metaKey && e.key.length === 1) {
      var c = e.key.toLowerCase();
      var code = c.charCodeAt(0);
      if (code >= 97 && code <= 122 && c !== 'c' && c !== 'v') {
        e.preventDefault();
        e.stopPropagation();
        if (_onDataCb) _onDataCb(String.fromCharCode(code - 96));
        return;
      }
    }
    // Alt+key
    if (e.altKey && !e.ctrlKey && !e.metaKey && e.key.length === 1) {
      e.preventDefault();
      e.stopPropagation();
      if (_onDataCb) _onDataCb('\x1b' + e.key);
      return;
    }

    switch (e.key) {
      case 'Enter':
        e.preventDefault(); e.stopPropagation();
        if (_onDataCb) _onDataCb('\r');
        return;
      case 'Backspace':
        e.preventDefault(); e.stopPropagation();
        if (e.ctrlKey) {
          if (_onDataCb) _onDataCb('\x17');
        } else {
          if (_onDataCb) _onDataCb('\x7f');
        }
        return;
      case 'Tab':
        e.preventDefault(); e.stopPropagation();
        if (_onDataCb) _onDataCb('\t');
        return;
      case 'Escape':
        e.preventDefault(); e.stopPropagation();
        if (_onDataCb) _onDataCb('\x1b');
        return;
      case 'ArrowUp':    e.preventDefault(); e.stopPropagation(); if (_onDataCb) _onDataCb('\x1b[A'); return;
      case 'ArrowDown':  e.preventDefault(); e.stopPropagation(); if (_onDataCb) _onDataCb('\x1b[B'); return;
      case 'ArrowRight': e.preventDefault(); e.stopPropagation(); if (_onDataCb) _onDataCb('\x1b[C'); return;
      case 'ArrowLeft':  e.preventDefault(); e.stopPropagation(); if (_onDataCb) _onDataCb('\x1b[D'); return;
      case 'Home':    e.preventDefault(); e.stopPropagation(); if (_onDataCb) _onDataCb('\x1b[H'); return;
      case 'End':     e.preventDefault(); e.stopPropagation(); if (_onDataCb) _onDataCb('\x1b[F'); return;
      case 'Insert':  e.preventDefault(); e.stopPropagation(); if (_onDataCb) _onDataCb('\x1b[2~'); return;
      case 'Delete':  e.preventDefault(); e.stopPropagation(); if (_onDataCb) _onDataCb('\x1b[3~'); return;
      case 'PageUp':  e.preventDefault(); e.stopPropagation(); if (_onDataCb) _onDataCb('\x1b[5~'); return;
      case 'PageDown': e.preventDefault(); e.stopPropagation(); if (_onDataCb) _onDataCb('\x1b[6~'); return;
    }

    // Regular printable character
    if (!e.ctrlKey && !e.altKey && !e.metaKey && e.key.length === 1) {
      e.preventDefault();
      e.stopPropagation();
      if (_onDataCb) _onDataCb(e.key);
      return;
    }
  }

  document.addEventListener('keydown', _handleKeydown, true);

  // Focus management — click anywhere in terminal area to focus wrapper
  _wrapper.addEventListener('mousedown', function (e) {
    _wrapper.focus();
  });

  // Click handler for detected file paths — navigate to file manager
  _wrapper.addEventListener('click', function (e) {
    var pathEl = e.target.closest('.term-path');
    if (!pathEl) return;
    e.preventDefault();
    e.stopPropagation();
    var rawPath = pathEl.getAttribute('data-path');
    if (!rawPath) return;
    // Normalize path: convert Windows backslashes to forward slashes for file manager
    var normalized = rawPath.replace(/\\/g, '/');
    if (typeof switchTab === 'function') {
      switchTab('files');
    }
    if (typeof FileManager !== 'undefined') {
      FileManager.createTab(normalized);
    }
  });

  // --- Public API ---

  this.write = function (data) {
    if (_disposed) return;
    _parseAnsi(data);
    _scheduleRender();
  };

  this.resize = function (cols, rows) {
    _cols = cols;
    _rows = rows;
    _scheduleRender();
  };

  this.getCols = function () { return _cols; };
  this.getRows = function () { return _rows; };

  this.getDimensions = function () {
    _measureChar();
    var w = _wrapper.clientWidth || _wrapper.parentElement.clientWidth;
    var h = _wrapper.clientHeight || _wrapper.parentElement.clientHeight;
    var cols = Math.max(10, Math.floor((w - 16) / _charWidth));
    var rows = Math.max(3, Math.floor((h - 8) / _charHeight));
    _cols = cols;
    _rows = rows;
    return { cols: cols, rows: rows };
  };

  this.onData = function (cb) { _onDataCb = cb; };
  this.focus = function () { _wrapper.focus(); };

  this.clear = function () {
    _lines = [[]];
    _cursorRow = 0;
    _cursorCol = 0;
    _scheduleRender();
  };

  this.writeln = function (text) {
    this.write(text + '\r\n');
  };

  this.dispose = function () {
    _disposed = true;
    document.removeEventListener('keydown', _handleKeydown, true);
    if (_wrapper.parentNode) _wrapper.parentNode.removeChild(_wrapper);
  };

  // --- Internal: character metrics ---

  function _measureChar() {
    if (_wrapper.clientWidth < 10) return; // not visible yet
    var span = document.createElement('span');
    span.style.cssText =
      'visibility:hidden;position:absolute;white-space:pre;' +
      'font-family:"Cascadia Code","Fira Code","JetBrains Mono",Menlo,Monaco,monospace;' +
      'font-size:14px;line-height:16px;';
    span.textContent = 'MMMMMMMMMM'; // 10 M characters
    document.body.appendChild(span);
    var rect = span.getBoundingClientRect();
    _charWidth = rect.width / 10;
    _charHeight = rect.height || 16;
    document.body.removeChild(span);
  }

  // --- Internal: ANSI parser state machine ---

  function _parseAnsi(data) {
    for (var i = 0; i < data.length; i++) {
      var ch = data[i];
      var code = data.charCodeAt(i);

      // CSI sequence collection mode
      if (_csiMode) {
        if ((code >= 0x30 && code <= 0x3F) || ch === ';') {
          // Parameter bytes: 0-9, :, ;, <, =, >, ?
          _csiParams += ch;
        } else if (code >= 0x40 && code <= 0x7E) {
          // Final byte -- execute the CSI sequence
          _handleCSI(_csiParams, ch);
          _csiMode = false;
          _csiParams = '';
        } else {
          // Unexpected byte, abort CSI
          _csiMode = false;
          _csiParams = '';
        }
        continue;
      }

      // ESC was seen, check next character
      if (_escMode) {
        _escMode = false;
        if (ch === '[') {
          _csiMode = true;
          _csiParams = '';
        } else if (ch === 's') {
          _savedCursor.row = _cursorRow;
          _savedCursor.col = _cursorCol;
        } else if (ch === 'u') {
          _cursorRow = _savedCursor.row;
          _cursorCol = _savedCursor.col;
        } else if (ch === 'c') {
          // Full reset
          _lines = [[]];
          _cursorRow = 0;
          _cursorCol = 0;
          _attrs = { fg: 37, bg: -1, bold: false };
        }
        // Other ESC sequences (ESC (, ESC ), etc.) are silently ignored
        continue;
      }

      // ESC starts escape mode
      if (code === 0x1b) {
        _escMode = true;
        continue;
      }

      // Control characters
      if (code === 0x0d) { // CR
        _cursorCol = 0;
        continue;
      }
      if (code === 0x0a || code === 0x0b || code === 0x0c) { // LF, VT, FF
        _cursorRow++;
        _ensureLine(_cursorRow);
        if (_cursorRow >= _lines.length + _maxScrollback) {
          _lines.shift();
          _cursorRow--;
        }
        continue;
      }
      if (code === 0x08) { // BS
        if (_cursorCol > 0) _cursorCol--;
        continue;
      }
      if (code === 0x09) { // TAB
        var nextTab = Math.min(_cols, _cursorCol + (8 - (_cursorCol % 8)));
        _ensureLine(_cursorRow);
        while (_cursorCol < nextTab) {
          _setChar(_cursorRow, _cursorCol, ' ');
          _cursorCol++;
        }
        continue;
      }
      if (code === 0x07) { // BEL -- ignore
        continue;
      }
      if (code < 0x20) {
        // Other C0 control characters -- skip
        continue;
      }

      // DEL -- ignore
      if (code === 0x7f) continue;

      // Printable character
      _ensureLine(_cursorRow);
      _setChar(_cursorRow, _cursorCol, ch);
      _cursorCol++;
      if (_cursorCol >= _cols) {
        _cursorCol = 0;
        _cursorRow++;
        _ensureLine(_cursorRow);
      }
    }
  }

  // --- Internal: CSI sequence handler ---

  function _handleCSI(params, cmd) {
    var args = params.split(';').map(function (p) {
      return p === '' ? 0 : parseInt(p, 10);
    });
    if (isNaN(args[0])) args[0] = 0;

    switch (cmd) {
      case 'm': // SGR -- set graphics rendition
        _handleSGR(args);
        break;

      case 'H': case 'f': // Cursor position
        var r = (args[0] || 1) - 1;
        var c = (args[1] || 1) - 1;
        _cursorRow = Math.max(0, r);
        _cursorCol = Math.max(0, Math.min(c, _cols - 1));
        _ensureLine(_cursorRow);
        break;

      case 'J': // Erase in display
        _eraseDisplay(args[0] || 0);
        break;

      case 'K': // Erase in line
        _eraseLine(args[0] || 0);
        break;

      case 'A': // Cursor up
        _cursorRow = Math.max(0, _cursorRow - (args[0] || 1));
        break;

      case 'B': // Cursor down
        _cursorRow += (args[0] || 1);
        _ensureLine(_cursorRow);
        break;

      case 'C': // Cursor forward
        _cursorCol = Math.min(_cols - 1, _cursorCol + (args[0] || 1));
        break;

      case 'D': // Cursor back
        _cursorCol = Math.max(0, _cursorCol - (args[0] || 1));
        break;

      case 'E': // Cursor next line
        _cursorRow += (args[0] || 1);
        _cursorCol = 0;
        _ensureLine(_cursorRow);
        break;

      case 'F': // Cursor previous line
        _cursorRow = Math.max(0, _cursorRow - (args[0] || 1));
        _cursorCol = 0;
        break;

      case 'G': // Cursor horizontal absolute
        _cursorCol = Math.max(0, Math.min((args[0] || 1) - 1, _cols - 1));
        break;

      case 'd': // Cursor vertical absolute
        _cursorRow = Math.max(0, (args[0] || 1) - 1);
        _ensureLine(_cursorRow);
        break;

      case 's': // Save cursor (CSI variant)
        _savedCursor.row = _cursorRow;
        _savedCursor.col = _cursorCol;
        break;

      case 'u': // Restore cursor (CSI variant)
        _cursorRow = _savedCursor.row;
        _cursorCol = _savedCursor.col;
        break;

      case 'r': // Set scrolling region -- partially handled (ignored for now)
        break;

      case 'l': case 'h': // Set/reset mode (e.g., cursor visibility)
        break;

      case 'P': // Delete characters
        _deleteChars(args[0] || 1);
        break;

      case '@': // Insert blank characters
        _insertChars(args[0] || 1);
        break;

      case 'X': // Erase characters
        _eraseChars(args[0] || 1);
        break;

      // n (device status report), c (device attributes), etc. -- ignored
    }
  }

  // --- Internal: SGR (Select Graphic Rendition) ---

  function _handleSGR(args) {
    for (var i = 0; i < args.length; i++) {
      var p = args[i];
      if (p === 0) {
        _attrs = { fg: 37, bg: -1, bold: false };
      } else if (p === 1) {
        _attrs.bold = true;
      } else if (p === 22) {
        _attrs.bold = false;
      } else if (p >= 30 && p <= 37) {
        _attrs.fg = p;
      } else if (p === 38) {
        // Extended foreground
        if (args[i + 1] === 5) {
          // 256-color: 38;5;N
          _attrs.fg = 'fg-' + (args[i + 2] || 0);
          i += 2;
        } else if (args[i + 1] === 2) {
          // RGB: 38;2;R;G;B -- fall back to default
          i += 4;
        }
      } else if (p === 39) {
        _attrs.fg = 37; // default fg
      } else if (p >= 40 && p <= 47) {
        _attrs.bg = p;
      } else if (p === 48) {
        // Extended background
        if (args[i + 1] === 5) {
          _attrs.bg = 'bg-' + (args[i + 2] || 0);
          i += 2;
        } else if (args[i + 1] === 2) {
          i += 4;
        }
      } else if (p === 49) {
        _attrs.bg = -1; // default bg
      } else if (p >= 90 && p <= 97) {
        _attrs.fg = p; // bright foreground
      } else if (p >= 100 && p <= 107) {
        _attrs.bg = p; // bright background
      }
    }
  }

  // --- Internal: buffer helpers ---

  function _ensureLine(row) {
    while (_lines.length <= row) {
      _lines.push([]);
    }
    if (_lines.length > _maxScrollback) {
      var excess = _lines.length - _maxScrollback;
      _lines.splice(0, excess);
      _cursorRow = Math.max(0, _cursorRow - excess);
      row -= excess;
    }
  }

  function _setChar(row, col, ch) {
    if (!_lines[row]) _lines[row] = [];
    _lines[row][col] = {
      char: ch,
      fg: _attrs.fg,
      bg: _attrs.bg,
      bold: _attrs.bold
    };
  }

  function _eraseDisplay(mode) {
    if (mode === 2) {
      // Clear entire screen
      _lines = [];
      for (var i = 0; i < _rows; i++) _lines.push([]);
      _cursorRow = 0;
      _cursorCol = 0;
      return;
    }
    if (mode === 0) {
      // Erase from cursor to end of display
      _eraseLine(0);
      for (var i = _cursorRow + 1; i < _lines.length; i++) _lines[i] = [];
    } else if (mode === 1) {
      // Erase from start of display to cursor
      for (var i = 0; i < _cursorRow; i++) _lines[i] = [];
      _eraseLine(1);
    } else if (mode === 3) {
      // Erase scrollback
      var visible = _lines.slice(-_rows);
      _lines = visible;
      _cursorRow = Math.min(_cursorRow, _lines.length - 1);
    }
  }

  function _eraseLine(mode) {
    _ensureLine(_cursorRow);
    var line = _lines[_cursorRow];
    if (mode === 0) {
      // Erase from cursor to end of line
      line.length = Math.min(line.length, _cursorCol);
    } else if (mode === 1) {
      // Erase from start of line to cursor
      for (var i = 0; i <= Math.min(_cursorCol, line.length - 1); i++) {
        delete line[i];
      }
    } else if (mode === 2) {
      // Erase entire line
      _lines[_cursorRow] = [];
    }
  }

  function _deleteChars(n) {
    _ensureLine(_cursorRow);
    var line = _lines[_cursorRow];
    if (_cursorCol < line.length) {
      line.splice(_cursorCol, n);
    }
  }

  function _insertChars(n) {
    _ensureLine(_cursorRow);
    var line = _lines[_cursorRow];
    for (var i = 0; i < n; i++) {
      line.splice(_cursorCol, 0, undefined);
    }
    if (line.length > _cols) line.length = _cols;
  }

  function _eraseChars(n) {
    _ensureLine(_cursorRow);
    var line = _lines[_cursorRow];
    for (var i = _cursorCol; i < Math.min(_cursorCol + n, line.length); i++) {
      delete line[i];
    }
  }

  // --- Internal: rendering ---

  function _scheduleRender() {
    if (_renderPending) return;
    _renderPending = true;
    requestAnimationFrame(function () {
      _renderPending = false;
      if (!_disposed) _render();
    });
  }

  function _render() {
    var visibleStart = Math.max(0, _lines.length - _rows);
    var html = [];

    for (var vr = 0; vr < _rows; vr++) {
      var lineIdx = visibleStart + vr;
      var line = (lineIdx < _lines.length) ? _lines[lineIdx] : null;
      var absRow = lineIdx;

      // Render characters for this visible row
      var lineHtml = _renderLine(line, _cols);

      // Overlay the block cursor on this row if it belongs here
      if (absRow === _cursorRow) {
        var cCol = Math.min(_cursorCol, _cols - 1);
        var cursorCh = ' ';
        if (line && line[cCol] && line[cCol].char) {
          cursorCh = line[cCol].char;
        }
        // Build cursor span and inject at correct position
        lineHtml = _injectCursor(lineHtml, line, cCol, cursorCh);
      }

      html.push('<div class="term-line">' + lineHtml + '</div>');
    }

    _pre.innerHTML = html.join('');
  }

  function _renderLine(line, cols) {
    if (!line || line.length === 0) {
      return '<span class="term-space"> </span>';
    }

    // Extract plain text for path detection
    var plainText = '';
    for (var i = 0; i < cols; i++) {
      var cell = line[i];
      plainText += (cell && cell.char) ? cell.char : ' ';
    }

    // Find path ranges in the plain text
    var pathRanges = [];
    var pathMatch;
    _PATH_REGEX.lastIndex = 0;
    while ((pathMatch = _PATH_REGEX.exec(plainText)) !== null) {
      var matchStr = pathMatch[0];
      // Trim trailing punctuation that is unlikely to be part of a path
      var trimLen = matchStr.length;
      while (trimLen > 0 && /[.,;:!?)\]}>]/.test(matchStr[trimLen - 1])) {
        trimLen--;
      }
      matchStr = matchStr.substring(0, trimLen);
      // Require minimum length and at least one path separator or drive letter
      if (matchStr.length >= 4 && (matchStr.indexOf('/') !== -1 || matchStr.indexOf('\\') !== -1)) {
        pathRanges.push({
          start: pathMatch.index,
          end: pathMatch.index + trimLen,
          text: matchStr
        });
      }
    }

    // Check if a column index falls within a path range; return range index or -1
    function _pathAt(col) {
      for (var r = 0; r < pathRanges.length; r++) {
        if (col >= pathRanges[r].start && col < pathRanges[r].end) return r;
      }
      return -1;
    }

    var parts = [];
    var curFg = -1, curBg = -1, curBold = false;
    var curPath = -2; // -2 = uninitialized, -1 = not in path, >= 0 = path range index
    var buf = '';

    for (var i = 0; i < cols; i++) {
      var cell = line[i];
      var fg = 37, bg = -1, bold = false, ch = ' ';

      if (cell) {
        fg = cell.fg;
        bg = cell.bg;
        bold = cell.bold || false;
        ch = cell.char || ' ';
      }

      var pi = _pathAt(i);

      if (fg !== curFg || bg !== curBg || bold !== curBold || pi !== curPath) {
        if (buf) {
          var html = _wrapSpan(buf, curFg, curBg, curBold);
          if (curPath >= 0) {
            var ptext = pathRanges[curPath].text;
            html = '<span class="term-path" data-path="' + _escapeAttr(ptext) + '">' + html + '</span>';
          }
          parts.push(html);
        }
        buf = ch;
        curFg = fg;
        curBg = bg;
        curBold = bold;
        curPath = pi;
      } else {
        buf += ch;
      }
    }

    if (buf) {
      var html = _wrapSpan(buf, curFg, curBg, curBold);
      if (curPath >= 0) {
        var ptext = pathRanges[curPath].text;
        html = '<span class="term-path" data-path="' + _escapeAttr(ptext) + '">' + html + '</span>';
      }
      parts.push(html);
    }

    return parts.join('') || '<span class="term-space"> </span>';
  }

  function _injectCursor(lineHtml, line, cCol, cursorCh) {
    // Render the line up to the cursor column, then the cursor span, then the rest
    var before = '';
    var curFg = -1, curBg = -1, curBold = false;
    var buf = '';

    for (var i = 0; i < cCol; i++) {
      var cell = (line && line[i]) ? line[i] : null;
      var fg = cell ? (cell.fg || 37) : 37;
      var bg = cell ? (cell.bg != null ? cell.bg : -1) : -1;
      var bold = cell ? (cell.bold || false) : false;
      var ch = (cell && cell.char) ? cell.char : ' ';

      if (fg !== curFg || bg !== curBg || bold !== curBold) {
        if (buf) before += _wrapSpan(buf, curFg, curBg, curBold);
        buf = ch;
        curFg = fg; curBg = bg; curBold = bold;
      } else {
        buf += ch;
      }
    }
    if (buf) before += _wrapSpan(buf, curFg, curBg, curBold);

    // Cursor block character
    var cursorSpan =
      '<span class="term-cursor">' + _escapeChar(cursorCh) + '</span>';

    // After cursor
    var afterParts = [];
    curFg = -1; curBg = -1; curBold = false;
    buf = '';
    for (var i = cCol + 1; i < _cols; i++) {
      var cell = (line && line[i]) ? line[i] : null;
      var fg = cell ? (cell.fg || 37) : 37;
      var bg = cell ? (cell.bg != null ? cell.bg : -1) : -1;
      var bold = cell ? (cell.bold || false) : false;
      var ch = (cell && cell.char) ? cell.char : ' ';

      if (fg !== curFg || bg !== curBg || bold !== curBold) {
        if (buf) afterParts.push(_wrapSpan(buf, curFg, curBg, curBold));
        buf = ch;
        curFg = fg; curBg = bg; curBold = bold;
      } else {
        buf += ch;
      }
    }
    if (buf) afterParts.push(_wrapSpan(buf, curFg, curBg, curBold));

    var result = before + cursorSpan + afterParts.join('');
    return result || '<span class="term-space"> </span>';
  }

  function _wrapSpan(text, fg, bg, bold) {
    var cls = [];
    if (typeof fg === 'string') {
      cls.push('term-' + fg);
    } else if (fg !== 37) {
      cls.push('term-fg-' + fg);
    }
    if (typeof bg === 'string') {
      cls.push('term-' + bg);
    } else if (bg >= 0) {
      cls.push('term-bg-' + bg);
    }
    if (bold) cls.push('term-bold');
    if (cls.length === 0) {
      return _escapeChar(text);
    }
    return '<span class="' + cls.join(' ') + '">' + _escapeChar(text) + '</span>';
  }

  function _escapeChar(text) {
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
}


// ========================= TerminalManager =========================

var TerminalManager = (function () {
  var _tabs = [];
  var _activeTabId = null;
  var _tabCounter = 0;
  var _savedConnections = [];
  var _contextMenu = null;

  // DOM references (set in init)
  var _container = null;
  var _tabBar = null;
  var _body = null;

  // ========================= Initialization =========================

  function init() {
    _container = document.getElementById('terminalContainer');
    _tabBar = document.getElementById('terminalTabBar');
    _body = document.getElementById('terminalBody');

    if (!_container || !_tabBar || !_body) return;

    // Click on terminal body to focus the active terminal
    _body.addEventListener('click', function () {
      var tab = _getActiveTab();
      if (tab && tab.renderer) {
        tab.renderer.focus();
      }
    });

    // Add tab button
    var addBtn = document.getElementById('terminalAddBtn');
    if (addBtn) {
      addBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        _showAddMenu(e);
      });
    }

    // Close context menu and add menu on click outside
    document.addEventListener('click', function () {
      _hideContextMenu();
      _hideAddMenu();
    });

    // Load saved connections
    _loadSavedConnections();

    // Shared window resize handler for all terminal tabs
    var _resizeTimer = null;
    window.addEventListener('resize', function () {
      if (_resizeTimer) clearTimeout(_resizeTimer);
      _resizeTimer = setTimeout(function () {
        var tab = _getActiveTab();
        if (tab && tab.renderer) {
          var dims = tab.renderer.getDimensions();
          tab.renderer.resize(dims.cols, dims.rows);
          _sendResize(tab);
        }
      }, 150);
    });

    // Register with Router for activate/deactivate
    if (typeof Router !== 'undefined') {
      Router.register('terminal', {
        activate: function () { _onActivate(); },
        deactivate: function () { _onDeactivate(); },
      });
    }
  }

  function _onActivate() {
    // Fit the active terminal when tab becomes visible
    var tab = _getActiveTab();
    if (tab && tab.renderer) {
      setTimeout(function () {
        var dims = tab.renderer.getDimensions();
        tab.renderer.resize(dims.cols, dims.rows);
        _sendResize(tab);
      }, 100);
    }
  }

  function _onDeactivate() {
    // Nothing special needed
  }

  // ========================= Tab Management =========================

  function createTab(kind, options) {
    options = options || {};

    // Ensure the terminal sidebar tab is active so the panel is visible
    // (renderer needs visible container for proper dimension calculation)
    if (typeof switchTab === 'function') {
      switchTab('terminal');
    }

    _tabCounter++;
    var tabId = 'term-' + _tabCounter + '-' + Date.now();
    var name = options.name || (kind === 'ssh' ? '\u8FDC\u7A0B' : '\u672C\u5730') + ' ' + _tabCounter;

    var tab = {
      id: tabId,
      kind: kind,
      name: name,
      status: 'connecting',
      renderer: null,
      ws: null,
      sessionId: null,
      options: options,
    };

    _tabs.push(tab);
    _renderTabBar();
    _switchToTab(tabId);
    _initTerminal(tab);
    return tab;
  }

  function _initTerminal(tab) {
    // Create terminal pane container
    var termDiv = document.createElement('div');
    termDiv.className = 'terminal-pane';
    termDiv.id = 'terminal-pane-' + tab.id;
    termDiv.style.cssText = 'width:100%;height:100%;display:none;';
    _body.appendChild(termDiv);

    // Create custom renderer (initial size will be recalculated once visible)
    var renderer = new TerminalRenderer(termDiv, 80, 24);

    tab.renderer = renderer;

    // Small delay to let DOM settle, then measure and fit
    setTimeout(function () {
      var dims = renderer.getDimensions();
      renderer.resize(dims.cols, dims.rows);
    }, 50);

    // Local echo flag: default ON for Windows PIPE I/O (cmd.exe does not echo
    // typed characters when stdin is a pipe). Unix PTY backends already echo,
    // so set this to false if double-echo is observed.
    var LOCAL_ECHO = true;

    // Tracks characters typed on the current input line.
    // Used only to gate Backspace so it cannot erase the shell prompt.
    var _currentLine = '';

    // Input handler with local echo for Windows PIPE I/O compatibility.
    // Handles printable chars, Enter, Backspace, arrows, Ctrl keys, Tab.
    renderer.onData(function (data) {
      // Helper: send data string to the backend via WebSocket
      function _send(s) {
        if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
          tab.ws.send(JSON.stringify({ type: 'input', data: s }));
        }
      }

      var code = data.charCodeAt(0);

      // --- Enter (\r from _handleKeydown, or \r\n from paste) ---
      if (data === '\r' || data === '\r\n') {
        if (LOCAL_ECHO) renderer.write('\r\n');
        _send('\r\n');  // cmd.exe PIPE I/O requires \r\n as line terminator
        _currentLine = '';
        return;
      }

      // --- Backspace (DEL \x7f or BS \x08) ---
      if (code === 0x7f || code === 0x08) {
        if (_currentLine.length > 0) {
          _currentLine = _currentLine.slice(0, -1);
          if (LOCAL_ECHO) renderer.write('\x08 \x08');  // BS space BS: erase char visually
        }
        // Send \x08 to backend (BS works with both cmd.exe PIPE and PTY)
        _send('\x08');
        return;
      }

      // --- Ctrl+W (word delete, from Ctrl+Backspace) ---
      if (code === 0x17) {
        // Erase all tracked line chars locally (best-effort visual cleanup)
        if (LOCAL_ECHO) {
          for (var w = 0; w < _currentLine.length; w++) {
            renderer.write('\x08 \x08');
          }
        }
        _currentLine = '';
        _send(data);
        return;
      }

      // --- Arrow keys (Up/Down/Left/Right), Home, End, etc. ---
      // Forward to backend for shell history/cursor movement, no local echo.
      if (code === 0x1b && data.length > 1) {
        _send(data);
        return;
      }

      // --- Tab (\x09) — forward for backend completion, no local echo ---
      if (code === 0x09) {
        _send(data);
        return;
      }

      // --- Other control characters (Ctrl+A–Z, \x00–\x1a) ---
      // Forward to backend, no local echo.
      if (code < 0x20) {
        _send(data);
        return;
      }

      // --- Printable character (code >= 0x20, not DEL) ---
      _currentLine += data;
      if (LOCAL_ECHO) renderer.write(data);
      _send(data);
    });

    // Connect WebSocket
    _connectWebSocket(tab);

    // Show this terminal pane
    _showTabPane(tab.id);
  }

  function _connectWebSocket(tab) {
    var proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var sessionId = tab.id;
    var wsUrl = proto + '//' + window.location.host + '/v1/webui/ws/terminal/' + sessionId;

    var ws = new WebSocket(wsUrl);
    tab.ws = ws;

    ws.onopen = function () {
      // Send init message
      var cols = tab.renderer ? tab.renderer.getCols() : 80;
      var rows = tab.renderer ? tab.renderer.getRows() : 24;
      var initMsg = {
        type: 'init',
        kind: tab.kind,
        cols: cols,
        rows: rows,
      };

      if (tab.kind === 'ssh') {
        initMsg.host = tab.options.host || '';
        initMsg.port = tab.options.port || 22;
        initMsg.username = tab.options.username || '';
        initMsg.password = tab.options.password || '';
        initMsg.key_data = tab.options.key_data || '';
      }

      ws.send(JSON.stringify(initMsg));
    };

    ws.onmessage = function (event) {
      try {
        var msg = JSON.parse(event.data);
        if (msg.type === 'ready') {
          tab.sessionId = msg.session_id;
          tab.status = 'connected';
          _renderTabBar();
          // Send initial size
          _sendResize(tab);
        } else if (msg.type === 'output') {
          tab.renderer.write(msg.data);
        } else if (msg.type === 'error') {
          tab.renderer.writeln('\r\n\x1b[31m\u9519\u8BEF: ' + msg.message + '\x1b[0m');
          tab.status = 'disconnected';
          _renderTabBar();
        } else if (msg.type === 'exit') {
          tab.renderer.writeln(
            '\r\n\x1b[33m[\u8FDB\u7A0B\u5DF2\u9000\u51FA\uFF0C\u9000\u51FA\u7801 ' +
            msg.code + ']\x1b[0m'
          );
          tab.status = 'disconnected';
          _renderTabBar();
        }
      } catch (e) {
        // ignore
      }
    };

    ws.onclose = function () {
      tab.status = 'disconnected';
      _renderTabBar();
    };

    ws.onerror = function () {
      tab.status = 'disconnected';
      _renderTabBar();
      if (tab.renderer) {
        tab.renderer.writeln('\r\n\x1b[31m[WebSocket \u8FDE\u63A5\u9519\u8BEF]\x1b[0m');
      }
    };
  }

  function _sendResize(tab) {
    if (tab.ws && tab.ws.readyState === WebSocket.OPEN && tab.renderer) {
      tab.ws.send(JSON.stringify({
        type: 'resize',
        cols: tab.renderer.getCols(),
        rows: tab.renderer.getRows(),
      }));
    }
  }

  function _switchToTab(tabId) {
    _activeTabId = tabId;
    _renderTabBar();
    _showTabPane(tabId);

    // Measure and fit the active terminal
    var tab = _getActiveTab();
    if (tab && tab.renderer) {
      setTimeout(function () {
        var dims = tab.renderer.getDimensions();
        tab.renderer.resize(dims.cols, dims.rows);
        _sendResize(tab);
        tab.renderer.focus();
      }, 50);
    }
  }

  function _showTabPane(tabId) {
    // Hide all terminal panes, show the active one
    var panes = _body.querySelectorAll('.terminal-pane');
    for (var i = 0; i < panes.length; i++) {
      panes[i].style.display = panes[i].id === 'terminal-pane-' + tabId ? 'block' : 'none';
    }

    // Show/hide empty state
    var emptyState = document.getElementById('terminalEmptyState');
    if (emptyState) {
      emptyState.style.display = _tabs.length > 0 ? 'none' : 'flex';
    }
  }

  function closeTab(tabId) {
    var idx = -1;
    for (var i = 0; i < _tabs.length; i++) {
      if (_tabs[i].id === tabId) { idx = i; break; }
    }
    if (idx === -1) return;

    var tab = _tabs[idx];

    // Close WebSocket
    if (tab.ws) {
      try { tab.ws.close(); } catch (e) {}
    }

    // Dispose renderer
    if (tab.renderer) {
      try { tab.renderer.dispose(); } catch (e) {}
    }

    // Remove DOM
    var pane = document.getElementById('terminal-pane-' + tabId);
    if (pane) pane.remove();

    // Remove from array
    _tabs.splice(idx, 1);

    // Switch to another tab if needed
    if (_activeTabId === tabId) {
      if (_tabs.length > 0) {
        var newIdx = Math.min(idx, _tabs.length - 1);
        _switchToTab(_tabs[newIdx].id);
      } else {
        _activeTabId = null;
        _showTabPane(null);
      }
    }

    _renderTabBar();
  }

  function closeAllTabs() {
    var ids = _tabs.map(function (t) { return t.id; });
    for (var i = 0; i < ids.length; i++) {
      closeTab(ids[i]);
    }
  }

  function closeOtherTabs(keepTabId) {
    var ids = _tabs.map(function (t) { return t.id; });
    for (var i = 0; i < ids.length; i++) {
      if (ids[i] !== keepTabId) closeTab(ids[i]);
    }
  }

  function renameTab(tabId, newName) {
    var tab = _getTabById(tabId);
    if (tab && newName) {
      tab.name = newName;
      _renderTabBar();
    }
  }

  function _getTabById(tabId) {
    for (var i = 0; i < _tabs.length; i++) {
      if (_tabs[i].id === tabId) return _tabs[i];
    }
    return null;
  }

  function _getActiveTab() {
    return _getTabById(_activeTabId);
  }

  // ========================= Tab Bar Rendering =========================

  function _renderTabBar() {
    if (!_tabBar) return;

    // Save sidebar toggle button before clearing
    var sidebarToggle = _tabBar.querySelector('.tab-sidebar-toggle');
    var addBtn = document.getElementById('terminalAddBtn');

    // Clear existing tabs
    _tabBar.innerHTML = '';

    for (var i = 0; i < _tabs.length; i++) {
      var tab = _tabs[i];
      var el = document.createElement('div');
      el.className = 'terminal-tab' + (tab.id === _activeTabId ? ' active' : '');
      el.dataset.tabId = tab.id;

      var statusClass = tab.status === 'connected'
        ? 'connected'
        : (tab.status === 'disconnected' ? 'disconnected' : '');
      el.innerHTML =
        '<span class="terminal-tab-status ' + statusClass + '"></span>' +
        '<span class="terminal-tab-name">' + _escapeHtml(tab.name) + '</span>' +
        '<span class="terminal-tab-close">&times;</span>';

      // Click to switch or close
      (function (tid) {
        el.addEventListener('click', function (e) {
          if (e.target.classList.contains('terminal-tab-close')) {
            closeTab(tid);
          } else {
            _switchToTab(tid);
          }
        });

        // Right-click context menu
        el.addEventListener('contextmenu', function (e) {
          e.preventDefault();
          _showContextMenu(e, tid);
        });
      })(tab.id);

      _tabBar.appendChild(el);
    }

    // Re-add sidebar toggle button
    if (sidebarToggle) {
      _tabBar.insertBefore(sidebarToggle, _tabBar.firstChild);
    }

    // Re-add the add button
    if (addBtn) {
      _tabBar.appendChild(addBtn);
    } else {
      var newAddBtn = document.createElement('div');
      newAddBtn.className = 'terminal-tab-add';
      newAddBtn.id = 'terminalAddBtn';
      newAddBtn.innerHTML = '+';
      newAddBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        _showAddMenu(e);
      });
      _tabBar.appendChild(newAddBtn);
    }

    // Show/hide floating close-all button when tabs > 5
    var closeAllBtn = document.getElementById('terminalCloseAllBtn');
    if (_tabs.length > 5) {
      if (!closeAllBtn) {
        closeAllBtn = document.createElement('div');
        closeAllBtn.id = 'terminalCloseAllBtn';
        closeAllBtn.className = 'tab-close-all-btn';
        closeAllBtn.innerHTML = '&times; \u5168\u90E8\u5173\u95ED';
        closeAllBtn.title = '\u5173\u95ED\u6240\u6709\u6807\u7B7E';
        closeAllBtn.addEventListener('click', function (e) {
          e.stopPropagation();
          closeAllTabs();
        });
        _container.appendChild(closeAllBtn);
      }
      closeAllBtn.style.display = '';
    } else if (closeAllBtn) {
      closeAllBtn.style.display = 'none';
    }
  }

  // ========================= Context Menu =========================

  function _showContextMenu(event, tabId) {
    _hideContextMenu();

    _contextMenu = document.createElement('div');
    _contextMenu.className = 'terminal-context-menu';
    _contextMenu.style.left = event.clientX + 'px';
    _contextMenu.style.top = event.clientY + 'px';

    var items = [
      { label: '\u91CD\u547D\u540D', action: function () { _promptRename(tabId); } },
      { label: '\u91CD\u65B0\u8FDE\u63A5', action: function () { _reconnectTab(tabId); } },
      { separator: true },
      { label: '\u5173\u95ED', action: function () { closeTab(tabId); } },
      { label: '\u5173\u95ED\u5176\u4ED6', action: function () { closeOtherTabs(tabId); } },
      { label: '\u5173\u95ED\u5168\u90E8', action: function () { closeAllTabs(); }, danger: true },
    ];

    for (var i = 0; i < items.length; i++) {
      if (items[i].separator) {
        var sep = document.createElement('div');
        sep.className = 'terminal-context-menu-separator';
        _contextMenu.appendChild(sep);
      } else {
        var item = document.createElement('div');
        item.className = 'terminal-context-menu-item' + (items[i].danger ? ' danger' : '');
        item.textContent = items[i].label;
        (function (action) {
          item.addEventListener('click', function (e) {
            e.stopPropagation();
            _hideContextMenu();
            action();
          });
        })(items[i].action);
        _contextMenu.appendChild(item);
      }
    }

    document.body.appendChild(_contextMenu);

    // Adjust position if menu goes off-screen
    var rect = _contextMenu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      _contextMenu.style.left = (window.innerWidth - rect.width - 8) + 'px';
    }
    if (rect.bottom > window.innerHeight) {
      _contextMenu.style.top = (window.innerHeight - rect.height - 8) + 'px';
    }
  }

  function _hideContextMenu() {
    if (_contextMenu) {
      _contextMenu.remove();
      _contextMenu = null;
    }
  }

  function _promptRename(tabId) {
    var tab = _getTabById(tabId);
    if (!tab) return;
    var newName = prompt('\u91CD\u547D\u540D\u7EC8\u7AEF\u6807\u7B7E:', tab.name);
    if (newName && newName.trim()) {
      renameTab(tabId, newName.trim());
    }
  }

  function _reconnectTab(tabId) {
    var tab = _getTabById(tabId);
    if (!tab) return;

    // Close old WebSocket and reconnect
    if (tab.ws) {
      try { tab.ws.close(); } catch (e) {}
    }
    tab.status = 'connecting';
    tab.renderer.clear();
    tab.renderer.writeln('\x1b[33m[\u91CD\u65B0\u8FDE\u63A5\u4E2D...]\x1b[0m\r\n');
    _renderTabBar();
    _connectWebSocket(tab);
  }

  // ========================= Add Menu =========================

  function _showAddMenu(event) {
    _hideAddMenu();

    var menu = document.createElement('div');
    menu.className = 'terminal-context-menu';
    menu.id = 'terminalAddMenu';
    menu.style.left = event.clientX + 'px';
    menu.style.top = (event.clientY + 4) + 'px';

    var items = [
      {
        label: '+ \u672C\u5730\u7EC8\u7AEF',
        action: function () { createTab('local'); }
      },
      {
        label: '+ \u8FDC\u7A0B\u7EC8\u7AEF',
        action: function () { _showSSHDialog(); }
      },
    ];

    // Add saved connections
    if (_savedConnections.length > 0) {
      items.push({ separator: true });
      for (var i = 0; i < _savedConnections.length; i++) {
        (function (conn) {
          var label = conn.name || (conn.username + '@' + conn.host);
          items.push({
            label: label,
            action: function () {
              createTab('ssh', {
                host: conn.host,
                port: conn.port || 22,
                username: conn.username,
                password: conn.password || '',
                key_data: conn.key_data || '',
                name: label,
              });
            },
          });
        })(_savedConnections[i]);
      }
    }

    for (var i = 0; i < items.length; i++) {
      if (items[i].separator) {
        var sep = document.createElement('div');
        sep.className = 'terminal-context-menu-separator';
        menu.appendChild(sep);
      } else {
        var item = document.createElement('div');
        item.className = 'terminal-context-menu-item';
        item.textContent = items[i].label;
        (function (action) {
          item.addEventListener('click', function (e) {
            e.stopPropagation();
            _hideAddMenu();
            action();
          });
        })(items[i].action);
        menu.appendChild(item);
      }
    }

    document.body.appendChild(menu);

    // Adjust position
    var rect = menu.getBoundingClientRect();
    if (rect.right > window.innerWidth) {
      menu.style.left = (window.innerWidth - rect.width - 8) + 'px';
    }
    if (rect.bottom > window.innerHeight) {
      menu.style.top = (event.clientY - rect.height - 4) + 'px';
    }
  }

  function _hideAddMenu() {
    var menu = document.getElementById('terminalAddMenu');
    if (menu) menu.remove();
  }

  // ========================= SSH Dialog =========================

  function _showSSHDialog() {
    var overlay = document.createElement('div');
    overlay.className = 'terminal-ssh-dialog-overlay';
    overlay.id = 'terminalSSHOverlay';

    var savedHtml = '';
    if (_savedConnections.length > 0) {
      savedHtml = '<div class="terminal-ssh-saved">';
      savedHtml += '<div class="terminal-ssh-saved-title">\u5DF2\u4FDD\u5B58\u7684\u8FDE\u63A5</div>';
      for (var i = 0; i < _savedConnections.length; i++) {
        var conn = _savedConnections[i];
        savedHtml += '<div class="terminal-ssh-saved-item" data-idx="' + i + '">';
        savedHtml += '<div class="terminal-ssh-saved-item-info">';
        savedHtml += '<div class="terminal-ssh-saved-item-name">' +
          _escapeHtml(conn.name || conn.host) + '</div>';
        savedHtml += '<div class="terminal-ssh-saved-item-host">' +
          _escapeHtml(conn.username + '@' + conn.host + ':' + (conn.port || 22)) + '</div>';
        savedHtml += '</div>';
        savedHtml += '<span class="terminal-ssh-saved-item-del" data-idx="' + i + '">&times;</span>';
        savedHtml += '</div>';
      }
      savedHtml += '</div>';
    }

    overlay.innerHTML =
      '<div class="terminal-ssh-dialog">' +
      '<h3>SSH \u8FDC\u7A0B\u7EC8\u7AEF</h3>' +
      '<p class="terminal-ssh-dialog-subtitle">\u901A\u8FC7 SSH \u8FDE\u63A5\u8FDC\u7A0B\u670D\u52A1\u5668</p>' +
      '<div class="terminal-ssh-field">' +
      '<label>\u5FEB\u901F\u8FDE\u63A5</label>' +
      '<input type="text" id="sshQuickInput" ' +
        'placeholder="user@host:port \u6216 user:pass@host:port">' +
      '<div class="terminal-ssh-quick-hint">' +
        '\u6309\u56DE\u8F66\u89E3\u6790\uFF0C\u6216\u5728\u4E0B\u65B9\u586B\u5199\u8BE6\u7EC6\u4FE1\u606F</div>' +
      '</div>' +
      '<div class="terminal-ssh-row">' +
      '<div class="terminal-ssh-field">' +
      '<label>\u4E3B\u673A\u5730\u5740</label>' +
      '<input type="text" id="sshHost" placeholder="192.168.1.1">' +
      '</div>' +
      '<div class="terminal-ssh-field" style="max-width:100px;">' +
      '<label>\u7AEF\u53E3</label>' +
      '<input type="number" id="sshPort" value="22">' +
      '</div>' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label>\u7528\u6237\u540D</label>' +
      '<input type="text" id="sshUsername" placeholder="root">' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label>\u5BC6\u7801</label>' +
      '<input type="password" id="sshPassword" ' +
        'placeholder="\uFF08\u7559\u7A7A\u5219\u4F7F\u7528\u5BC6\u94A5\u8BA4\u8BC1\uFF09">' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label>\u79C1\u94A5\uFF08\u53EF\u9009\uFF09</label>' +
      '<textarea id="sshKey" placeholder="' +
        '-----BEGIN OPENSSH PRIVATE KEY-----&#10;...&#10;-----END OPENSSH PRIVATE KEY-----' +
      '"></textarea>' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label>\u8FDE\u63A5\u540D\u79F0\uFF08\u53EF\u9009\uFF09</label>' +
      '<input type="text" id="sshName" placeholder="\u6211\u7684\u670D\u52A1\u5668">' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label style="display:flex;align-items:center;gap:6px;cursor:pointer;">' +
      '<input type="checkbox" id="sshSave" checked style="width:auto;">' +
      ' \u4FDD\u5B58\u8FDE\u63A5\u4EE5\u4FBF\u540E\u7EED\u4F7F\u7528' +
      '</label>' +
      '</div>' +
      savedHtml +
      '<div class="terminal-ssh-actions">' +
      '<button class="terminal-ssh-btn-cancel" type="button" id="sshCancelBtn">' +
        '\u53D6\u6D88</button>' +
      '<button class="terminal-ssh-btn-connect" type="button" id="sshConnectBtn">' +
        '\u8FDE\u63A5</button>' +
      '</div>' +
      '</div>';

    document.body.appendChild(overlay);

    // Event listeners
    overlay.querySelector('#sshCancelBtn').addEventListener('click', function () {
      overlay.remove();
    });

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) overlay.remove();
    });

    overlay.querySelector('#sshConnectBtn').addEventListener('click', function () {
      _doSSHConnect(overlay);
    });

    // Quick input parse on Enter
    var quickInput = overlay.querySelector('#sshQuickInput');
    quickInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        _parseQuickConnect(quickInput.value, overlay);
      }
    });

    // Saved connection click handlers
    var savedItems = overlay.querySelectorAll('.terminal-ssh-saved-item');
    for (var i = 0; i < savedItems.length; i++) {
      (function (item) {
        var delBtn = item.querySelector('.terminal-ssh-saved-item-del');
        if (delBtn) {
          delBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            var idx = parseInt(delBtn.dataset.idx, 10);
            _savedConnections.splice(idx, 1);
            _saveSavedConnections();
            overlay.remove();
            _showSSHDialog();
          });
        }
        item.addEventListener('click', function () {
          var idx = parseInt(item.dataset.idx, 10);
          var conn = _savedConnections[idx];
          if (conn) {
            overlay.remove();
            createTab('ssh', {
              host: conn.host,
              port: conn.port || 22,
              username: conn.username,
              password: conn.password || '',
              key_data: conn.key_data || '',
              name: conn.name || (conn.username + '@' + conn.host),
            });
          }
        });
      })(savedItems[i]);
    }

    // Focus quick input
    quickInput.focus();
  }

  function _parseQuickConnect(input, overlay) {
    if (!input || !input.trim()) return;
    input = input.trim();

    var match;

    // Pattern: user:pass@host:port
    match = input.match(/^([^:@]+):([^@]+)@([^:]+):(\d+)$/);
    if (match) {
      overlay.querySelector('#sshUsername').value = match[1];
      overlay.querySelector('#sshPassword').value = match[2];
      overlay.querySelector('#sshHost').value = match[3];
      overlay.querySelector('#sshPort').value = match[4];
      return;
    }

    // Pattern: user@host:port
    match = input.match(/^([^@]+)@([^:]+):(\d+)$/);
    if (match) {
      overlay.querySelector('#sshUsername').value = match[1];
      overlay.querySelector('#sshHost').value = match[2];
      overlay.querySelector('#sshPort').value = match[3];
      return;
    }

    // Pattern: user@host
    match = input.match(/^([^@]+)@(.+)$/);
    if (match) {
      overlay.querySelector('#sshUsername').value = match[1];
      overlay.querySelector('#sshHost').value = match[2];
      return;
    }

    // Pattern: host:port
    match = input.match(/^([^:]+):(\d+)$/);
    if (match) {
      overlay.querySelector('#sshHost').value = match[1];
      overlay.querySelector('#sshPort').value = match[2];
      return;
    }

    // Just a host
    overlay.querySelector('#sshHost').value = input;
  }

  function _doSSHConnect(overlay) {
    var host = overlay.querySelector('#sshHost').value.trim();
    var port = parseInt(overlay.querySelector('#sshPort').value, 10) || 22;
    var username = overlay.querySelector('#sshUsername').value.trim();
    var password = overlay.querySelector('#sshPassword').value;
    var keyData = overlay.querySelector('#sshKey').value.trim();
    var name = overlay.querySelector('#sshName').value.trim();
    var saveConn = overlay.querySelector('#sshSave').checked;

    if (!host) {
      if (typeof toast === 'function') toast('\u4E3B\u673A\u5730\u5740\u4E0D\u80FD\u4E3A\u7A7A', 'error');
      return;
    }
    if (!username) {
      if (typeof toast === 'function') toast('\u7528\u6237\u540D\u4E0D\u80FD\u4E3A\u7A7A', 'error');
      return;
    }

    // Save connection if checked
    if (saveConn) {
      var conn = {
        host: host,
        port: port,
        username: username,
        password: password,
        key_data: keyData,
        name: name || (username + '@' + host),
      };
      _savedConnections.push(conn);
      _saveSavedConnections();
    }

    overlay.remove();

    createTab('ssh', {
      host: host,
      port: port,
      username: username,
      password: password,
      key_data: keyData,
      name: name || (username + '@' + host + ':' + port),
    });
  }

  // ========================= Saved Connections =========================

  async function _loadSavedConnections() {
    try {
      if (typeof persistLoad === 'function') {
        var data = await persistLoad('terminals.json');
        if (data && data.connections) {
          _savedConnections = data.connections;
        }
      }
    } catch (e) {
      // ignore
    }
  }

  async function _saveSavedConnections() {
    try {
      if (typeof persistSave === 'function') {
        await persistSave('terminals.json', { connections: _savedConnections });
      }
    } catch (e) {
      // ignore
    }
  }

  // ========================= Utilities =========================

  function _escapeHtml(text) {
    var d = document.createElement('div');
    d.textContent = String(text);
    return d.innerHTML;
  }

  // ========================= Public API =========================

  return {
    init: init,
    createTab: createTab,
    closeTab: closeTab,
    closeAllTabs: closeAllTabs,
    closeOtherTabs: closeOtherTabs,
    renameTab: renameTab,
    showSSHDialog: _showSSHDialog,
  };
})();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function () { TerminalManager.init(); });
} else {
  TerminalManager.init();
}
