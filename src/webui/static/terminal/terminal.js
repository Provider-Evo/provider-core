/**
 * Terminal Tab — xterm.js-based terminal with local and SSH support.
 *
 * Features:
 * - Horizontal tab bar with add/close/rename
 * - Local terminal via WebSocket to backend
 * - SSH remote terminal via paramiko on backend
 * - Resize handling
 * - Right-click context menu
 * - SSH dialog with quick-parse (user@host:port, user:pass@host:port)
 * - Saved SSH connections via persist API
 */
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
      if (tab && tab.term) {
        tab.term.focus();
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

    // Close context menu on click outside
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
        if (tab && tab.fitAddon) {
          tab.fitAddon.fit();
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
    if (tab && tab.fitAddon) {
      setTimeout(function () {
        tab.fitAddon.fit();
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
    // (xterm.js needs visible container for proper dimension calculation)
    if (typeof switchTab === 'function') {
      switchTab('terminal');
    }

    _tabCounter++;
    var tabId = 'term-' + _tabCounter + '-' + Date.now();
    var name = options.name || (kind === 'ssh' ? '远程' : '本地') + ' ' + _tabCounter;

    var tab = {
      id: tabId,
      kind: kind,
      name: name,
      status: 'connecting',
      term: null,
      fitAddon: null,
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
    // Create xterm instance
    var termDiv = document.createElement('div');
    termDiv.className = 'terminal-pane';
    termDiv.id = 'terminal-pane-' + tab.id;
    termDiv.style.cssText = 'width:100%;height:100%;display:none;';
    _body.appendChild(termDiv);

    var term = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: '"Cascadia Code", "Fira Code", "JetBrains Mono", Menlo, Monaco, monospace',
      theme: {
        background: '#1e1e1e',
        foreground: '#d4d4d4',
        cursor: '#d4d4d4',
        selectionBackground: '#264f78',
        black: '#1e1e1e',
        red: '#f44747',
        green: '#6a9955',
        yellow: '#d7ba7d',
        blue: '#569cd6',
        magenta: '#c586c0',
        cyan: '#4ec9b0',
        white: '#d4d4d4',
        brightBlack: '#808080',
        brightRed: '#f44747',
        brightGreen: '#6a9955',
        brightYellow: '#d7ba7d',
        brightBlue: '#569cd6',
        brightMagenta: '#c586c0',
        brightCyan: '#4ec9b0',
        brightWhite: '#ffffff',
      },
      allowProposedApi: true,
    });

    var fitAddon = new FitAddon.FitAddon();
    term.loadAddon(fitAddon);

    term.open(termDiv);

    // Small delay to let DOM settle, then fit
    setTimeout(function () {
      fitAddon.fit();
    }, 50);

    tab.term = term;
    tab.fitAddon = fitAddon;

    // Input handler
    term.onData(function (data) {
      if (tab.ws && tab.ws.readyState === WebSocket.OPEN) {
        tab.ws.send(JSON.stringify({ type: 'input', data: data }));
      }
    });

    // Context menu on tab bar
    // (handled in _renderTabBar)

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
      var initMsg = {
        type: 'init',
        kind: tab.kind,
        cols: tab.term.cols,
        rows: tab.term.rows,
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
          tab.term.write(msg.data);
        } else if (msg.type === 'error') {
          tab.term.writeln('\r\n\x1b[31m错误: ' + msg.message + '\x1b[0m');
          tab.status = 'disconnected';
          _renderTabBar();
        } else if (msg.type === 'exit') {
          tab.term.writeln('\r\n\x1b[33m[进程已退出，退出码 ' + msg.code + ']\x1b[0m');
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
      tab.term.writeln('\r\n\x1b[31m[WebSocket 连接错误]\x1b[0m');
    };
  }

  function _sendResize(tab) {
    if (tab.ws && tab.ws.readyState === WebSocket.OPEN && tab.term) {
      tab.ws.send(JSON.stringify({
        type: 'resize',
        cols: tab.term.cols,
        rows: tab.term.rows,
      }));
    }
  }

  function _switchToTab(tabId) {
    _activeTabId = tabId;
    _renderTabBar();
    _showTabPane(tabId);

    // Fit the active terminal
    var tab = _getActiveTab();
    if (tab && tab.fitAddon) {
      setTimeout(function () {
        tab.fitAddon.fit();
        _sendResize(tab);
        if (tab.term) tab.term.focus();
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

    // Dispose xterm
    if (tab.term) {
      try { tab.term.dispose(); } catch (e) {}
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

      var statusClass = tab.status === 'connected' ? 'connected' : (tab.status === 'disconnected' ? 'disconnected' : '');
      el.innerHTML =
        '<span class="terminal-tab-status ' + statusClass + '"></span>' +
        '<span class="terminal-tab-name">' + _escapeHtml(tab.name) + '</span>' +
        '<span class="terminal-tab-close">&times;</span>';

      // Click to switch
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
  }

  // ========================= Context Menu =========================

  function _showContextMenu(event, tabId) {
    _hideContextMenu();

    _contextMenu = document.createElement('div');
    _contextMenu.className = 'terminal-context-menu';
    _contextMenu.style.left = event.clientX + 'px';
    _contextMenu.style.top = event.clientY + 'px';

    var items = [
      { label: '重命名', action: function () { _promptRename(tabId); } },
      { label: '重新连接', action: function () { _reconnectTab(tabId); } },
      { separator: true },
      { label: '关闭', action: function () { closeTab(tabId); } },
      { label: '关闭其他', action: function () { closeOtherTabs(tabId); } },
      { label: '关闭全部', action: function () { closeAllTabs(); }, danger: true },
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
    var newName = prompt('重命名终端标签:', tab.name);
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
    tab.term.clear();
    tab.term.writeln('\x1b[33m[重新连接中...]\x1b[0m\r\n');
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
      { label: '+ 本地终端', action: function () { createTab('local'); } },
      { label: '+ 远程终端', action: function () { _showSSHDialog(); } },
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
      savedHtml += '<div class="terminal-ssh-saved-title">已保存的连接</div>';
      for (var i = 0; i < _savedConnections.length; i++) {
        var conn = _savedConnections[i];
        savedHtml += '<div class="terminal-ssh-saved-item" data-idx="' + i + '">';
        savedHtml += '<div class="terminal-ssh-saved-item-info">';
        savedHtml += '<div class="terminal-ssh-saved-item-name">' + _escapeHtml(conn.name || conn.host) + '</div>';
        savedHtml += '<div class="terminal-ssh-saved-item-host">' + _escapeHtml(conn.username + '@' + conn.host + ':' + (conn.port || 22)) + '</div>';
        savedHtml += '</div>';
        savedHtml += '<span class="terminal-ssh-saved-item-del" data-idx="' + i + '">&times;</span>';
        savedHtml += '</div>';
      }
      savedHtml += '</div>';
    }

    overlay.innerHTML =
      '<div class="terminal-ssh-dialog">' +
      '<h3>SSH 远程终端</h3>' +
      '<p class="terminal-ssh-dialog-subtitle">通过 SSH 连接远程服务器</p>' +
      '<div class="terminal-ssh-field">' +
      '<label>快速连接</label>' +
      '<input type="text" id="sshQuickInput" placeholder="user@host:port 或 user:pass@host:port">' +
      '<div class="terminal-ssh-quick-hint">按回车解析，或在下方填写详细信息</div>' +
      '</div>' +
      '<div class="terminal-ssh-row">' +
      '<div class="terminal-ssh-field">' +
      '<label>主机地址</label>' +
      '<input type="text" id="sshHost" placeholder="192.168.1.1">' +
      '</div>' +
      '<div class="terminal-ssh-field" style="max-width:100px;">' +
      '<label>端口</label>' +
      '<input type="number" id="sshPort" value="22">' +
      '</div>' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label>用户名</label>' +
      '<input type="text" id="sshUsername" placeholder="root">' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label>密码</label>' +
      '<input type="password" id="sshPassword" placeholder="（留空则使用密钥认证）">' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label>私钥（可选）</label>' +
      '<textarea id="sshKey" placeholder="-----BEGIN OPENSSH PRIVATE KEY-----&#10;...&#10;-----END OPENSSH PRIVATE KEY-----"></textarea>' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label>连接名称（可选）</label>' +
      '<input type="text" id="sshName" placeholder="我的服务器">' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label style="display:flex;align-items:center;gap:6px;cursor:pointer;">' +
      '<input type="checkbox" id="sshSave" checked style="width:auto;"> 保存连接以便后续使用' +
      '</label>' +
      '</div>' +
      savedHtml +
      '<div class="terminal-ssh-actions">' +
      '<button class="terminal-ssh-btn-cancel" type="button" id="sshCancelBtn">取消</button>' +
      '<button class="terminal-ssh-btn-connect" type="button" id="sshConnectBtn">连接</button>' +
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

    // Saved connection click
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

    // Pattern: user:pass@host:port
    var match = input.match(/^([^:@]+):([^@]+)@([^:]+):(\d+)$/);
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
      if (typeof toast === 'function') toast('主机地址不能为空', 'error');
      return;
    }
    if (!username) {
      if (typeof toast === 'function') toast('用户名不能为空', 'error');
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
