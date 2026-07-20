/**
 * File Manager -- clipboard, delete, rename, new-folder, and download operations.
 *
 * Part of the files.js split. Depends on state.js. Calls into
 * dirlist.js (_loadDirectory), render.js (_renderContent),
 * tabs.js (_canWriteToTab is in state.js).
 */

function _clipboardCopy(paths) {
  _clipboard = { action: 'copy', paths: paths.slice() };
  if (typeof toast === 'function') toast(t('files.copiedCount', { count: paths.length }), 'ok');
}

function _clipboardCut(paths) {
  _clipboard = { action: 'cut', paths: paths.slice() };
  if (typeof toast === 'function') toast(t('files.cutCount', { count: paths.length }), 'ok');
}

async function _clipboardPaste(tab) {
  if (!_clipboard.action || _clipboard.paths.length === 0) return;
  if (!tab || !_canWriteToTab(tab)) {
    if (typeof toast === 'function') {
      toast(t('files.genericFailed', { error: t('files.dirNotWritable') }), 'error');
    }
    return;
  }
  var endpoint = _clipboard.action === 'cut' ? '/v1/webui/files/move' : '/v1/webui/files/copy';
  var actionLabel = _clipboard.action === 'cut' ? t('files.move') : t('files.copy');
  var destDir = tab.path || '/';

  // Process each path sequentially
  var successCount = 0;
  for (var i = 0; i < _clipboard.paths.length; i++) {
    var srcPath = _clipboard.paths[i];
    try {
      await Api.post(endpoint, { source: srcPath, dest: destDir });
      successCount++;
    } catch (e) {
      if (typeof toast === 'function') toast(t('files.pasteFailed', { action: actionLabel, error: e.message }), 'error');
    }
  }

  if (successCount > 0) {
    if (typeof toast === 'function') toast(t('files.pasteOk', { action: actionLabel, count: successCount }), 'ok');
  }

  // Clear clipboard after cut, keep for copy
  if (_clipboard.action === 'cut') {
    _clipboard = { action: null, paths: [] };
  }

  _loadDirectory(tab, tab.path);
}

function _downloadFile(path) {
  var a = document.createElement('a');
  a.href = '/v1/webui/files/download?path=' + encodeURIComponent(path);
  a.download = '';
  document.body.appendChild(a);
  a.click();
  a.remove();
}

async function _deleteEntries(tab, paths) {
  var msg = paths.length === 1 ?
    t('files.deleteSingleConfirm', { name: paths[0].split(/[\/\\]/).pop() }) :
    t('files.deleteMultiConfirm', { count: paths.length });
  var confirmed = await showConfirmDialog(msg, { title: t('files.deleteTitle'), confirmText: t('files.delete') });
  if (!confirmed) return;

  try {
    var resp = await Api.post('/v1/webui/files/delete', { paths: paths });
    var ok = (resp.results || []).every(function (r) { return r.ok; });
    if (ok) {
      if (typeof toast === 'function') toast(t('files.deleteOk'), 'ok');
      _loadDirectory(tab, tab.path);
    } else {
      var errs = (resp.results || []).filter(function (r) { return !r.ok; });
      if (typeof toast === 'function') toast(t('files.deleteFailed', { error: errs[0].error }), 'error');
    }
  } catch (e) {
    if (typeof toast === 'function') toast(t('files.deleteFailed', { error: e.message }), 'error');
  }
}

function _showRenameDialog(tab, entry) {
  var overlay = document.createElement('div');
  overlay.className = 'files-rename-overlay';

  overlay.innerHTML =
    '<div class="files-rename-dialog">' +
    '<h3>' + t('files.rename') + '</h3>' +
    '<input type="text" id="filesRenameInput" value="' + _escapeAttr(entry.name) + '">' +
    '<div class="files-rename-actions">' +
    '<button class="files-rename-cancel" type="button">' + t('common.cancel') + '</button>' +
    '<button class="files-rename-confirm" type="button">' + t('files.rename') + '</button>' +
    '</div></div>';

  document.body.appendChild(overlay);

  var input = overlay.querySelector('#filesRenameInput');
  // Select name without extension for files
  if (entry.type === 'file') {
    var dotIdx = entry.name.lastIndexOf('.');
    if (dotIdx > 0) input.setSelectionRange(0, dotIdx);
    else input.select();
  } else {
    input.select();
  }
  input.focus();

  overlay.querySelector('.files-rename-cancel').addEventListener('click', function () {
    overlay.remove();
  });

  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) overlay.remove();
  });

  var doRename = _makeRenameSubmitHandler(overlay, input, tab, entry);
  overlay.querySelector('.files-rename-confirm').addEventListener('click', doRename);
  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') { e.preventDefault(); doRename(); }
    if (e.key === 'Escape') overlay.remove();
  });
}

function _submitRename(overlay, input, tab, entry) {
  var newName = input.value.trim();
  if (!newName || newName === entry.name) { overlay.remove(); return; }

  var parentPath = entry.path.replace(/[\/\\][^\/\\]+[\/\\]?$/, '') || '/';
  var newPath = _pathJoin(parentPath, newName);

  Api.post('/v1/webui/files/rename', {
    old_path: entry.path,
    new_path: newPath,
  }).then(function () {
    if (typeof toast === 'function') toast(t('files.renamed'), 'ok');
    _loadDirectory(tab, tab.path);
  }).catch(function (e) {
    if (typeof toast === 'function') toast(t('files.renameFailed', { error: e.message }), 'error');
  });

  overlay.remove();
}

function _makeRenameSubmitHandler(overlay, input, tab, entry) {
  return function () {
    _submitRename(overlay, input, tab, entry);
  };
}

function _promptNewFolder(tab) {
  showInputDialog(t('files.newFolderPrompt'), {
    title: t('files.newFolder'),
    placeholder: t('files.folderNamePlaceholder')
  }).then(function(name) {
    if (!name || !name.trim()) return;

    var newPath = _pathJoin(tab.path, name.trim());

    Api.post('/v1/webui/files/mkdir', { path: newPath }).then(function () {
      if (typeof toast === 'function') toast(t('files.folderCreated'), 'ok');
      _loadDirectory(tab, tab.path);
    }).catch(function (e) {
      if (typeof toast === 'function') toast(t('files.genericFailed', { error: e.message }), 'error');
    });
  });
}

