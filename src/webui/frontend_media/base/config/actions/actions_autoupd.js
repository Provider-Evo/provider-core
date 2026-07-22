function syncAutoupdateStatusFromConfig() {
  var el = document.getElementById('autoupdateStatus');
  if (!el || !window._currentConfig) return;
  var au = window._currentConfig.autoupdate || {};
  if (typeof t !== 'function') {
    el.textContent = au.enabled ? 'enabled' : 'disabled';
    return;
  }
  el.textContent = au.enabled ? t('autoupdate.statusEnabled') : t('autoupdate.statusDisabled');
}

var _mirrorList = null;

function _syncAutoupdateMirrorsToConfig(mirrors) {
  if (!window._currentConfig) return;
  if (!window._currentConfig.autoupdate) window._currentConfig.autoupdate = {};
  window._currentConfig.autoupdate.mirrors = mirrors;
  if (typeof scheduleConfigSave === 'function') scheduleConfigSave();
  syncAutoupdateStatusFromConfig();
}

function _renderAutoupdateMirrors(mirrors) {
  var list = document.getElementById('autoupdateMirrorsList');
  if (!list) return;
  _mirrorList = null;
  if (typeof SortableList === 'undefined') {
    list.innerHTML = '<div class="sl-empty">' + escapeHtml(typeof t === 'function' ? t('common.loading') : '') + '</div>';
    return;
  }
  _mirrorList = new SortableList(list, {
    renderItem: function(value) {
      var safe = String(value || '').replace(/&/g, '&amp;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
      return '<input type="text" class="config-input mirror-url" value="' + safe + '" style="width:100%;">';
    },
    getItemValue: function(el) {
      var inp = el.querySelector('.mirror-url');
      return inp ? inp.value.trim() : '';
    },
    onChange: function(items) {
      _syncAutoupdateMirrorsToConfig(items);
    },
    placeholder: typeof t === 'function' ? t('autoupdate.noMirrors') : '',
  });
  _mirrorList.setItems(mirrors || []);
}

function _getMirrorsFromUI() {
  if (_mirrorList) return _mirrorList.getItems().filter(function(v) { return v; });
  var inputs = document.querySelectorAll('#autoupdateMirrorsList .mirror-url');
  var arr = [];
  inputs.forEach(function(inp) { if (inp.value.trim()) arr.push(inp.value.trim()); });
  return arr;
}

window._renderAutoupdateMirrors = _renderAutoupdateMirrors;
window._getMirrorsFromUI = _getMirrorsFromUI;
window._syncAutoupdateMirrorsToConfig = _syncAutoupdateMirrorsToConfig;

async function loadAutoupdateLastCheck() {
  try {
    const result = await fetchJson('/v1/admin/autoupdate');
    if (result.success && result.data && result.data.last_check && result.data.last_check.status) {
      _showCheckResults(result.data.last_check);
    }
  } catch (error) {
    /* optional: last check unavailable */
  }
}

function _showCheckResultsError(d, statusEl, metaEl, filesEl) {
  statusEl.textContent = '[error]';
  statusEl.style.color = 'var(--err)';
  metaEl.textContent = d.message || t('autoupdate.checkFailed');
  filesEl.innerHTML = '';
}

function _showCheckResultsUpToDate(d, statusEl, metaEl, filesEl) {
  statusEl.textContent = t('autoupdate.upToDate');
  statusEl.style.color = 'var(--ok)';
  metaEl.textContent = (d.local_hash || '') + ' = ' + (d.remote_hash || '') + ' (mirror: ' + (d.mirror || '') + ')';
  filesEl.innerHTML = '';
}

function _bindAutoupdateFileEvents(filesEl, files) {
  filesEl.querySelectorAll('.autoupdate-file-link').forEach(function(link) {
    link.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      _showFileDiff(link.dataset.file);
    });
  });
  filesEl.querySelectorAll('.autoupdate-file-check').forEach(function(cb) {
    cb.addEventListener('change', function() { _updateAutoupdateSelectedCount(filesEl); });
  });
}

function _updateAutoupdateSelectedCount(filesEl) {
  var selectedCount = document.getElementById('autoupdateSelectedCount');
  var checked = filesEl.querySelectorAll('.autoupdate-file-check:checked').length;
  var total = filesEl.querySelectorAll('.autoupdate-file-check').length;
  if (selectedCount) selectedCount.textContent = t('autoupdate.selectedCount', { checked: checked, total: total });
}

function _renderAutoupdateFileList(filesEl, files, filter) {
  var filtered = filter ? files.filter(function(f) { return f.toLowerCase().indexOf(filter) !== -1; }) : files;
  var html = filtered.map(function(f) {
    return '<label class="flex items-center gap-2" style="padding:2px 0;cursor:pointer;">'
      + '<input type="checkbox" class="autoupdate-file-check" value="' + escapeHtml(f) + '" checked>'
      + '<span class="text-[12px] font-mono autoupdate-file-link" data-file="' + escapeHtml(f) + '" style="color:var(--accent);cursor:pointer;text-decoration:underline;" title="' + escapeHtml(t('autoupdate.viewDiff')) + '">' + escapeHtml(f) + '</span>'
      + '</label>';
  }).join('');
  filesEl.innerHTML = html || '<div class="text-muted" style="padding:8px;">' + escapeHtml(t('autoupdate.noMatchingFiles')) + '</div>';
  _bindAutoupdateFileEvents(filesEl, files);
  _updateAutoupdateSelectedCount(filesEl);
}

function _bindAutoupdateToolbar(filesEl, files, searchInput) {
  if (searchInput) {
    searchInput.oninput = function() {
      _renderAutoupdateFileList(filesEl, files, searchInput.value.toLowerCase());
    };
  }

  var selectAllBtn = document.getElementById('autoupdateSelectAllBtn');
  var selectNoneBtn = document.getElementById('autoupdateSelectNoneBtn');
  if (selectAllBtn) {
    selectAllBtn.onclick = function() {
      filesEl.querySelectorAll('.autoupdate-file-check').forEach(function(cb) { cb.checked = true; });
      _updateAutoupdateSelectedCount(filesEl);
    };
  }
  if (selectNoneBtn) {
    selectNoneBtn.onclick = function() {
      filesEl.querySelectorAll('.autoupdate-file-check').forEach(function(cb) { cb.checked = false; });
      _updateAutoupdateSelectedCount(filesEl);
    };
  }

  var confirmBtn = document.getElementById('autoupdateConfirmBtn');
  if (confirmBtn) {
    confirmBtn.onclick = function() { applyAutoupdate(); };
  }

  var cancelBtn = document.getElementById('autoupdateCancelBtn');
  var applyBtn = document.getElementById('autoupdateApplyBtn');
  if (cancelBtn) {
    cancelBtn.onclick = function() {
      var panel = document.getElementById('autoupdateResults');
      if (panel) panel.classList.add('hidden');
      if (applyBtn) applyBtn.classList.add('hidden');
    };
  }
}

function _showCheckResultsHasUpdate(d, statusEl, metaEl, filesEl, searchInput, actionBtns) {
  var files = d.changed_files || [];
  statusEl.textContent = t('autoupdate.filesChanged', { count: files.length });
  statusEl.style.color = 'var(--warn)';
  metaEl.textContent = (d.local_hash || '?') + ' -> ' + (d.remote_hash || '?') + ' (mirror: ' + (d.mirror || '') + ')';

  if (searchInput) {
    searchInput.style.display = files.length > 5 ? '' : 'none';
    searchInput.value = '';
  }

  if (actionBtns) actionBtns.style.display = '';

  _bindAutoupdateToolbar(filesEl, files, searchInput);
  _renderAutoupdateFileList(filesEl, files, '');
}

function _showCheckResults(d) {
  var panel = document.getElementById('autoupdateResults');
  var statusEl = document.getElementById('autoupdateResultStatus');
  var metaEl = document.getElementById('autoupdateResultMeta');
  var filesEl = document.getElementById('autoupdateChangedFiles');
  var actionBtns = document.getElementById('autoupdateActionBtns');
  var searchInput = document.getElementById('autoupdateSearchInput');
  var applyBtn = document.getElementById('autoupdateApplyBtn');
  if (!panel) return;
  panel.classList.remove('hidden');

  if (actionBtns) actionBtns.style.display = 'none';
  if (searchInput) searchInput.style.display = 'none';
  if (applyBtn) applyBtn.classList.add('hidden');

  if (d.status === 'error') {
    _showCheckResultsError(d, statusEl, metaEl, filesEl);
    return;
  }

  if (!d.has_update) {
    _showCheckResultsUpToDate(d, statusEl, metaEl, filesEl);
    return;
  }

  _showCheckResultsHasUpdate(d, statusEl, metaEl, filesEl, searchInput, actionBtns);
}

function _ensureAutoupdateDiffOverlay() {
  var overlay = document.getElementById('autoupdateDiffOverlay');
  if (overlay) return overlay;
  overlay = document.createElement('div');
  overlay.id = 'autoupdateDiffOverlay';
  overlay.style.cssText = 'position:fixed;inset:0;z-index:99999;background:rgba(0,0,0,0.5);display:flex;align-items:center;justify-content:center;padding:16px;';
  overlay.innerHTML = '<div style="background:var(--panel);border:1px solid var(--border);border-radius:16px;max-width:1200px;width:100%;max-height:85vh;display:flex;flex-direction:column;overflow:hidden;padding:16px;">'
    + '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
    + '<strong id="autoupdateDiffTitle" style="font-size:14px;font-family:monospace;"></strong>'
    + '<button id="autoupdateDiffClose" type="button" style="cursor:pointer;font-size:20px;border:none;background:none;color:var(--text);">&times;</button>'
    + '</div>'
    + '<div id="autoupdateDiffContent" style="flex:1;overflow:auto;display:grid;grid-template-columns:1fr 1fr;gap:8px;">'
    + '<div id="diffLeft" style="overflow:auto;font-size:12px;line-height:1.5;padding:12px;background:var(--panel-alt);border:1px solid var(--border);border-radius:8px;white-space:pre-wrap;word-break:break-all;font-family:monospace;"><div style="font-size:11px;color:var(--muted);margin-bottom:8px;font-weight:600;">' + escapeHtml(t('autoupdate.diffOld')) + '</div><pre id="diffLeftPre" style="margin:0;white-space:pre-wrap;"></pre></div>'
    + '<div id="diffRight" style="overflow:auto;font-size:12px;line-height:1.5;padding:12px;background:var(--panel-alt);border:1px solid var(--border);border-radius:8px;white-space:pre-wrap;word-break:break-all;font-family:monospace;"><div style="font-size:11px;color:var(--muted);margin-bottom:8px;font-weight:600;">' + escapeHtml(t('autoupdate.diffNew')) + '</div><pre id="diffRightPre" style="margin:0;white-space:pre-wrap;"></pre></div>'
    + '</div>'
    + '</div>';
  document.body.appendChild(overlay);
  overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.style.display = 'none'; });
  document.getElementById('autoupdateDiffClose').addEventListener('click', function() { overlay.style.display = 'none'; });
  return overlay;
}

function _renderDiffLine(line, leftHtml, rightHtml) {
  if (line.startsWith('+++') || line.startsWith('---')) {
    leftHtml.push('<span style="color:var(--muted);">' + escapeHtml(line) + '</span>');
    rightHtml.push('<span style="color:var(--muted);">' + escapeHtml(line) + '</span>');
  } else if (line.startsWith('@@')) {
    leftHtml.push('<span style="color:var(--accent);">' + escapeHtml(line) + '</span>');
    rightHtml.push('<span style="color:var(--accent);">' + escapeHtml(line) + '</span>');
  } else if (line.startsWith('-')) {
    leftHtml.push('<span style="color:var(--err);background:rgba(217,72,72,0.1);display:block;padding:0 4px;margin:0 -4px;">' + escapeHtml(line) + '</span>');
    rightHtml.push('<span style="display:block;min-height:1.5em;">&nbsp;</span>');
  } else if (line.startsWith('+')) {
    leftHtml.push('<span style="display:block;min-height:1.5em;">&nbsp;</span>');
    rightHtml.push('<span style="color:var(--ok);background:rgba(31,157,97,0.1);display:block;padding:0 4px;margin:0 -4px;">' + escapeHtml(line) + '</span>');
  } else {
    leftHtml.push(escapeHtml(line));
    rightHtml.push(escapeHtml(line));
  }
}

function _bindDiffScrollSync() {
  var diffLeft = document.getElementById('diffLeft');
  var diffRight = document.getElementById('diffRight');
  var syncing = false;
  diffLeft.onscroll = function() {
    if (syncing) return;
    syncing = true;
    diffRight.scrollTop = diffLeft.scrollTop;
    syncing = false;
  };
  diffRight.onscroll = function() {
    if (syncing) return;
    syncing = true;
    diffLeft.scrollTop = diffRight.scrollTop;
    syncing = false;
  };
}

function _renderFileDiffResult(data) {
  var leftPre = document.getElementById('diffLeftPre');
  var rightPre = document.getElementById('diffRightPre');
  if (!data.success) {
    leftPre.textContent = 'Error: ' + (data.error || 'unknown');
    rightPre.textContent = '';
    return;
  }
  var lines = (data.diff || '(no changes)').split('\n');
  var leftHtml = [];
  var rightHtml = [];
  for (var i = 0; i < lines.length; i++) {
    _renderDiffLine(lines[i], leftHtml, rightHtml);
  }
  leftPre.innerHTML = leftHtml.join('\n');
  rightPre.innerHTML = rightHtml.join('\n');
  _bindDiffScrollSync();
}

async function _showFileDiff(filepath) {
  var overlay = _ensureAutoupdateDiffOverlay();
  overlay.style.display = 'flex';
  document.getElementById('autoupdateDiffTitle').textContent = filepath;
  document.getElementById('diffLeftPre').textContent = t('autoupdate.diffLoading');
  document.getElementById('diffRightPre').textContent = '';

  try {
    var resp = await fetch('/v1/admin/autoupdate/diff', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file: filepath }),
    });
    var data = await resp.json();
    _renderFileDiffResult(data);
  } catch (e) {
    document.getElementById('diffLeftPre').textContent = 'Error: ' + e.message;
    document.getElementById('diffRightPre').textContent = '';
  }
}

async function triggerAutoupdateCheck() {
  try {
    var statusEl = document.getElementById('autoupdateResultStatus');
    var panel = document.getElementById('autoupdateResults');
    if (panel) panel.classList.remove('hidden');
    if (statusEl) { statusEl.textContent = t('autoupdate.checking'); statusEl.style.color = 'var(--muted)'; }
    var resp = await fetch('/v1/admin/autoupdate/check', { method: 'POST' });
    var data = await resp.json();
    if (data.success) {
      _showCheckResults(data.data);
      toast(t('autoupdate.checkComplete', { count: data.data.changed_count || 0 }), 'ok');
    } else {
      _showCheckResults({ status: 'error', message: data.error || t('actions.unknownError') });
      toast(t('autoupdate.checkFailedDetail', { error: data.error || t('actions.unknownError') }), 'error');
    }
  } catch (error) {
    _showCheckResults({ status: 'error', message: String(error) });
    toast(t('autoupdate.checkFailedDetail', { error: String(error) }), 'error');
  }
}

async function _applyAutoupdateReload() {
  try {
    var reloadResp = await fetch('/v1/config/reload', { method: 'POST' });
    var reloadResult = await reloadResp.json();
    if (reloadResult.status === 'ok') {
      toast(t('autoupdate.configReloaded'), 'ok');
    }
  } catch (e) { /* ignore reload errors */ }
}

async function applyAutoupdate() {
  try {
    var checkboxes = document.querySelectorAll('.autoupdate-file-check:checked');
    var selectedFiles = [];
    checkboxes.forEach(function(cb) { selectedFiles.push(cb.value); });

    if (selectedFiles.length === 0) {
      toast(t('autoupdate.selectAtLeastOne'), 'warn');
      return;
    }

    var confirmed = await showConfirmDialog(t('autoupdate.applyConfirm', { count: selectedFiles.length }));
    if (!confirmed) return;
    toast(t('autoupdate.applying', { count: selectedFiles.length }), 'info');
    var resp = await fetch('/v1/admin/autoupdate/apply', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ files: selectedFiles })
    });
    var data = await resp.json();
    if (data.success) {
      toast(t('autoupdate.applyOk', { count: selectedFiles.length }), 'ok');
      var applyBtn = document.getElementById('autoupdateApplyBtn');
      if (applyBtn) applyBtn.classList.add('hidden');
      await _applyAutoupdateReload();
      await refreshAll();
    } else {
      toast(t('autoupdate.applyFailed', { error: data.error || t('actions.unknownError') }), 'error');
    }
  } catch (error) {
    toast(t('autoupdate.applyFailed', { error: String(error) }), 'error');
  }
}

window.syncAutoupdateStatusFromConfig = syncAutoupdateStatusFromConfig;

function _initAutoupdateConfigSection() {
  var checkBtn = document.getElementById('autoupdateCheckBtn');
  if (checkBtn && !checkBtn.dataset.bound) {
    checkBtn.dataset.bound = '1';
    checkBtn.addEventListener('click', triggerAutoupdateCheck);
  }
  var applyBtn = document.getElementById('autoupdateApplyBtn');
  if (applyBtn && !applyBtn.dataset.bound) {
    applyBtn.dataset.bound = '1';
    applyBtn.addEventListener('click', applyAutoupdate);
  }
  var addMirrorBtn = document.getElementById('autoupdateAddMirrorBtn');
  if (addMirrorBtn && !addMirrorBtn.dataset.bound) {
    addMirrorBtn.dataset.bound = '1';
    addMirrorBtn.addEventListener('click', function() {
      var mirrors = _getMirrorsFromUI().slice();
      mirrors.push('');
      _renderAutoupdateMirrors(mirrors);
      _syncAutoupdateMirrorsToConfig(mirrors.filter(function(v) { return v; }));
      var inputs = document.querySelectorAll('#autoupdateMirrorsList .mirror-url');
      if (inputs.length) inputs[inputs.length - 1].focus();
    });
  }
  if (!window._autoupdateOpsLoaded) {
    window._autoupdateOpsLoaded = true;
    loadAutoupdateLastCheck();
  }
}
window._initAutoupdateConfigSection = _initAutoupdateConfigSection;
