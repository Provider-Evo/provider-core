/**
 * TerminalSidebar commands sub-module -- quick command list (CRUD +
 * import/export + send-to-terminal). Attaches renderCommands/paintCommands/
 * deleteCommand/exportCommands/importCommands onto the shared ctx object
 * used by sidebar.js.
 *
 * Helper builders are top-level functions (not nested closures) so each
 * stays independently under the line-length budget; ctx is threaded
 * through explicitly instead of being captured.
 */
function _renderCommands(ctx) {
  var panel = document.getElementById('terminalSidebarPanelCommands');
  if (!panel) return;

  fetch('/v1/webui/terminal/commands')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      ctx.commands = (data && data.commands) || [];
      _paintCommands(ctx, panel);
    })
    .catch(function () {
      ctx.commands = [];
      _paintCommands(ctx, panel);
    });
}

function _buildCommandsActionsBar(ctx) {
  var actions = document.createElement('div');
  actions.className = 'terminal-sidebar-actions';

  var addBtn = document.createElement('button');
  addBtn.type = 'button';
  addBtn.textContent = t('terminal.sidebarAddCommand');
  addBtn.addEventListener('click', function () { ctx.openCommandDialog(null); });
  actions.appendChild(addBtn);

  var exportBtn = document.createElement('button');
  exportBtn.type = 'button';
  exportBtn.className = 'terminal-sidebar-btn-ghost';
  exportBtn.textContent = t('terminal.sidebarExport');
  exportBtn.addEventListener('click', function () { _exportCommands(); });
  actions.appendChild(exportBtn);

  var importBtn = document.createElement('button');
  importBtn.type = 'button';
  importBtn.className = 'terminal-sidebar-btn-ghost';
  importBtn.textContent = t('terminal.sidebarImport');
  importBtn.addEventListener('click', function () { _importCommands(ctx); });
  actions.appendChild(importBtn);

  return actions;
}

function _buildCommandRow(ctx, cmd) {
  var tr = document.createElement('tr');
  tr.className = 'terminal-sidebar-row';

  var tdName = document.createElement('td');
  tdName.textContent = cmd.name || cmd.command;
  tr.appendChild(tdName);

  var tdActions = document.createElement('td');

  var editBtn = document.createElement('button');
  editBtn.type = 'button';
  editBtn.className = 'terminal-sidebar-btn-ghost';
  editBtn.textContent = t('terminal.sidebarEdit');
  editBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    ctx.openCommandDialog(cmd);
  });
  tdActions.appendChild(editBtn);

  var delBtn = document.createElement('button');
  delBtn.type = 'button';
  delBtn.className = 'terminal-sidebar-btn-ghost';
  delBtn.textContent = t('terminal.sidebarDelete');
  delBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    _deleteCommand(ctx, cmd.id);
  });
  tdActions.appendChild(delBtn);

  tr.appendChild(tdActions);

  tr.addEventListener('click', function () { _sendCommandToActiveTab(cmd.command, cmd.auto_enter); });

  return tr;
}

function _buildCommandsTable(ctx) {
  var table = document.createElement('table');
  table.className = 'terminal-sidebar-table';
  table.innerHTML =
    '<thead><tr>' +
    '<th>' + t('terminal.sidebarCommandName') + '</th>' +
    '<th>' + t('terminal.sidebarActions') + '</th>' +
    '</tr></thead>';

  var tbody = document.createElement('tbody');
  for (var i = 0; i < ctx.commands.length; i++) {
    tbody.appendChild(_buildCommandRow(ctx, ctx.commands[i]));
  }
  table.appendChild(tbody);
  return table;
}

function _paintCommands(ctx, panel) {
  panel.innerHTML = '';
  panel.appendChild(_buildCommandsActionsBar(ctx));

  if (ctx.commands.length === 0) {
    var empty = document.createElement('div');
    empty.className = 'terminal-empty-state';
    empty.innerHTML = '<div class="terminal-empty-state-text">' + t('terminal.sidebarCommandEmpty') + '</div>';
    panel.appendChild(empty);
    return;
  }

  panel.appendChild(_buildCommandsTable(ctx));
}

function _sendCommandToActiveTab(commandText, autoEnter) {
  if (typeof TerminalManager === 'undefined' || typeof TerminalManager.sendToActiveTab !== 'function') return;
  var text = autoEnter ? commandText + '\n' : commandText;
  if (!TerminalManager.sendToActiveTab(text)) {
    if (typeof toast === 'function') toast(t('terminal.noActiveTab'), 'error');
  }
}

function _deleteCommand(ctx, id) {
  showConfirmDialog(t('terminal.sidebarConfirmDeleteCommand'), {
    title: t('terminal.sidebarDelete'),
    confirmText: t('terminal.sidebarDelete'),
    cancelText: t('common.cancel'),
  }).then(function (confirmed) {
    if (!confirmed) return;
    fetch('/v1/webui/terminal/commands/' + encodeURIComponent(id), { method: 'DELETE' })
      .then(function () { _renderCommands(ctx); })
      .catch(function () {
        if (typeof toast === 'function') toast(t('toast.failed'), 'error');
      });
  });
}

function _exportCommands() {
  fetch('/v1/webui/terminal/commands/export')
    .then(function (r) { return r.json(); })
    .then(function (data) {
      var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url;
      a.download = 'terminal-commands.json';
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    })
    .catch(function () {
      if (typeof toast === 'function') toast(t('toast.failed'), 'error');
    });
}

function _handleImportFileRead(ctx, input, reader) {
  var parsed;
  try {
    parsed = JSON.parse(reader.result);
  } catch (err) {
    if (typeof toast === 'function') toast(t('toast.failed'), 'error');
    document.body.removeChild(input);
    return;
  }
  fetch('/v1/webui/terminal/commands/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(parsed),
  })
    .then(function () { _renderCommands(ctx); })
    .catch(function () {
      if (typeof toast === 'function') toast(t('toast.failed'), 'error');
    })
    .then(function () { document.body.removeChild(input); });
}

function _importCommands(ctx) {
  var input = document.createElement('input');
  input.type = 'file';
  input.accept = 'application/json';
  input.style.display = 'none';
  input.addEventListener('change', function (e) {
    if (!e.target.files || !e.target.files[0]) {
      document.body.removeChild(input);
      return;
    }
    var file = e.target.files[0];
    var reader = new FileReader();
    reader.onload = function () { _handleImportFileRead(ctx, input, reader); };
    reader.readAsText(file);
  });
  document.body.appendChild(input);
  input.click();
}

function _attachTerminalSidebarCommands(ctx) {
  ctx.renderCommands = function () { _renderCommands(ctx); };
  ctx.paintCommands = function (panel) { _paintCommands(ctx, panel); };
  ctx.sendCommandToActiveTab = _sendCommandToActiveTab;
  ctx.deleteCommand = function (id) { _deleteCommand(ctx, id); };
  ctx.exportCommands = _exportCommands;
  ctx.importCommands = function () { _importCommands(ctx); };
}

window._attachTerminalSidebarCommands = _attachTerminalSidebarCommands;
