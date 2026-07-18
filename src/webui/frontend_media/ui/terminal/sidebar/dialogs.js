/**
 * TerminalSidebar dialogs sub-module -- server add/edit dialog and command
 * add/edit dialog. Attaches openServerDialog/openCommandDialog onto the
 * shared ctx object used by sidebar.js.
 */
function _attachTerminalSidebarDialogs(ctx) {
  _attachTerminalSidebarDialogsSubServer(ctx);
  _attachTerminalSidebarDialogsSubCommand(ctx);
}

function _buildServerDialogHtml() {
  return (
    '<div class="terminal-ssh-dialog">' +
    '<h3>' + t('terminal.sidebarAddServer') + '</h3>' +
    '<div class="terminal-ssh-row">' +
    '<div class="terminal-ssh-field">' +
    '<label>' + t('terminal.hostAddress') + '</label>' +
    '<input type="text" id="sbHost" placeholder="192.168.1.1">' +
    '</div>' +
    '<div class="terminal-ssh-field" style="max-width:100px;">' +
    '<label>' + t('terminal.sshPort') + '</label>' +
    '<input type="number" id="sbPort" value="22">' +
    '</div>' +
    '</div>' +
    '<div class="terminal-ssh-field">' +
    '<label>' + t('terminal.sshUsername') + '</label>' +
    '<input type="text" id="sbUsername" placeholder="root">' +
    '</div>' +
    '<div class="terminal-ssh-field">' +
    '<label>' + t('terminal.sshPassword') + '</label>' +
    '<input type="password" id="sbPassword" placeholder="' + t('terminal.passwordKeyHint') + '">' +
    '</div>' +
    '<div class="terminal-ssh-field">' +
    '<label>' + t('terminal.privateKeyOptional') + '</label>' +
    '<textarea id="sbKey"></textarea>' +
    '</div>' +
    '<div class="terminal-ssh-field">' +
    '<label>' + t('terminal.connectionNameOptional') + '</label>' +
    '<input type="text" id="sbName" placeholder="' + t('terminal.myServer') + '">' +
    '</div>' +
    '<div class="terminal-ssh-actions">' +
    '<button class="terminal-ssh-btn-cancel" type="button" id="sbCancelBtn">' + t('common.cancel') + '</button>' +
    '<button class="terminal-ssh-btn-connect" type="button" id="sbSaveBtn">' + t('common.save') + '</button>' +
    '</div>' +
    '</div>'
  );
}

function _submitServerDialog(ctx, overlay, existingConn) {
  var host = overlay.querySelector('#sbHost').value.trim();
  var port = parseInt(overlay.querySelector('#sbPort').value, 10) || 22;
  var username = overlay.querySelector('#sbUsername').value.trim();
  var password = overlay.querySelector('#sbPassword').value;
  var keyData = overlay.querySelector('#sbKey').value.trim();
  var name = overlay.querySelector('#sbName').value.trim();

  if (!host || !username) {
    if (typeof toast === 'function') toast(t('terminal.hostRequired'), 'error');
    return;
  }

  var body = {
    host: host,
    port: port,
    username: username,
    password: password,
    key_data: keyData,
    name: name || (username + '@' + host),
  };
  if (existingConn) body.connection_id = existingConn.connection_id;

  fetch('/v1/webui/terminal/ssh-connections', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
    .then(function () {
      overlay.remove();
      ctx.renderServers();
    })
    .catch(function () {
      if (typeof toast === 'function') toast(t('toast.failed'), 'error');
    });
}

function _populateServerDialog(overlay, existingConn) {
  overlay.querySelector('#sbHost').value = existingConn.host || '';
  overlay.querySelector('#sbPort').value = existingConn.port || 22;
  overlay.querySelector('#sbUsername').value = existingConn.username || '';
  overlay.querySelector('#sbName').value = existingConn.name || '';
}

function _attachTerminalSidebarDialogsSubServer(ctx) {
  function openServerDialog(existingConn) {
    var overlay = document.createElement('div');
    overlay.className = 'terminal-ssh-dialog-overlay';
    overlay.innerHTML = _buildServerDialogHtml();

    document.body.appendChild(overlay);

    if (existingConn) _populateServerDialog(overlay, existingConn);

    overlay.querySelector('#sbCancelBtn').addEventListener('click', function () { overlay.remove(); });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#sbSaveBtn').addEventListener('click', function () {
      _submitServerDialog(ctx, overlay, existingConn);
    });
  }

  ctx.openServerDialog = openServerDialog;
}

function _buildCommandDialogHtml(isEdit) {
  var title = isEdit ? t('terminal.sidebarEditCommand') : t('terminal.sidebarAddCommand');
  return (
    '<div class="terminal-ssh-dialog">' +
    '<h3>' + title + '</h3>' +
    '<div class="terminal-ssh-field">' +
    '<label>' + t('terminal.sidebarCommandName') + '</label>' +
    '<input type="text" id="cmdName">' +
    '</div>' +
    '<div class="terminal-ssh-field">' +
    '<label>' + t('terminal.sidebarCommandContent') + '</label>' +
    '<textarea id="cmdText"></textarea>' +
    '</div>' +
    '<div class="terminal-ssh-field" style="flex-direction:row;align-items:center;gap:8px;">' +
    '<span class="terminal-toggle-switch" id="cmdAutoEnterToggle"><span class="knob"></span></span>' +
    '<span style="cursor:pointer;user-select:none;" id="cmdAutoEnterLabel">' + t('terminal.sidebarAutoEnter') + '</span>' +
    '</div>' +
    '<div class="terminal-ssh-actions">' +
    '<button class="terminal-ssh-btn-cancel" type="button" id="cmdCancelBtn">' + t('common.cancel') + '</button>' +
    '<button class="terminal-ssh-btn-connect" type="button" id="cmdSaveBtn">' + t('common.save') + '</button>' +
    '</div>' +
    '</div>'
  );
}

function _submitCommandDialog(ctx, overlay, existingCmd, autoEnter) {
  var name = overlay.querySelector('#cmdName').value.trim();
  var command = overlay.querySelector('#cmdText').value.trim();
  if (!command) {
    if (typeof toast === 'function') toast(t('toast.failed'), 'error');
    return;
  }

  var body = { name: name || command, command: command, auto_enter: !!autoEnter };
  if (existingCmd) body.command_id = existingCmd.id;

  fetch('/v1/webui/terminal/commands', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
    .then(function () {
      overlay.remove();
      ctx.renderCommands();
    })
    .catch(function () {
      if (typeof toast === 'function') toast(t('toast.failed'), 'error');
    });
}

function _attachTerminalSidebarDialogsSubCommand(ctx) {
  function openCommandDialog(existingCmd) {
    var overlay = document.createElement('div');
    overlay.className = 'terminal-ssh-dialog-overlay';
    overlay.innerHTML = _buildCommandDialogHtml(!!existingCmd);

    document.body.appendChild(overlay);

    var toggle = overlay.querySelector('#cmdAutoEnterToggle');
    var autoEnterValue = false;

    if (existingCmd) {
      overlay.querySelector('#cmdName').value = existingCmd.name || '';
      overlay.querySelector('#cmdText').value = existingCmd.command || '';
      autoEnterValue = !!existingCmd.auto_enter;
    }
    if (autoEnterValue) toggle.classList.add('on');

    toggle.addEventListener('click', function () {
      autoEnterValue = !autoEnterValue;
      toggle.classList.toggle('on', autoEnterValue);
    });
    overlay.querySelector('#cmdAutoEnterLabel').addEventListener('click', function () {
      autoEnterValue = !autoEnterValue;
      toggle.classList.toggle('on', autoEnterValue);
    });

    overlay.querySelector('#cmdCancelBtn').addEventListener('click', function () { overlay.remove(); });
    overlay.addEventListener('click', function (e) { if (e.target === overlay) overlay.remove(); });
    overlay.querySelector('#cmdSaveBtn').addEventListener('click', function () {
      _submitCommandDialog(ctx, overlay, existingCmd, autoEnterValue);
    });
  }

  ctx.openCommandDialog = openCommandDialog;
}

window._attachTerminalSidebarDialogs = _attachTerminalSidebarDialogs;
