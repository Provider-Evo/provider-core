/**
 * TerminalSidebar audit sub-module -- session recording audit log
 * (list/detail/delete + record toggle). Attaches renderAudit/paintAudit/
 * showAuditDetail/deleteAuditRecord onto the shared ctx object used by
 * sidebar.js.
 *
 * Helper builders are top-level functions (not nested closures) so each
 * stays independently under the line-length budget; ctx is threaded
 * through explicitly instead of being captured.
 */
function _renderAudit(ctx) {
  var panel = document.getElementById('terminalSidebarPanelAudit');
  if (!panel) return;

  Promise.all([
    fetch('/v1/webui/terminal/audit/config').then(function (r) { return r.json(); }).catch(function () { return {}; }),
    fetch('/v1/webui/terminal/audit?page=' + ctx.auditPage + '&page_size=' + ctx.auditPageSize)
      .then(function (r) { return r.json(); }).catch(function () { return {}; }),
  ]).then(function (results) {
    var config = results[0] || {};
    var listData = results[1] || {};
    ctx.auditEnabled = !!config.audit_enabled;
    ctx.auditTotal = listData.total || 0;
    _paintAudit(ctx, panel, listData.items || []);
  });
}

function _buildAuditToggleRow(ctx) {
  var toggleRow = document.createElement('div');
  toggleRow.className = 'terminal-sidebar-actions';
  var toggleLabel = document.createElement('span');
  toggleLabel.textContent = t('terminal.sidebarAuditRecording');
  toggleRow.appendChild(toggleLabel);

  var switchEl = document.createElement('div');
  switchEl.className = 'terminal-toggle-switch' + (ctx.auditEnabled ? ' on' : '');
  switchEl.innerHTML = '<div class="knob"></div>';
  switchEl.addEventListener('click', function () {
    var next = !ctx.auditEnabled;
    fetch('/v1/webui/terminal/audit/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ audit_enabled: next }),
    })
      .then(function () {
        ctx.auditEnabled = next;
        switchEl.classList.toggle('on', ctx.auditEnabled);
      })
      .catch(function () {
        if (typeof toast === 'function') toast(t('toast.failed'), 'error');
      });
  });
  toggleRow.appendChild(switchEl);
  return toggleRow;
}

function _buildAuditRow(ctx, rec) {
  var tr = document.createElement('tr');
  tr.className = 'terminal-sidebar-row';

  var tdHost = document.createElement('td');
  tdHost.textContent = (rec.host || '') + ' (' + (rec.kind || '') + ')';
  tr.appendChild(tdHost);

  var tdTime = document.createElement('td');
  tdTime.textContent = rec.login_time ? new Date(rec.login_time * 1000).toLocaleString() : '';
  tr.appendChild(tdTime);

  var tdActions = document.createElement('td');
  var delBtn = document.createElement('button');
  delBtn.type = 'button';
  delBtn.className = 'terminal-sidebar-btn-ghost';
  delBtn.textContent = t('terminal.sidebarDelete');
  delBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    _deleteAuditRecord(ctx, rec.session_id);
  });
  tdActions.appendChild(delBtn);
  tr.appendChild(tdActions);

  tr.addEventListener('click', function () { _showAuditDetail(ctx, rec.session_id); });

  return tr;
}

function _buildAuditTable(ctx, items) {
  var table = document.createElement('table');
  table.className = 'terminal-sidebar-table';
  table.innerHTML =
    '<thead><tr>' +
    '<th>' + t('terminal.sshHost') + '</th>' +
    '<th>' + t('terminal.sidebarLoginTime') + '</th>' +
    '<th>' + t('terminal.sidebarActions') + '</th>' +
    '</tr></thead>';

  var tbody = document.createElement('tbody');
  for (var i = 0; i < items.length; i++) {
    tbody.appendChild(_buildAuditRow(ctx, items[i]));
  }
  table.appendChild(tbody);
  return table;
}

function _buildAuditPagination(ctx) {
  var totalPages = Math.max(1, Math.ceil(ctx.auditTotal / ctx.auditPageSize));
  var pagination = document.createElement('div');
  pagination.className = 'terminal-sidebar-pagination';

  var prevBtn = document.createElement('button');
  prevBtn.type = 'button';
  prevBtn.textContent = t('terminal.sidebarPrevPage');
  prevBtn.disabled = ctx.auditPage <= 1;
  prevBtn.addEventListener('click', function () {
    if (ctx.auditPage > 1) { ctx.auditPage--; _renderAudit(ctx); }
  });
  pagination.appendChild(prevBtn);

  var pageLabel = document.createElement('span');
  pageLabel.textContent = t('terminal.sidebarPageOf', { page: ctx.auditPage });
  pagination.appendChild(pageLabel);

  var nextBtn = document.createElement('button');
  nextBtn.type = 'button';
  nextBtn.textContent = t('terminal.sidebarNextPage');
  nextBtn.disabled = ctx.auditPage >= totalPages;
  nextBtn.addEventListener('click', function () {
    if (ctx.auditPage < totalPages) { ctx.auditPage++; _renderAudit(ctx); }
  });
  pagination.appendChild(nextBtn);

  return pagination;
}

function _paintAudit(ctx, panel, items) {
  panel.innerHTML = '';
  panel.appendChild(_buildAuditToggleRow(ctx));

  if (!items || items.length === 0) {
    var empty = document.createElement('div');
    empty.className = 'terminal-empty-state';
    empty.innerHTML = '<div class="terminal-empty-state-text">' + t('terminal.sidebarCommandEmpty') + '</div>';
    panel.appendChild(empty);
    return;
  }

  panel.appendChild(_buildAuditTable(ctx, items));
  panel.appendChild(_buildAuditPagination(ctx));
}

function _buildAuditDetailDialog(ctx, rec) {
  var overlay = document.createElement('div');
  overlay.className = 'terminal-ssh-dialog-overlay';
  var d = document.createElement('div');
  d.className = 'terminal-ssh-dialog';

  var title = document.createElement('h3');
  title.textContent = t('terminal.sidebarDetail');
  d.appendChild(title);

  var info = document.createElement('div');
  info.textContent =
    (rec.host || '') + ' | ' + (rec.kind || '') + ' | ' +
    (rec.login_time ? new Date(rec.login_time * 1000).toLocaleString() : '') + ' | ' +
    (rec.status || '');
  d.appendChild(info);

  var pre = document.createElement('pre');
  pre.style.maxHeight = '300px';
  pre.style.overflow = 'auto';
  pre.textContent = ctx.stripAnsiSequences(rec.output || '');
  d.appendChild(pre);

  var actions = document.createElement('div');
  actions.className = 'terminal-ssh-actions';
  var closeBtn = document.createElement('button');
  closeBtn.type = 'button';
  closeBtn.className = 'terminal-ssh-btn-cancel';
  closeBtn.textContent = t('common.cancel');
  closeBtn.addEventListener('click', function () { overlay.remove(); });
  actions.appendChild(closeBtn);
  d.appendChild(actions);

  overlay.appendChild(d);
  overlay.addEventListener('click', function (e) { if (e.target === overlay) overlay.remove(); });
  return overlay;
}

function _showAuditDetail(ctx, sessionId) {
  fetch('/v1/webui/terminal/audit/' + encodeURIComponent(sessionId))
    .then(function (r) { return r.json(); })
    .then(function (rec) {
      document.body.appendChild(_buildAuditDetailDialog(ctx, rec));
    })
    .catch(function () {
      if (typeof toast === 'function') toast(t('toast.failed'), 'error');
    });
}

function _deleteAuditRecord(ctx, sessionId) {
  showConfirmDialog(t('terminal.sidebarConfirmDeleteAudit'), {
    title: t('terminal.sidebarDelete'),
    confirmText: t('terminal.sidebarDelete'),
    cancelText: t('common.cancel'),
  }).then(function (confirmed) {
    if (!confirmed) return;
    fetch('/v1/webui/terminal/audit/' + encodeURIComponent(sessionId), { method: 'DELETE' })
      .then(function () { _renderAudit(ctx); })
      .catch(function () {
        if (typeof toast === 'function') toast(t('toast.failed'), 'error');
      });
  });
}

function _attachTerminalSidebarAudit(ctx) {
  ctx.renderAudit = function () { _renderAudit(ctx); };
  ctx.paintAudit = function (panel, items) { _paintAudit(ctx, panel, items); };
  ctx.showAuditDetail = function (sessionId) { _showAuditDetail(ctx, sessionId); };
  ctx.deleteAuditRecord = function (sessionId) { _deleteAuditRecord(ctx, sessionId); };
}

window._attachTerminalSidebarAudit = _attachTerminalSidebarAudit;
