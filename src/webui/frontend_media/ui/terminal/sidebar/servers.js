/**
 * TerminalSidebar servers sub-module -- saved SSH connections list (CRUD + connect).
 * Attaches renderServers/paintServers/connectServer/deleteServer/batchDeleteServers
 * onto the shared ctx object used by sidebar.js.
 */
function _attachTerminalSidebarServers(ctx) {
  ctx.renderServers = function () { _tsServersRender(ctx); };
  ctx.paintServers = function (panel) { _tsServersPaint(ctx, panel); };
  ctx.connectServer = function (conn) { _tsServersConnect(conn); };
  ctx.deleteServer = function (connectionId) { _tsServersDelete(ctx, connectionId); };
  ctx.batchDeleteServers = function (ids) { _tsServersBatchDelete(ctx, ids); };
}

function _tsServersRender(ctx) {
  var panel = document.getElementById('terminalSidebarPanelServers');
  if (!panel) return;

  fetch('/v1/webui/terminal/ssh-connections')
    .then(function (resp) { return resp.json(); })
    .then(function (data) {
      ctx.servers = (data && data.connections) || [];
      _tsServersPaint(ctx, panel);
    })
    .catch(function () {
      ctx.servers = [];
      _tsServersPaint(ctx, panel);
    });
}

function _tsServersBuildActionsBar(ctx, panel) {
  var actions = document.createElement('div');
  actions.className = 'terminal-sidebar-actions';

  var addBtn = document.createElement('button');
  addBtn.type = 'button';
  addBtn.textContent = t('terminal.sidebarAddServer');
  addBtn.addEventListener('click', function () { ctx.openServerDialog(null); });
  actions.appendChild(addBtn);

  var batchBtn = document.createElement('button');
  batchBtn.type = 'button';
  batchBtn.className = 'terminal-sidebar-btn-ghost';
  batchBtn.textContent = t('terminal.sidebarBatchDelete');
  batchBtn.addEventListener('click', function () {
    var checked = panel.querySelectorAll('.server-row-check:checked');
    var ids = [];
    for (var i = 0; i < checked.length; i++) ids.push(checked[i].getAttribute('data-id'));
    if (ids.length > 0) _tsServersBatchDelete(ctx, ids);
  });
  actions.appendChild(batchBtn);

  return actions;
}

function _tsServersBuildRow(ctx, conn) {
  var tr = document.createElement('tr');
  tr.className = 'terminal-sidebar-row';

  var tdCheck = document.createElement('td');
  var check = document.createElement('input');
  check.type = 'checkbox';
  check.className = 'server-row-check';
  check.setAttribute('data-id', conn.connection_id);
  check.addEventListener('click', function (e) { e.stopPropagation(); });
  tdCheck.appendChild(check);
  tr.appendChild(tdCheck);

  var tdInfo = document.createElement('td');
  var nameLabel = conn.name || conn.host;
  tdInfo.textContent = nameLabel + ' (' + conn.username + '@' + conn.host + ':' + (conn.port || 22) + ')';
  tr.appendChild(tdInfo);

  var tdActions = document.createElement('td');

  var editBtn = document.createElement('button');
  editBtn.type = 'button';
  editBtn.className = 'terminal-sidebar-btn-ghost';
  editBtn.textContent = t('terminal.sidebarEdit');
  editBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    ctx.openServerDialog(conn);
  });
  tdActions.appendChild(editBtn);

  var delBtn = document.createElement('button');
  delBtn.type = 'button';
  delBtn.className = 'terminal-sidebar-btn-ghost';
  delBtn.textContent = t('terminal.sidebarDelete');
  delBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    _tsServersDelete(ctx, conn.connection_id);
  });
  tdActions.appendChild(delBtn);

  tr.appendChild(tdActions);

  tr.addEventListener('click', function () { _tsServersConnect(conn); });

  return tr;
}

function _tsServersBuildTable(ctx, panel) {
  var table = document.createElement('table');
  table.className = 'terminal-sidebar-table';

  var thead = document.createElement('thead');
  thead.innerHTML =
    '<tr>' +
    '<th><input type="checkbox" id="serverSelectAll"></th>' +
    '<th>' + t('terminal.sidebarHost') + '</th>' +
    '<th>' + t('terminal.sidebarActions') + '</th>' +
    '</tr>';
  table.appendChild(thead);

  var tbody = document.createElement('tbody');
  for (var i = 0; i < ctx.servers.length; i++) {
    tbody.appendChild(_tsServersBuildRow(ctx, ctx.servers[i]));
  }
  table.appendChild(tbody);
  panel.appendChild(table);

  var selectAll = panel.querySelector('#serverSelectAll');
  if (selectAll) {
    selectAll.addEventListener('click', function () {
      var checks = panel.querySelectorAll('.server-row-check');
      for (var k = 0; k < checks.length; k++) checks[k].checked = selectAll.checked;
    });
  }
}

function _tsServersPaint(ctx, panel) {
  panel.innerHTML = '';
  panel.appendChild(_tsServersBuildActionsBar(ctx, panel));

  if (ctx.servers.length === 0) {
    var empty = document.createElement('div');
    empty.className = 'terminal-empty-state';
    empty.innerHTML = '<div class="terminal-empty-state-text">' + t('terminal.sidebarCommandEmpty') + '</div>';
    panel.appendChild(empty);
    return;
  }

  _tsServersBuildTable(ctx, panel);
}

function _tsServersConnect(conn) {
  if (typeof TerminalManager === 'undefined' || typeof TerminalManager.createTab !== 'function') return;
  var opts = {
    connection_id: conn.connection_id,
    name: conn.name || (conn.username + '@' + conn.host),
    host: conn.host,
    port: conn.port,
    username: conn.username,
  };
  var activeTab = typeof TerminalManager.getActiveTab === 'function' ? TerminalManager.getActiveTab() : null;
  if (activeTab && activeTab.kind === 'chooser' && typeof TerminalManager.convertChooserTabToSSH === 'function') {
    TerminalManager.convertChooserTabToSSH(activeTab.id, opts);
  } else {
    TerminalManager.createTab('ssh', opts);
  }
}

function _tsServersDelete(ctx, connectionId) {
  showConfirmDialog(t('terminal.sidebarConfirmDeleteServer'), {
    title: t('terminal.sidebarDelete'),
    confirmText: t('terminal.sidebarDelete'),
    cancelText: t('common.cancel'),
  }).then(function (confirmed) {
    if (!confirmed) return;
    fetch('/v1/webui/terminal/ssh-connections/' + encodeURIComponent(connectionId), { method: 'DELETE' })
      .then(function () { _tsServersRender(ctx); })
      .catch(function () {
        if (typeof toast === 'function') toast(t('toast.failed'), 'error');
      });
  });
}

function _tsServersBatchDelete(ctx, ids) {
  showConfirmDialog(t('terminal.sidebarConfirmDeleteServer'), {
    title: t('terminal.sidebarBatchDelete'),
    confirmText: t('terminal.sidebarBatchDelete'),
    cancelText: t('common.cancel'),
  }).then(function (confirmed) {
    if (!confirmed) return;
    var chain = Promise.resolve();
    for (var i = 0; i < ids.length; i++) {
      (function (id) {
        chain = chain.then(function () {
          return fetch('/v1/webui/terminal/ssh-connections/' + encodeURIComponent(id), { method: 'DELETE' });
        });
      })(ids[i]);
    }
    chain.then(function () { _tsServersRender(ctx); }).catch(function () {
      if (typeof toast === 'function') toast(t('toast.failed'), 'error');
    });
  });
}

window._attachTerminalSidebarServers = _attachTerminalSidebarServers;
