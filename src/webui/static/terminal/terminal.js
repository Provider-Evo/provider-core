/**
 * Terminal Tab -- xterm.js-based terminal with local and SSH support.
 *
 * Uses @xterm/xterm v5 for rendering and keyboard capture (loaded via CDN).
 * Uses @xterm/addon-fit for automatic resize to container dimensions.
 *
 * Features:
 * - xterm.js for full VT100/xterm emulation (ANSI, cursor, scrollback, etc.)
 * - Unified TabBar for tab rendering (horizontal/vertical/compressed layouts)
 * - Local terminal via WebSocket to backend (ConPTY or pipe mode)
 * - SSH remote terminal via paramiko on backend
 * - ResizeObserver-based resize propagation to backend
 * - Right-click context menu
 * - SSH dialog with quick-parse (user@host:port, user:pass@host:port)
 * - Saved SSH connections via persist API
 *
 * Requires (loaded by LazyLoader before this script):
 * - @xterm/xterm v5.5.0  (global: Terminal)
 * - @xterm/addon-fit v0.10.0  (global: FitAddon)
 * - TabBar (global: TabBar)
 */

// ========================= TerminalManager =========================

var TerminalManager = (function () {
  var _tabs = [];
  var _activeTabId = null;
  var _tabCounter = 0;
  var _savedConnections = [];
  var _contextMenu = null;
  var _discoveryProcessed = false; // guard against double-processing existing sessions
  var _terminalBgMode = 'theme'; // 'theme' | 'original' | 'custom'
  var _pendingDecStrip = ''; // pending incomplete escape sequence for cross-message handling
  var _customBgImage = ''; // custom background image data URL
  var _customBgOpacity = 0.3; // custom background opacity (0-1)

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
    // Prepend any pending incomplete sequence from previous message
    data = _pendingDecStrip + data;
    _pendingDecStrip = '';

    // Check for incomplete escape sequence at the end
    var lastEsc = data.lastIndexOf('\x1b');
    if (lastEsc !== -1) {
      var suffix = data.slice(lastEsc);
      // If suffix doesn't match a complete sequence pattern, it's incomplete
      if (!/\x1b\[[0-9;]*[a-zA-Z]/.test(suffix) &&
          !/\x1b\[\?[0-9;]*c/.test(suffix)) {
        // Might be incomplete, keep as pending
        _pendingDecStrip = suffix;
        data = data.slice(0, lastEsc);
      }
    }

    // Strip Device Attribute responses (end with 'c' after ?)
    // e.g. \x1b[?6c  \x1b[?1;2c  \x1b[?62;1;2;6c
    return data.replace(/\x1b\[\?[0-9;]*c/g, '')
               .replace(/\x1b\[[0-9;]*[cR]/g, '');
  }

  /**
   * Return xterm.js theme colors based on background mode and current UI theme.
   * @param {string} bgMode - 'theme', 'original', or 'custom'
   */
  function _getTerminalTheme(bgMode) {
    bgMode = bgMode || _terminalBgMode;

    if (bgMode === 'original') {
      // Classic dark terminal theme (VS Code style)
      return {
        background: '#1e1e1e',
        foreground: '#cccccc',
        cursor: '#ffffff',
        selectionBackground: '#264f78',
        black: '#1e1e1e',
        red: '#f44747',
        green: '#6a9955',
        yellow: '#dcdcaa',
        blue: '#569cd6',
        magenta: '#c586c0',
        cyan: '#4ec9b0',
        white: '#cccccc',
        brightBlack: '#808080',
        brightRed: '#f44747',
        brightGreen: '#6a9955',
        brightYellow: '#dcdcaa',
        brightBlue: '#569cd6',
        brightMagenta: '#c586c0',
        brightCyan: '#4ec9b0',
        brightWhite: '#ffffff',
      };
    }

    if (bgMode === 'custom') {
      // Custom image mode: transparent background to let CSS background show through
      var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
      return {
        background: 'rgba(0,0,0,0)',
        foreground: isDark ? '#edf3ff' : '#162033',
        cursor: isDark ? '#edf3ff' : '#162033',
        selectionBackground: isDark ? 'rgba(42,58,92,0.8)' : 'rgba(219,227,255,0.8)',
        black: isDark ? '#172131' : '#172131',
        red: isDark ? '#ff7b7b' : '#d94848',
        green: isDark ? '#37ca7e' : '#1f9d61',
        yellow: isDark ? '#ffb454' : '#d17b17',
        blue: isDark ? '#8aa4ff' : '#4263eb',
        magenta: isDark ? '#c084fc' : '#9333ea',
        cyan: isDark ? '#22d3ee' : '#0891b2',
        white: isDark ? '#edf3ff' : '#f3f6fb',
        brightBlack: isDark ? '#9eabc2' : '#5d6980',
        brightRed: isDark ? '#ff9b9b' : '#ef4444',
        brightGreen: isDark ? '#5ee6a0' : '#22c55e',
        brightYellow: isDark ? '#ffc97a' : '#f59e0b',
        brightBlue: isDark ? '#a8bbff' : '#6366f1',
        brightMagenta: isDark ? '#d4a5ff' : '#a855f7',
        brightCyan: isDark ? '#5ee9f5' : '#06b6d4',
        brightWhite: '#ffffff',
      };
    }

    // Theme mode: follow provider-v2 global light/dark theme
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark) {
      return {
        background: '#0d1420',
        foreground: '#edf3ff',
        cursor: '#edf3ff',
        selectionBackground: '#2a3a5c',
        black: '#172131',
        red: '#ff7b7b',
        green: '#37ca7e',
        yellow: '#ffb454',
        blue: '#8aa4ff',
        magenta: '#c084fc',
        cyan: '#22d3ee',
        white: '#edf3ff',
        brightBlack: '#9eabc2',
        brightRed: '#ff9b9b',
        brightGreen: '#5ee6a0',
        brightYellow: '#ffc97a',
        brightBlue: '#a8bbff',
        brightMagenta: '#d4a5ff',
        brightCyan: '#5ee9f5',
        brightWhite: '#ffffff',
      };
    }
    return {
      background: '#ffffff',
      foreground: '#162033',
      cursor: '#162033',
      selectionBackground: '#dbe3ff',
      black: '#172131',
      red: '#d94848',
      green: '#1f9d61',
      yellow: '#d17b17',
      blue: '#4263eb',
      magenta: '#9333ea',
      cyan: '#0891b2',
      white: '#f3f6fb',
      brightBlack: '#5d6980',
      brightRed: '#ef4444',
      brightGreen: '#22c55e',
      brightYellow: '#f59e0b',
      brightBlue: '#6366f1',
      brightMagenta: '#a855f7',
      brightCyan: '#06b6d4',
      brightWhite: '#ffffff',
    };
  }

  /**
   * Apply terminal background mode to all open tabs and persist the setting.
   * @param {string} mode - 'theme', 'original', or 'custom'
   */
  function _applyTerminalBgMode(mode) {
    _terminalBgMode = mode;
    document.documentElement.setAttribute('data-terminal-bg', mode);

    // Toggle CSS class on terminal body
    if (_body) {
      _body.classList.remove('terminal-body--original', 'terminal-body--custom');
      if (mode === 'original') {
        _body.classList.add('terminal-body--original');
      } else if (mode === 'custom') {
        _body.classList.add('terminal-body--custom');
        _applyCustomBgImage();
      }
    }

    // Update all open xterm instances
    var theme = _getTerminalTheme(mode);
    for (var i = 0; i < _tabs.length; i++) {
      var tab = _tabs[i];
      if (tab.xterm) {
        tab.xterm.options.theme = theme;
      }
    }

    _saveTerminalBgMode();
    _updateBgModeButton();
    _updateCustomBgControls();
  }

  /**
   * Apply custom background image to terminal body.
   */
  function _applyCustomBgImage() {
    if (!_body) return;
    if (_customBgImage) {
      // Store background image URL in CSS variable for pseudo-element
      _body.style.setProperty('--custom-bg-image', 'url(' + _customBgImage + ')');
      _body.style.setProperty('--custom-bg-opacity', _customBgOpacity);
    } else {
      _body.style.removeProperty('--custom-bg-image');
      _body.style.removeProperty('--custom-bg-opacity');
    }
  }

  /**
   * Migrate legacy base64 data URL to server-side file.
   * Converts the data URL to a Blob, uploads it, and updates stored URL.
   * @param {string} dataUrl - Legacy base64 data URL
   */
  function _migrateBgImageToServer(dataUrl) {
    // Convert data URL to Blob
    var parts = dataUrl.split(',');
    if (parts.length !== 2) return;
    var mime = parts[0].match(/:(.*?);/);
    if (!mime) return;
    var bstr = atob(parts[1]);
    var n = bstr.length;
    var u8arr = new Uint8Array(n);
    while (n--) {
      u8arr[n] = bstr.charCodeAt(n);
    }
    var blob = new Blob([u8arr], { type: mime[1] });
    var ext = (mime[1].split('/')[1] || 'png').split(';')[0];
    var filename = 'terminal-bg-migrated.' + ext;
    var formData = new FormData();
    formData.append('file', blob, filename);
    fetch('/v1/webui/bg-image', { method: 'POST', body: formData })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (data && data.url) {
          _customBgImage = data.url;
          _applyCustomBgImage();
          _saveTerminalBgMode();
        }
      })
      .catch(function() {});
  }

  /**
   * Set custom background image from file input.
   * Uploads the image to the server and stores the URL path.
   * @param {File} file - Image file
   */
  function _setCustomBgImage(file) {
    if (!file || !file.type.startsWith('image/')) return;
    var formData = new FormData();
    formData.append('file', file);
    fetch('/v1/webui/bg-image', { method: 'POST', body: formData })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (data && data.url) {
          _customBgImage = data.url;
          _applyCustomBgImage();
          _saveTerminalBgMode();
        }
      })
      .catch(function() {});
  }

  /**
   * Clear custom background image.
   */
  function _clearCustomBgImage() {
    _customBgImage = '';
    _customBgOpacity = 0.3;
    _applyCustomBgImage();
    _saveTerminalBgMode();
  }

  /**
   * Set custom background opacity.
   * @param {number} opacity - Value between 0 and 1
   */
  function _setCustomBgOpacity(opacity) {
    _customBgOpacity = Math.max(0, Math.min(1, opacity));
    if (_body) {
      // Update CSS variable for background opacity (affects pseudo-element only)
      _body.style.setProperty('--custom-bg-opacity', _customBgOpacity);
    }
    _saveTerminalBgMode();
  }

  /**
   * Toggle between background modes: theme -> original -> custom -> theme
   */
  function _toggleTerminalBgMode() {
    var modes = ['theme', 'original', 'custom'];
    var idx = modes.indexOf(_terminalBgMode);
    var next = modes[(idx + 1) % modes.length];
    _applyTerminalBgMode(next);
  }

  /**
   * Get display label for current background mode.
   */
  function _getBgModeLabel() {
    var labels = {
      'original': '\u7ECF\u5178\u9ED1\u8272',
      'custom': '\u81EA\u5B9A\u4E49\u56FE\u7247',
      'theme': 'Provider \u4E3B\u9898'
    };
    return labels[_terminalBgMode] || 'Provider \u4E3B\u9898';
  }

  /**
   * Update the background mode button display.
   */
  function _updateBgModeButton() {
    var iconEl = document.getElementById('terminalBgModeIcon');
    var labelEl = document.getElementById('terminalBgModeLabel');
    var icons = {
      'original': '\u263E', // ☾ moon
      'custom': '\u25A3',   // ▣ image
      'theme': '\u2600'     // ☀ sun
    };
    if (iconEl) {
      iconEl.textContent = icons[_terminalBgMode] || '\u2600';
    }
    if (labelEl) {
      labelEl.textContent = _getBgModeLabel();
    }
  }

  /**
   * Update custom background controls visibility and state.
   */
  function _updateCustomBgControls() {
    var controls = document.getElementById('terminalCustomBgControls');
    var opacityRange = document.getElementById('terminalBgOpacityRange');

    if (controls) {
      controls.style.display = _terminalBgMode === 'custom' ? 'flex' : 'none';
    }

    if (opacityRange) {
      opacityRange.value = Math.round(_customBgOpacity * 100);
    }
  }

  /**
   * Save terminal background mode to持久化 storage.
   */
  async function _saveTerminalBgMode() {
    try {
      if (typeof persistSave === 'function') {
        var existing = await persistLoad('terminals.json') || {};
        existing.bgMode = _terminalBgMode;
        if (_terminalBgMode === 'custom') {
          existing.bgImage = _customBgImage;
          existing.bgOpacity = _customBgOpacity;
        } else {
          // Clear custom settings when not in custom mode
          delete existing.bgImage;
          delete existing.bgOpacity;
        }
        await persistSave('terminals.json', existing);
      }
    } catch (e) { /* ignore */ }
  }

  /**
   * Load terminal background mode from持久化 storage.
   * Handles both legacy data URLs and new server-side file paths.
   */
  async function _loadTerminalBgMode() {
    try {
      if (typeof persistLoad === 'function') {
        var data = await persistLoad('terminals.json');
        if (data && data.bgMode) {
          _terminalBgMode = data.bgMode;
        }
        if (data && data.bgImage) {
          // Legacy data URL: migrate to server-side file
          if (data.bgImage.indexOf('data:') === 0) {
            _migrateBgImageToServer(data.bgImage);
          } else {
            _customBgImage = data.bgImage;
          }
        }
        if (data && typeof data.bgOpacity === 'number') {
          _customBgOpacity = data.bgOpacity;
        }
      }
    } catch (e) { /* ignore */ }
    // Apply the loaded mode
    _applyTerminalBgMode(_terminalBgMode);
  }

  // DOM references (set in init)
  var _container = null;
  var _tabBarEl = null;
  var _body = null;

  // TabBar instance
  var _bar = null;

  // ========================= Initialization =========================

  function init() {
    _container = document.getElementById('terminalContainer');
    _tabBarEl = document.getElementById('terminalTabBar');
    _body = document.getElementById('terminalBody');

    if (!_container || !_tabBarEl || !_body) return;

    // Open a lightweight WS probe immediately to discover surviving
    // sessions from a previous page load.  The backend sends an
    // existing_sessions message as soon as any WS connects.  By
    // launching the probe here (before the rest of init finishes),
    // the session list arrives while TabBar is being set up, so
    // tabs appear instantly when the response comes back.
    _probeForDiscovery();

    // Also fire a REST pre-fetch in parallel — whichever returns first
    // (WS or REST) creates the tab UI; the other is dedup-guarded.
    _restPreFetch();

    // Create the unified TabBar instance
    if (typeof TabBar !== 'undefined') {
      _bar = TabBar.create(_container, {
        tabBarEl: _tabBarEl,
        bodyEl: _body,
        layout: 'horizontal',
        collapsed: false,
        closeAllThreshold: 6,
        onSwitch: function (id) { _switchToTab(id); },
        onClose: function (id) { closeTab(id); },
        onContextMenu: function (id, event) { _showContextMenu(event, id); },
        onAdd: function () { _createChooserTab(); },
        onCloseAll: function () { closeAllTabs(); },
        onToggleCollapsed: function (collapsed) {
          // Update shared layout config
          if (typeof _tabLayoutConfig !== 'undefined') {
            _tabLayoutConfig.sidebarCompressed = collapsed;
          }
          // Propagate collapsed state to ALL registered TabBar instances
          // so both terminal and files sidebars expand/compress together.
          var bars = window._tabBars || {};
          var keys = Object.keys(bars);
          for (var i = 0; i < keys.length; i++) {
            if (bars[keys[i]] !== _bar && bars[keys[i]] && typeof bars[keys[i]].setCollapsed === 'function') {
              bars[keys[i]].setCollapsed(collapsed);
            }
          }
          // Persist the state
          (async function () {
            var existing = await persistLoad('terminals.json') || {};
            existing.layout = (typeof _tabLayoutConfig !== 'undefined') ? _tabLayoutConfig.layout : 'horizontal';
            existing.sidebarCompressed = collapsed;
            persistSave('terminals.json', existing);
          })();
        },
      });

      // Register in global registry for bootstrap.js layout toggle
      if (window._tabBars) {
        window._tabBars.terminal = _bar;
      }

      // Apply current layout from _tabLayoutConfig (may have been loaded from persist)
      if (typeof _tabLayoutConfig !== 'undefined') {
        _bar.setLayout(_tabLayoutConfig.layout || 'horizontal', _tabLayoutConfig.sidebarCompressed || false);
      }
    }

    // Click on terminal body to focus the active xterm instance
    _body.addEventListener('click', function () {
      var tab = _getActiveTab();
      if (tab && tab.xterm) {
        tab.xterm.focus();
      }
    });

    // Close context menu on click outside
    document.addEventListener('click', function () {
      _hideContextMenu();
    });

    // Load saved connections
    _loadSavedConnections();

    // Load terminal background mode preference
    _loadTerminalBgMode();

    // Background mode button click handler
    var bgModeBtn = document.getElementById('terminalBgModeBtn');
    if (bgModeBtn) {
      bgModeBtn.addEventListener('click', function () {
        _toggleTerminalBgMode();
        _updateBgModeButton();
        _updateCustomBgControls();
      });
    }
    _updateBgModeButton();

    // Custom background controls
    var bgImageBtn = document.getElementById('terminalBgImageBtn');
    if (bgImageBtn) {
      bgImageBtn.addEventListener('click', function () {
        _showImagePicker();
      });
    }

    var bgOpacityRange = document.getElementById('terminalBgOpacityRange');
    if (bgOpacityRange) {
      bgOpacityRange.addEventListener('input', function(e) {
        _setCustomBgOpacity(parseInt(e.target.value) / 100);
      });
    }

    _updateCustomBgControls();

    // Window resize: trigger fit on active terminal.
    // Per-tab ResizeObservers handle their own pane sizing,
    // but window resize may not fire ResizeObserver on hidden panes.
    var _resizeTimer = null;
    window.addEventListener('resize', function () {
      if (_resizeTimer) clearTimeout(_resizeTimer);
      _resizeTimer = setTimeout(function () {
        var tab = _getActiveTab();
        if (tab && tab.fitAddon) {
          try {
            tab.fitAddon.fit();
            _sendResize(tab);
          } catch (e) { /* ignore fit errors during layout transitions */ }
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

    // Session discovery is handled by _probeForDiscovery() at the start
    // of init(), which uses a WebSocket to receive existing_sessions.
  }

  function _updateTabTitle(tab) {
    if (!tab || !_bar) return;

    var title = tab.name;
    if (tab._hasRunningSubprocess && tab._childCommandLabel) {
      title += ' [' + tab._childCommandLabel + ']';
    }

    _bar.setTitle(tab.id, title);
  }

  function _onActivate() {
    // Fit the active terminal when tab becomes visible
    var tab = _getActiveTab();
    if (tab && tab.fitAddon) {
      setTimeout(function () {
        try {
          tab.fitAddon.fit();
          _sendResize(tab);
        } catch (e) { /* ignore */ }
        if (tab.xterm) tab.xterm.focus();
      }, 100);
    }
  }

  function _onDeactivate() {
    // Nothing special needed
  }

  // ========================= Tab Management =========================

  function createTab(kind, options) {
    options = options || {};

    // Ensure the terminal sidebar tab is visible so the pane has dimensions
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
      xterm: null,
      fitAddon: null,
      ws: null,
      sessionId: null,
      options: options,
      _resizeObserver: null,
      _container: null,
      _readOnly: false,
    };

    _tabs.push(tab);

    // Add tab to TabBar
    if (_bar) {
      _bar.addTab({
        id: tabId,
        type: 'terminal',
        icon: '',
        title: name,
        closable: true,
        status: 'connecting',
      });
      _bar.setActive(tabId);
    }

    _activeTabId = tabId;
    _showTabPane(tabId);
    _initTerminal(tab);
    return tab;
  }

  function _initTerminal(tab) {
    // Dispose any existing xterm instance to prevent ghost cursors
    // or duplicate xterm instances on reattach/reconnect.
    if (tab._resizeObserver) {
      try { tab._resizeObserver.disconnect(); } catch (e) {}
      tab._resizeObserver = null;
    }
    if (tab.xterm) {
      try { tab.xterm.dispose(); } catch (e) {}
      tab.xterm = null;
    }
    if (tab.fitAddon) {
      try { tab.fitAddon.dispose(); } catch (e) {}
      tab.fitAddon = null;
    }
    if (tab.ws) {
      try { tab.ws.close(); } catch (e) {}
      tab.ws = null;
    }

    // Create xterm.js container div inside the terminal pane.
    // Remove any pre-existing pane for this tab to avoid orphaned DOM nodes.
    var oldPane = document.getElementById('terminal-pane-' + tab.id);
    if (oldPane) oldPane.remove();

    var termDiv = document.createElement('div');
    termDiv.className = 'terminal-pane';
    termDiv.id = 'terminal-pane-' + tab.id;
    termDiv.style.cssText = 'width:100%;height:100%;display:none;';
    _body.appendChild(termDiv);

    var xtermContainer = document.createElement('div');
    xtermContainer.className = 'xterm-container';
    termDiv.appendChild(xtermContainer);

    tab._container = xtermContainer;

    // Verify xterm.js loaded from CDN
    if (typeof Terminal === 'undefined') {
      xtermContainer.innerHTML =
        '<div style="color:#f44747;padding:16px;font-family:monospace;">' +
        'xterm.js \u52A0\u8F7D\u5931\u8D25\uFF0C\u8BF7\u68C0\u67E5\u7F51\u7EDC\u8FDE\u63A5\u540E\u5237\u65B0\u9875\u9762\u3002</div>';
      tab.status = 'disconnected';
      if (_bar) _bar.setStatus(tab.id, 'disconnected');
      return;
    }

    // Create xterm.js Terminal instance
    var xterm = new Terminal({
      cursorBlink: true,
      cursorStyle: 'block',
      fontFamily: '"Cascadia Code","Fira Code","JetBrains Mono",Menlo,Monaco,monospace',
      fontSize: 14,
      lineHeight: 1.15,
      scrollback: 5000,
      allowProposedApi: true,
      theme: _getTerminalTheme(),
    });

    // Create and load FitAddon
    var fitAddon = new FitAddon.FitAddon();
    xterm.loadAddon(fitAddon);

    // Open terminal in the container
    xterm.open(xtermContainer);

    // Fit to container dimensions
    try { fitAddon.fit(); } catch (e) { /* ignore initial fit errors */ }

    tab.xterm = xterm;
    tab.fitAddon = fitAddon;

    // ResizeObserver: detect container size changes and propagate to backend.
    // Fires when the pane becomes visible, when the window is resized,
    // or when the sidebar/layout changes.
    var ro = new ResizeObserver(function () {
      if (!tab.xterm || !tab.fitAddon) return;
      try {
        tab.fitAddon.fit();
      } catch (e) { return; }
      if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
        _sendResize(tab);
      }
    });
    ro.observe(termDiv);
    tab._resizeObserver = ro;

    // Keyboard input -> WebSocket.
    // xterm.js captures all keystrokes via its internal <textarea> and
    // fires onData with the properly encoded terminal input string.
    // The backend PTY (ConPTY or pipe) handles character echo;
    // xterm.js renders whatever the backend sends back via {type:'output'}.
    // No local echo is needed on the frontend.
    xterm.onData(function (data) {
      if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
        tab.ws.send(JSON.stringify({ type: 'input', data: data }));
      }
    });

    // Binary input handler for mouse events (TUI apps like htop, vim, mc).
    // xterm.js emits binary mouse protocol data via onBinary when the
    // application enables mouse tracking (DECSET 1000/1002/1003).
    xterm.onBinary(function (data) {
      if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
        tab.ws.send(JSON.stringify({ type: 'input', data: data }));
      }
    });

    // Ensure xterm gets focus on click inside its container.
    xtermContainer.addEventListener('click', function () {
      xterm.focus();
    });

    // Connect WebSocket
    _connectWebSocket(tab);

    // Show this terminal pane
    _showTabPane(tab.id);

    // Send initial dimensions once WebSocket is ready
    setTimeout(function () {
      try { fitAddon.fit(); } catch (e) { /* ignore */ }
      if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
        _sendResize(tab);
      }
    }, 100);
  }

  function _connectWebSocket(tab) {
    var proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var sessionId = tab.id;
    var wsUrl = proto + '//' + window.location.host + '/v1/webui/ws/terminal/' + sessionId;

    var ws = new WebSocket(wsUrl);
    tab.ws = ws;

    ws.onopen = function () {
      // Reset pending DEC strip state for new connection
      _pendingDecStrip = '';

      // Send init message with terminal dimensions and connection parameters
      var cols = tab.xterm ? tab.xterm.cols : 80;
      var rows = tab.xterm ? tab.xterm.rows : 24;
      var initMsg = {
        type: 'init',
        kind: tab.kind,
        cols: cols,
        rows: rows,
        name: tab.name,
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
          if (_bar) _bar.setStatus(tab.id, 'connected');
          // Send initial dimensions after backend is ready
          _sendResize(tab);
        } else if (msg.type === 'mode') {
          // Backend signals ConPTY (real PTY) or pipe fallback.
          // With xterm.js, both modes work the same way on the frontend:
          // all input is forwarded, all output is rendered.
          // The PTY/pipe echo behavior is handled entirely by the backend.
          tab._mode = msg.mode;
        } else if (msg.type === 'output') {
          if (tab.xterm) {
            // Filter out DEC private mode responses that leak through ConPTY
            // (e.g. ^[[?1;2c device-attributes response).  xterm.js handles
            // these internally; they should not appear as visible text.
            var filtered = _stripDecResponses(msg.data);
            if (filtered) {
              tab.xterm.write(filtered);
            }
          }
        } else if (msg.type === 'error') {
          if (tab.xterm) {
            tab.xterm.write(_stripDecResponses('\r\n\x1b[31m\u9519\u8BEF: ' + msg.message + '\x1b[0m'));
          }
          tab.status = 'disconnected';
          if (_bar) _bar.setStatus(tab.id, 'disconnected');
        } else if (msg.type === 'exit') {
          if (tab.xterm) {
            if (msg.code === -1) {
              // Non-reattachable session (recovered after server restart)
              tab.xterm.write(_stripDecResponses(
                '\r\n\x1b[33m[\u6B64\u4F1A\u8BDD\u4E3A\u5386\u53F2\u8BB0\u5F55\uFF0C\u8FDB\u7A0B\u5DF2\u4E0D\u53EF\u4EA4\u4E92]\x1b[0m\r\n'
              ));
              tab._readOnly = true;
              if (_bar) _bar.setTitle(tab.id, tab.name + ' [\u5386\u53F2]');
            } else {
              tab.xterm.write(_stripDecResponses(
                '\r\n\x1b[33m[\u8FDB\u7A0B\u5DF2\u9000\u51FA\uFF0C\u9000\u51FA\u7801 ' +
                msg.code + ']\x1b[0m'
              ));
            }
          }
          tab.status = 'disconnected';
          if (_bar) _bar.setStatus(tab.id, 'disconnected');
        } else if (msg.type === 'session_closed') {
          // Backend confirms the session was killed (response to close_session)
          // Tab is already being cleaned up by closeTab()
        } else if (msg.type === 'metadata') {
          // Subprocess monitoring metadata
          if (msg.has_running_subprocess !== undefined) {
            tab._hasRunningSubprocess = msg.has_running_subprocess;
            tab._childCommandLabel = msg.child_command_label || null;
            _updateTabTitle(tab);
          }
        } else if (msg.type === 'existing_sessions') {
          // Backend advertises surviving sessions from a previous connection.
          // Recreate tab UI and reconnect WebSocket for each alive session.
          // Skip if discovery was already handled by probe or REST pre-fetch.
          if (!_discoveryProcessed && msg.sessions && msg.sessions.length > 0) {
            _reconnectExistingSessions(msg.sessions);
          }
        }
      } catch (e) {
        // ignore JSON parse errors
      }
    };

    ws.onclose = function () {
      tab.status = 'disconnected';
      if (_bar) _bar.setStatus(tab.id, 'disconnected');
    };

    ws.onerror = function () {
      tab.status = 'disconnected';
      if (_bar) _bar.setStatus(tab.id, 'disconnected');
      if (tab.xterm) {
        tab.xterm.write(_stripDecResponses('\r\n\x1b[31m[WebSocket \u8FDE\u63A5\u9519\u8BEF]\x1b[0m'));
      }
    };
  }

  // ========================= Session Reconnection =========================

  /**
   * Recreate tab UI and reconnect WebSocket for each surviving session
   * advertised by the backend via the `existing_sessions` message.
   *
   * Phase 1 (synchronous): create tab entries and TabBar UI elements so
   * the user sees tabs immediately — even before xterm.js or WS are ready.
   * Phase 2 (async via setTimeout): initialise xterm.js and open per-session
   * WebSocket connections that reattach and flush buffered offline output.
   *
   * Skips sessions that already have a tab (avoids duplicates on reconnect).
   */
  function _reconnectExistingSessions(sessions) {
    // Guard: only process discovery once per page load to prevent
    // duplicate tab creation when both WS probe and REST return results.
    if (_discoveryProcessed) return;
    _discoveryProcessed = true;

    // Phase 1 — create tab UI synchronously so tabs appear immediately
    var toInit = [];
    for (var i = 0; i < sessions.length; i++) {
      var s = sessions[i];
      if (!s.alive) continue;
      // Skip if a tab with this session ID already exists
      if (_getTabById(s.session_id)) continue;

      _tabCounter++;
      var name = s.name || (s.kind === 'ssh' ? '\u8FDC\u7A0B' : '\u672C\u5730') + ' ' + _tabCounter;

      var tab = {
        id: s.session_id,
        kind: s.kind || 'local',
        name: name,
        status: 'connecting',
        xterm: null,
        fitAddon: null,
        ws: null,
        sessionId: s.session_id,
        options: {},
        _resizeObserver: null,
        _container: null,
        _readOnly: false,
      };

      _tabs.push(tab);

      // Add tab to TabBar immediately so the user sees it
      if (_bar) {
        _bar.addTab({
          id: s.session_id,
          type: 'terminal',
          icon: '',
          title: name,
          closable: true,
          status: 'connecting',
        });
      }

      toInit.push(tab);
    }

    // Activate the last reconnected tab (or keep current active)
    if (_tabs.length > 0 && !_activeTabId) {
      _switchToTab(_tabs[_tabs.length - 1].id);
    }

    _showTabPane(_activeTabId);

    // Phase 2 — asynchronously attach xterm.js + WS for each tab.
    // The tab UI is already visible; xterm output streams in as each
    // WS connection establishes and the backend reattaches.
    for (var j = 0; j < toInit.length; j++) {
      (function (t) {
        setTimeout(function () { _initTerminal(t); }, j * 0);
      })(toInit[j]);
    }
  }

  /**
   * Open a lightweight WebSocket probe to discover surviving terminal
   * sessions.  The backend sends an ``existing_sessions`` message on
   * every new WS connection.  This probe receives that list without
   * creating a server-side terminal session (it never sends ``init``),
   * then closes.  The ``existing_sessions`` handler registered in every
   * WS onmessage (including this probe) calls _reconnectExistingSessions
   * to create tab UI synchronously and attach xterm + WS asynchronously.
   *
   * Called once at the START of init() so the response arrives while
   * the rest of the UI is still being set up — tabs appear instantly.
   */
  function _probeForDiscovery() {
    var proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    var probeId = '_probe_' + Date.now();
    var wsUrl = proto + '//' + window.location.host + '/v1/webui/ws/terminal/' + probeId;

    try {
      var ws = new WebSocket(wsUrl);
      ws.onmessage = function (event) {
        try {
          var msg = JSON.parse(event.data);
          if (msg.type === 'existing_sessions' && msg.sessions && msg.sessions.length > 0) {
            if (!_discoveryProcessed) {
              _reconnectExistingSessions(msg.sessions);
            }
          }
        } catch (e) {
          // ignore parse errors
        }
      };
      ws.onopen = function () {
        // The backend sends existing_sessions automatically on connect.
        // We never send 'init', so no server-side PTY is created.
        // Close the probe after a short delay to allow the message to arrive.
        setTimeout(function () {
          try { ws.close(); } catch (e) {}
        }, 2000);
      };
      ws.onerror = function () {};
      ws.onclose = function () {};
    } catch (e) {
      // Ignore WebSocket creation errors (e.g. network unavailable)
    }
  }

  /**
   * REST-based discovery that runs in parallel with the WS probe.
   * Whichever returns first (WS or REST) creates the tab UI;
   * the other is blocked by the _discoveryProcessed guard.
   * The REST endpoint is faster on most networks (single HTTP round-trip
   * vs WS handshake + message), providing the quickest tab appearance.
   */
  function _restPreFetch() {
    try {
      fetch('/v1/webui/terminal/sessions')
        .then(function (resp) {
          if (!resp.ok) return null;
          return resp.json();
        })
        .then(function (sessions) {
          if (_discoveryProcessed) return;
          if (!sessions || !Array.isArray(sessions)) return;
          var alive = sessions.filter(function (s) { return s.alive; });
          if (alive.length > 0) {
            _reconnectExistingSessions(alive);
          }
        })
        .catch(function () {
          // Ignore network or parse errors — WS probe is the fallback
        });
    } catch (e) {
      // Ignore
    }
  }

  function _sendResize(tab) {
    if (tab.ws && tab.ws.readyState === WebSocket.OPEN && tab.xterm) {
      tab.ws.send(JSON.stringify({
        type: 'resize',
        cols: tab.xterm.cols,
        rows: tab.xterm.rows,
      }));
    }
  }

  function _switchToTab(tabId) {
    _activeTabId = tabId;
    if (_bar) _bar.setActive(tabId);
    _showTabPane(tabId);

    // Fit the active terminal and send resize to backend
    var tab = _getActiveTab();
    if (tab && tab.fitAddon) {
      setTimeout(function () {
        try {
          tab.fitAddon.fit();
          _sendResize(tab);
        } catch (e) { /* ignore fit errors during transitions */ }
        if (tab.xterm) tab.xterm.focus();
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

    // Send close_session message to backend before closing WS.
    // This tells the server to kill the process (explicit close).
    // Without this, the server would just detach and keep the process alive.
    if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
      try {
        tab.ws.send(JSON.stringify({ type: 'close_session' }));
      } catch (e) {}
    }

    // Close WebSocket (after a tick to allow close_session to flush)
    var wsRef = tab.ws;
    setTimeout(function () {
      if (wsRef) { try { wsRef.close(); } catch (e) {} }
    }, 50);

    // Disconnect ResizeObserver
    if (tab._resizeObserver) {
      try { tab._resizeObserver.disconnect(); } catch (e) {}
    }

    // Dispose xterm.js instance
    if (tab.xterm) {
      try { tab.xterm.dispose(); } catch (e) {}
    }
    if (tab.fitAddon) {
      try { tab.fitAddon.dispose(); } catch (e) {}
    }

    // Remove DOM
    var pane = document.getElementById('terminal-pane-' + tabId);
    if (pane) pane.remove();

    // Remove from array
    _tabs.splice(idx, 1);

    // Remove from TabBar
    if (_bar) _bar.removeTab(tabId);

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
      if (_bar) _bar.setTitle(tabId, newName);
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
      { label: '\u6E05\u9664\u5386\u53F2', action: function () { _clearHistory(tabId); } },
      { label: '\u91CD\u542F\u7EC8\u7AEF', action: function () { _restartTerminal(tabId); } },
      { separator: true },
      { label: '\u80CC\u666F\u6A21\u5F0F: ' + _getBgModeLabel(), action: function () { _toggleTerminalBgMode(); } },
    ];

    // Add custom background options if in custom mode
    if (_terminalBgMode === 'custom') {
      items.push({ separator: true });
      items.push({ label: '\u9009\u62E9\u80CC\u666F\u56FE\u7247', action: function () { _showImagePicker(); } });
      if (_customBgImage) {
        items.push({ label: '\u6E05\u9664\u80CC\u666F\u56FE\u7247', action: function () { _clearCustomBgImage(); } });
        items.push({ label: '\u900F\u660E\u5EA6: ' + Math.round(_customBgOpacity * 100) + '%', action: function () { _cycleCustomBgOpacity(); } });
      }
    }

    items.push({ separator: true });
    items.push({ label: '\u5173\u95ED', action: function () { closeTab(tabId); } });
    items.push({ label: '\u5173\u95ED\u5176\u4ED6', action: function () { closeOtherTabs(tabId); } });
    items.push({ label: '\u5173\u95ED\u5168\u90E8', action: function () { closeAllTabs(); }, danger: true });

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
    showInputDialog('输入新的终端标签名称:', {
      title: '重命名终端标签',
      defaultValue: tab.name,
      placeholder: '终端标签名称'
    }).then(function(newName) {
      if (newName && newName.trim()) {
        renameTab(tabId, newName.trim());
      }
    });
  }

  /**
   * Show image picker dialog for custom background.
   */
  function _showImagePicker() {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.style.display = 'none';
    input.addEventListener('change', function(e) {
      if (e.target.files && e.target.files[0]) {
        _setCustomBgImage(e.target.files[0]);
      }
      document.body.removeChild(input);
    });
    document.body.appendChild(input);
    input.click();
  }

  /**
   * Cycle custom background opacity: 0.1 -> 0.3 -> 0.5 -> 0.7 -> 0.9 -> 0.1
   */
  function _cycleCustomBgOpacity() {
    var steps = [0.1, 0.3, 0.5, 0.7, 0.9];
    var idx = steps.indexOf(_customBgOpacity);
    var next = steps[(idx + 1) % steps.length];
    _setCustomBgOpacity(next);
  }

  function _reconnectTab(tabId) {
    var tab = _getTabById(tabId);
    if (!tab) return;

    // Send close_session to kill the old process before reconnecting
    if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
      try { tab.ws.send(JSON.stringify({ type: 'close_session' })); } catch (e) {}
    }

    // Close old WebSocket
    if (tab.ws) {
      try { tab.ws.close(); } catch (e) {}
    }

    // Dispose old xterm.js instance and observer
    if (tab._resizeObserver) {
      try { tab._resizeObserver.disconnect(); } catch (e) {}
    }
    if (tab.xterm) {
      try { tab.xterm.dispose(); } catch (e) {}
    }

    tab.status = 'connecting';
    if (_bar) _bar.setStatus(tabId, 'connecting');

    // Create fresh xterm.js instance in the existing pane
    var pane = document.getElementById('terminal-pane-' + tabId);
    if (pane) {
      pane.innerHTML = '';
      var xtermContainer = document.createElement('div');
      xtermContainer.className = 'xterm-container';
      pane.appendChild(xtermContainer);
      tab._container = xtermContainer;

      if (typeof Terminal !== 'undefined') {
        var xterm = new Terminal({
          cursorBlink: true,
          cursorStyle: 'block',
          fontFamily: '"Cascadia Code","Fira Code","JetBrains Mono",Menlo,Monaco,monospace',
          fontSize: 14,
          lineHeight: 1.15,
          scrollback: 5000,
          allowProposedApi: true,
          theme: _getTerminalTheme(),
        });
        var fitAddon = new FitAddon.FitAddon();
        xterm.loadAddon(fitAddon);
        xterm.open(xtermContainer);
        try { fitAddon.fit(); } catch (e) { /* ignore */ }

        tab.xterm = xterm;
        tab.fitAddon = fitAddon;

        // Re-attach ResizeObserver
        var ro = new ResizeObserver(function () {
          if (!tab.xterm || !tab.fitAddon) return;
          try { tab.fitAddon.fit(); } catch (e) { return; }
          if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
            _sendResize(tab);
          }
        });
        ro.observe(pane);
        tab._resizeObserver = ro;

        // Re-attach input handler
        xterm.onData(function (data) {
          if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
            tab.ws.send(JSON.stringify({ type: 'input', data: data }));
          }
        });

        // Re-attach binary input handler for mouse events (TUI apps)
        xterm.onBinary(function (data) {
          if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
            tab.ws.send(JSON.stringify({ type: 'input', data: data }));
          }
        });

        // Re-attach click-to-focus
        xtermContainer.addEventListener('click', function () {
          xterm.focus();
        });

        xterm.write(_stripDecResponses('\x1b[33m[\u91CD\u65B0\u8FDE\u63A5\u4E2D...]\x1b[0m\r\n'));
      }
    }

    _connectWebSocket(tab);
  }

  function _clearHistory(tabId) {
    var tab = _getTabById(tabId);
    if (!tab || !tab.ws || tab.ws.readyState !== WebSocket.OPEN) return;

    try {
      tab.ws.send(JSON.stringify({ type: 'clear' }));
      if (tab.xterm) {
        tab.xterm.clear();
        tab.xterm.write('\x1b[33m[\u5386\u53F2\u5DF2\u6E05\u9664]\x1b[0m\r\n');
      }
    } catch (e) {
      console.error('Failed to send clear command:', e);
    }
  }

  function _restartTerminal(tabId) {
    var tab = _getTabById(tabId);
    if (!tab || !tab.ws || tab.ws.readyState !== WebSocket.OPEN) return;

    showConfirmDialog('确定要重启终端吗？当前进程将被终止。', {
      title: '重启终端',
      confirmText: '重启',
      cancelText: '取消'
    }).then(function(confirmed) {
      if (!confirmed) return;

      try {
        var cols = tab.xterm ? tab.xterm.cols : 80;
        var rows = tab.xterm ? tab.xterm.rows : 24;
        tab.ws.send(JSON.stringify({ type: 'restart', cols: cols, rows: rows }));
        if (tab.xterm) {
          tab.xterm.clear();
          tab.xterm.write('\x1b[33m[\u91CD\u542F\u4E2D...]\x1b[0m\r\n');
        }
      } catch (e) {
        console.error('Failed to send restart command:', e);
      }
    });
  }

  // ========================= Chooser Tab (New Tab Page) =========================

  /**
   * Create a new chooser tab — similar to Chrome's new-tab page.
   * The tab renders the welcome/guide page inside its pane, with buttons
   * for "本地终端" and "远程终端".  Clicking either converts the tab
   * into a real terminal of that type.
   */
  function _createChooserTab() {
    // Ensure the terminal sidebar tab is visible
    if (typeof switchTab === 'function') {
      switchTab('terminal');
    }

    var tabId = 'chooser-' + Date.now();
    var name = '\u65B0\u6807\u7B7E\u9875';  // 新标签页

    var tab = {
      id: tabId,
      kind: 'chooser',
      name: name,
      status: 'idle',
      xterm: null,
      fitAddon: null,
      ws: null,
      sessionId: null,
      options: {},
      _resizeObserver: null,
      _container: null,
    };

    _tabs.push(tab);

    // Create pane with welcome page content
    var paneDiv = document.createElement('div');
    paneDiv.className = 'terminal-pane';
    paneDiv.id = 'terminal-pane-' + tabId;
    paneDiv.style.cssText = 'width:100%;height:100%;display:none;';

    var welcomeEl = _renderWelcomePage();
    paneDiv.appendChild(welcomeEl);
    _body.appendChild(paneDiv);

    // Add tab to TabBar
    if (_bar) {
      _bar.addTab({
        id: tabId,
        type: 'terminal',
        icon: '+',
        title: name,
        closable: true,
      });
      _bar.setActive(tabId);
    }

    _activeTabId = tabId;
    _showTabPane(tabId);

    // Wire up the welcome page buttons
    _wireWelcomePageButtons(welcomeEl, tabId);
  }

  /**
   * Render the welcome/guide page element — the same UI shown in the
   * zero-tab empty state, but reusable inside any tab pane.
   * Returns a DOM element.
   */
  function _renderWelcomePage() {
    var div = document.createElement('div');
    div.className = 'terminal-empty-state';
    div.innerHTML =
      '<div class="terminal-empty-state-icon">&#9002;_</div>' +
      '<div class="terminal-empty-state-text">\u9009\u62E9\u7EC8\u7AEF\u7C7B\u578B</div>' +
      '<div class="terminal-empty-state-actions">' +
      '<button type="button" class="welcome-local-btn">+ \u672C\u5730\u7EC8\u7AEF</button>' +
      '<button type="button" class="welcome-ssh-btn">+ \u8FDC\u7A0B\u7EC8\u7AEF</button>' +
      '</div>';
    return div;
  }

  /**
   * Wire up the Local / Remote buttons inside a welcome page element
   * to convert the owning chooser tab into a real terminal tab.
   */
  function _wireWelcomePageButtons(el, tabId) {
    var localBtn = el.querySelector('.welcome-local-btn');
    var sshBtn = el.querySelector('.welcome-ssh-btn');

    if (localBtn) {
      localBtn.addEventListener('click', function () {
        _convertChooserToLocal(tabId);
      });
    }

    if (sshBtn) {
      sshBtn.addEventListener('click', function () {
        _convertChooserToSSH(tabId);
      });
    }
  }

  /**
   * Convert a chooser tab into a local terminal tab.
   * Updates tab metadata, tab bar display, then initialises xterm.js + WS.
   */
  function _convertChooserToLocal(tabId) {
    var tab = _getTabById(tabId);
    if (!tab || tab.kind !== 'chooser') return;

    _tabCounter++;
    tab.kind = 'local';
    tab.name = '\u672C\u5730 ' + _tabCounter;  // 本地 N
    tab.status = 'connecting';

    // Update TabBar display
    if (_bar) {
      _bar.setTitle(tabId, tab.name);
      _bar.setIcon(tabId, '');
      _bar.setStatus(tabId, 'connecting');
    }

    // _initTerminal removes the old pane and creates a fresh xterm pane
    _initTerminal(tab);
  }

  /**
   * Convert a chooser tab into an SSH terminal tab.
   * Opens the SSH dialog; on successful connection the tab is converted.
   * If the user cancels, the chooser tab remains unchanged.
   */
  function _convertChooserToSSH(tabId) {
    _showSSHDialog(tabId);
  }

  // ========================= SSH Dialog =========================

  function _showSSHDialog(chooserTabId) {
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
      _doSSHConnect(overlay, chooserTabId);
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
            _showSSHDialog(chooserTabId);
          });
        }
        item.addEventListener('click', function () {
          var idx = parseInt(item.dataset.idx, 10);
          var conn = _savedConnections[idx];
          if (conn) {
            overlay.remove();
            var opts = {
              host: conn.host,
              port: conn.port || 22,
              username: conn.username,
              password: conn.password || '',
              key_data: conn.key_data || '',
              name: conn.name || (conn.username + '@' + conn.host),
            };
            if (chooserTabId) {
              _convertChooserTabToSSH(chooserTabId, opts);
            } else {
              createTab('ssh', opts);
            }
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

  function _doSSHConnect(overlay, chooserTabId) {
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

    var opts = {
      host: host,
      port: port,
      username: username,
      password: password,
      key_data: keyData,
      name: name || (username + '@' + host + ':' + port),
    };

    if (chooserTabId) {
      _convertChooserTabToSSH(chooserTabId, opts);
    } else {
      createTab('ssh', opts);
    }
  }

  /**
   * Convert a chooser tab into an SSH terminal tab.
   * Updates tab metadata, tab bar display, then initialises xterm.js + WS.
   */
  function _convertChooserTabToSSH(tabId, options) {
    var tab = _getTabById(tabId);
    if (!tab || tab.kind !== 'chooser') {
      // Fallback: if tab no longer exists or isn't a chooser, create a new tab
      createTab('ssh', options);
      return;
    }

    _tabCounter++;
    tab.kind = 'ssh';
    tab.name = options.name || ('\u8FDC\u7A0B ' + _tabCounter);
    tab.status = 'connecting';
    tab.options = options;

    // Update TabBar display
    if (_bar) {
      _bar.setTitle(tabId, tab.name);
      _bar.setIcon(tabId, '');
      _bar.setStatus(tabId, 'connecting');
    }

    // _initTerminal removes the old pane and creates a fresh xterm pane
    _initTerminal(tab);
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
        var existing = await persistLoad('terminals.json') || {};
        existing.connections = _savedConnections;
        await persistSave('terminals.json', existing);
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
    refreshTheme: function () {
      if (_terminalBgMode === 'theme') {
        var theme = _getTerminalTheme('theme');
        for (var i = 0; i < _tabs.length; i++) {
          if (_tabs[i].xterm) {
            _tabs[i].xterm.options.theme = theme;
          }
        }
      }
    },
  };
})();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function () { TerminalManager.init(); });
} else {
  TerminalManager.init();
}
