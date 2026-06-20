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
        onAdd: function (e) { _showAddMenu(e); },
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
            var existing = await persistLoad('config.toml') || {};
            existing.layout = (typeof _tabLayoutConfig !== 'undefined') ? _tabLayoutConfig.layout : 'horizontal';
            existing.sidebarCompressed = collapsed;
            persistSave('config.toml', existing);
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

    // Close context menu and add menu on click outside
    document.addEventListener('click', function () {
      _hideContextMenu();
      _hideAddMenu();
    });

    // Load saved connections
    _loadSavedConnections();

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
    };

    _tabs.push(tab);

    // Add tab to TabBar
    if (_bar) {
      _bar.addTab({
        id: tabId,
        type: 'terminal',
        icon: '&#9002;_',
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
    // Create xterm.js container div inside the terminal pane
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
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#d4d4d4',
        selectionBackground: '#264f78',
      },
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
            var filtered = msg.data.replace(/\x1b\[\?[0-9;]*[a-zA-Z]/g, '');
            if (filtered) {
              tab.xterm.write(filtered);
            }
          }
        } else if (msg.type === 'error') {
          if (tab.xterm) {
            tab.xterm.write('\r\n\x1b[31m\u9519\u8BEF: ' + msg.message + '\x1b[0m');
          }
          tab.status = 'disconnected';
          if (_bar) _bar.setStatus(tab.id, 'disconnected');
        } else if (msg.type === 'exit') {
          if (tab.xterm) {
            tab.xterm.write(
              '\r\n\x1b[33m[\u8FDB\u7A0B\u5DF2\u9000\u51FA\uFF0C\u9000\u51FA\u7801 ' +
              msg.code + ']\x1b[0m'
            );
          }
          tab.status = 'disconnected';
          if (_bar) _bar.setStatus(tab.id, 'disconnected');
        } else if (msg.type === 'session_closed') {
          // Backend confirms the session was killed (response to close_session)
          // Tab is already being cleaned up by closeTab()
        } else if (msg.type === 'existing_sessions') {
          // Backend advertises surviving sessions from a previous server run.
          // Store the list so the frontend can recreate tabs in a later phase.
          if (msg.sessions && msg.sessions.length > 0) {
            window._existingTerminalSessions = msg.sessions;
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
        tab.xterm.write('\r\n\x1b[31m[WebSocket \u8FDE\u63A5\u9519\u8BEF]\x1b[0m');
      }
    };
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
          theme: {
            background: '#1e1e1e',
            foreground: '#d4d4d4',
            cursor: '#d4d4d4',
            selectionBackground: '#264f78',
          },
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

        xterm.write('\x1b[33m[\u91CD\u65B0\u8FDE\u63A5\u4E2D...]\x1b[0m\r\n');
      }
    }

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
