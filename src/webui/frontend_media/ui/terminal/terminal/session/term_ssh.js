// ========================= Terminal: SSH Dialog =========================
// Split from terminal.js. Handles the SSH connect dialog, quick-connect
// parsing, saved connections persistence, and converting chooser/new tabs
// into SSH sessions.

function _attachSshMethods(ctx) {
  _attachSshEscapeMethods(ctx);
  _attachSshFormHtmlMethods(ctx);
  _attachSshDialogHtmlMethods(ctx);
  _attachSshSavedItemsMethods(ctx);
  _attachSshShowDialogMethods(ctx);
  _attachSshQuickConnectMethods(ctx);
  _attachSshConvertMethods(ctx);
  _attachSshDoConnectMethods(ctx);
  _attachSshPersistMethods(ctx);
}

function _attachSshEscapeMethods(ctx) {
  function _escapeHtml(text) {
    var d = document.createElement('div');
    d.textContent = String(text);
    return d.innerHTML;
  }

  function _buildSavedConnectionsHtml() {
    if (ctx.savedConnections.length === 0) return '';
    var savedHtml = '<div class="terminal-ssh-saved">';
    savedHtml += '<div class="terminal-ssh-saved-title">' + t('terminal.savedConnections') + '</div>';
    for (var i = 0; i < ctx.savedConnections.length; i++) {
      var conn = ctx.savedConnections[i];
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
    return savedHtml;
  }

  ctx.escapeHtml = _escapeHtml;
  ctx.buildSavedConnectionsHtml = _buildSavedConnectionsHtml;
}

function _attachSshFormHtmlMethods(ctx) {
  /**
   * Build the host/port/username/password/key/name/save form fields.
   */
  function _buildSshFormFieldsHtml() {
    return '<div class="terminal-ssh-row">' +
      '<div class="terminal-ssh-field">' +
      '<label>' + t('terminal.hostAddress') + '</label>' +
      '<input type="text" id="sshHost" placeholder="192.168.1.1">' +
      '</div>' +
      '<div class="terminal-ssh-field" style="max-width:100px;">' +
      '<label>' + t('terminal.sshPort') + '</label>' +
      '<input type="number" id="sshPort" value="22">' +
      '</div>' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label>' + t('terminal.sshUsername') + '</label>' +
      '<input type="text" id="sshUsername" placeholder="root">' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label>' + t('terminal.sshPassword') + '</label>' +
      '<input type="password" id="sshPassword" ' +
        'placeholder="' + t('terminal.passwordKeyHint') + '">' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label>' + t('terminal.privateKeyOptional') + '</label>' +
      '<textarea id="sshKey" placeholder="' +
        '-----BEGIN OPENSSH PRIVATE KEY-----&#10;...&#10;-----END OPENSSH PRIVATE KEY-----' +
      '"></textarea>' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label>' + t('terminal.connectionNameOptional') + '</label>' +
      '<input type="text" id="sshName" placeholder="' + t('terminal.myServer') + '">' +
      '</div>' +
      '<div class="terminal-ssh-field">' +
      '<label style="display:flex;align-items:center;gap:6px;cursor:pointer;">' +
      '<input type="checkbox" id="sshSave" checked style="width:auto;">' +
      ' ' + t('terminal.saveConnection') +
      '</label>' +
      '</div>';
  }

  ctx.buildSshFormFieldsHtml = _buildSshFormFieldsHtml;
}

function _attachSshDialogHtmlMethods(ctx) {
  /**
   * Build the full SSH dialog HTML: title, quick-connect input, form
   * fields, saved connections list, and action buttons.
   */
  function _buildSshDialogHtml(savedHtml) {
    return '<div class="terminal-ssh-dialog">' +
      '<h3>' + t('terminal.sshDialogTitle') + '</h3>' +
      '<p class="terminal-ssh-dialog-subtitle">' + t('terminal.sshDialogSubtitle') + '</p>' +
      '<div class="terminal-ssh-field">' +
      '<label>' + t('terminal.quickConnect') + '</label>' +
      '<input type="text" id="sshQuickInput" ' +
        'placeholder="' + t('terminal.quickConnectPlaceholder') + '">' +
      '<div class="terminal-ssh-quick-hint">' +
        t('terminal.quickConnectHint') + '</div>' +
      '</div>' +
      ctx.buildSshFormFieldsHtml() +
      savedHtml +
      '<div class="terminal-ssh-actions">' +
      '<button class="terminal-ssh-btn-cancel" type="button" id="sshCancelBtn">' +
        t('common.cancel') + '</button>' +
      '<button class="terminal-ssh-btn-connect" type="button" id="sshConnectBtn">' +
        t('terminal.sshConnect') + '</button>' +
      '</div>' +
      '</div>';
  }

  ctx.buildSshDialogHtml = _buildSshDialogHtml;
}

function _attachSshSavedItemsMethods(ctx) {
  /**
   * Wire up click/delete handlers for each saved-connection list item.
   */
  function _bindSavedConnectionItems(overlay, chooserTabId) {
    var savedItems = overlay.querySelectorAll('.terminal-ssh-saved-item');
    for (var i = 0; i < savedItems.length; i++) {
      (function (item) {
        var delBtn = item.querySelector('.terminal-ssh-saved-item-del');
        if (delBtn) {
          delBtn.addEventListener('click', function (e) {
            e.stopPropagation();
            var idx = parseInt(delBtn.dataset.idx, 10);
            ctx.savedConnections.splice(idx, 1);
            ctx.saveSavedConnections();
            overlay.remove();
            ctx.showSSHDialog(chooserTabId);
          });
        }
        item.addEventListener('click', function () {
          var idx = parseInt(item.dataset.idx, 10);
          var conn = ctx.savedConnections[idx];
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
              ctx.convertChooserTabToSSH(chooserTabId, opts);
            } else {
              ctx.createTab('ssh', opts);
            }
          }
        });
      })(savedItems[i]);
    }
  }

  ctx.bindSavedConnectionItems = _bindSavedConnectionItems;
}

function _attachSshShowDialogMethods(ctx) {
  function _showSSHDialog(chooserTabId) {
    var overlay = document.createElement('div');
    overlay.className = 'terminal-ssh-dialog-overlay';
    overlay.id = 'terminalSSHOverlay';

    var savedHtml = ctx.buildSavedConnectionsHtml();
    overlay.innerHTML = ctx.buildSshDialogHtml(savedHtml);

    document.body.appendChild(overlay);

    overlay.querySelector('#sshCancelBtn').addEventListener('click', function () {
      overlay.remove();
    });

    overlay.addEventListener('click', function (e) {
      if (e.target === overlay) overlay.remove();
    });

    overlay.querySelector('#sshConnectBtn').addEventListener('click', function () {
      ctx.doSSHConnect(overlay, chooserTabId);
    });

    var quickInput = overlay.querySelector('#sshQuickInput');
    quickInput.addEventListener('keydown', function (e) {
      if (e.key === 'Enter') {
        e.preventDefault();
        ctx.parseQuickConnect(quickInput.value, overlay);
      }
    });

    ctx.bindSavedConnectionItems(overlay, chooserTabId);
    quickInput.focus();
  }

  ctx.showSSHDialog = _showSSHDialog;
}

function _attachSshQuickConnectMethods(ctx) {
  /**
   * Parse a quick-connect string into the individual dialog fields.
   * Supports: user:pass@host:port, user@host:port, user@host, host:port, host.
   */
  function _parseQuickConnect(input, overlay) {
    if (!input || !input.trim()) return;
    input = input.trim();

    var match = input.match(/^([^:@]+):([^@]+)@([^:]+):(\d+)$/);
    if (match) {
      overlay.querySelector('#sshUsername').value = match[1];
      overlay.querySelector('#sshPassword').value = match[2];
      overlay.querySelector('#sshHost').value = match[3];
      overlay.querySelector('#sshPort').value = match[4];
      return;
    }

    match = input.match(/^([^@]+)@([^:]+):(\d+)$/);
    if (match) {
      overlay.querySelector('#sshUsername').value = match[1];
      overlay.querySelector('#sshHost').value = match[2];
      overlay.querySelector('#sshPort').value = match[3];
      return;
    }

    match = input.match(/^([^@]+)@(.+)$/);
    if (match) {
      overlay.querySelector('#sshUsername').value = match[1];
      overlay.querySelector('#sshHost').value = match[2];
      return;
    }

    match = input.match(/^([^:]+):(\d+)$/);
    if (match) {
      overlay.querySelector('#sshHost').value = match[1];
      overlay.querySelector('#sshPort').value = match[2];
      return;
    }

    overlay.querySelector('#sshHost').value = input;
  }

  ctx.parseQuickConnect = _parseQuickConnect;
}

function _attachSshConvertMethods(ctx) {
  /**
   * Convert a chooser tab into an SSH terminal tab.
   * Updates tab metadata, tab bar display, then initialises xterm.js + WS.
   */
  function _convertChooserTabToSSH(tabId, options) {
    var tab = ctx.getTabById(tabId);
    if (!tab || tab.kind !== 'chooser') {
      // Fallback: if tab no longer exists or isn't a chooser, create a new tab
      ctx.createTab('ssh', options);
      return;
    }

    ctx.tabCounter++;
    tab.kind = 'ssh';
    tab.name = options.name || t('terminal.remoteN', { index: ctx.tabCounter });
    tab.status = 'connecting';
    tab.options = options;

    if (ctx.bar) {
      ctx.bar.setTitle(tabId, tab.name);
      ctx.bar.setIcon(tabId, '');
      ctx.bar.setStatus(tabId, 'connecting');
    }

    // _initTerminal removes the old pane and creates a fresh xterm pane
    ctx.initTerminal(tab);
  }

  ctx.convertChooserTabToSSH = _convertChooserTabToSSH;
}

function _attachSshDoConnectMethods(ctx) {
  function _doSSHConnect(overlay, chooserTabId) {
    var host = overlay.querySelector('#sshHost').value.trim();
    var port = parseInt(overlay.querySelector('#sshPort').value, 10) || 22;
    var username = overlay.querySelector('#sshUsername').value.trim();
    var password = overlay.querySelector('#sshPassword').value;
    var keyData = overlay.querySelector('#sshKey').value.trim();
    var name = overlay.querySelector('#sshName').value.trim();
    var saveConn = overlay.querySelector('#sshSave').checked;

    if (!host) {
      if (typeof toast === 'function') toast(t('terminal.hostRequired'), 'error');
      return;
    }
    if (!username) {
      if (typeof toast === 'function') toast(t('terminal.usernameRequired'), 'error');
      return;
    }

    if (saveConn) {
      ctx.savedConnections.push({
        host: host, port: port, username: username, password: password,
        key_data: keyData, name: name || (username + '@' + host),
      });
      ctx.saveSavedConnections();
    }

    overlay.remove();

    var opts = {
      host: host, port: port, username: username, password: password,
      key_data: keyData, name: name || (username + '@' + host + ':' + port),
    };

    if (chooserTabId) {
      ctx.convertChooserTabToSSH(chooserTabId, opts);
    } else {
      ctx.createTab('ssh', opts);
    }
  }

  ctx.doSSHConnect = _doSSHConnect;
}

function _attachSshPersistMethods(ctx) {
  async function _loadSavedConnections() {
    try {
      if (typeof persistLoad === 'function') {
        var data = await persistLoad('terminals.json');
        if (data && data.connections) {
          ctx.savedConnections = data.connections;
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
        existing.connections = ctx.savedConnections;
        await persistSave('terminals.json', existing);
      }
    } catch (e) {
      // ignore
    }
  }

  ctx.loadSavedConnections = _loadSavedConnections;
  ctx.saveSavedConnections = _saveSavedConnections;
}
