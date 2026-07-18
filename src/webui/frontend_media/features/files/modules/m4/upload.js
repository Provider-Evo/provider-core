/**
 * File Manager -- upload trigger, form upload, and drag-and-drop support.
 *
 * Part of the files.js split. Depends on state.js. Calls into
 * dirlist.js (_loadDirectory).
 */

function _triggerFilePicker() {
  var tab = _getActiveTab();
  if (tab && !_canWriteToTab(tab)) {
    if (typeof toast === 'function') toast(t('files.uploadDirRequired'), 'error');
    return;
  }
  var input = document.getElementById('filesUploadInput');
  if (input) input.click();
}

function _formatUploadSkipped(skipped) {
  if (!skipped || skipped.length === 0) return '';
  var first = skipped[0];
  var detail = first.file ? (first.file + ': ' + first.error) : first.error;
  if (skipped.length === 1) return detail;
  return detail + t('files.uploadPartialMore', { count: skipped.length - 1 });
}

async function _uploadFiles(tab, dirPath, fileList) {
  if (!fileList || fileList.length === 0) return;
  if (!tab || !_canWriteToTab(tab)) {
    if (typeof toast === 'function') toast(t('files.uploadDirRequired'), 'error');
    return;
  }

  var formData = new FormData();
  formData.append('dir', dirPath);
  for (var i = 0; i < fileList.length; i++) {
    formData.append('files', fileList[i]);
  }

  var count = fileList.length;
  if (typeof toast === 'function') toast(t('files.uploading', { count: count }), 'ok');

  try {
    var data = await Api.postForm('/v1/webui/files/upload', formData);
    var uploaded = (data && data.uploaded) || [];
    var skipped = (data && data.skipped) || [];
    if (skipped.length > 0) {
      var msg = t('files.uploadPartial', {
        uploaded: uploaded.length,
        skipped: skipped.length,
        detail: _formatUploadSkipped(skipped)
      });
      if (typeof toast === 'function') toast(msg, uploaded.length > 0 ? 'ok' : 'error');
    } else if (typeof toast === 'function') {
      toast(t('files.uploadedCount', { count: uploaded.length }), 'ok');
    }
    _loadDirectory(tab, tab.path);
  } catch (e) {
    var skippedErr = (e.data && e.data.skipped) || [];
    var errMsg = e.message;
    if (skippedErr.length > 0) {
      errMsg += ' (' + _formatUploadSkipped(skippedErr) + ')';
    }
    if (typeof toast === 'function') toast(t('files.uploadFailed', { error: errMsg }), 'error');
  }
}

function _dragDropShowOverlay(listArea, state) {
  if (state.overlay) return;
  state.overlay = document.createElement('div');
  state.overlay.className = 'files-drop-overlay';
  state.overlay.textContent = t('files.dropToUpload');
  listArea.style.position = 'relative';
  listArea.appendChild(state.overlay);
}

function _dragDropHideOverlay(state) {
  if (state.overlay) {
    state.overlay.remove();
    state.overlay = null;
  }
  state.dragCounter = 0;
}

function _wireDragEnter(listArea, tab, state) {
  listArea.addEventListener('dragenter', function (e) {
    e.preventDefault();
    e.stopPropagation();
    if (!_canWriteToTab(tab)) return;
    state.dragCounter++;
    if (e.dataTransfer && e.dataTransfer.types && e.dataTransfer.types.indexOf('Files') !== -1) {
      _dragDropShowOverlay(listArea, state);
    }
  });
}

function _wireDragOverLeave(listArea, state) {
  listArea.addEventListener('dragover', function (e) {
    e.preventDefault();
    e.stopPropagation();
    if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy';
  });

  listArea.addEventListener('dragleave', function (e) {
    e.preventDefault();
    e.stopPropagation();
    state.dragCounter--;
    if (state.dragCounter <= 0) {
      _dragDropHideOverlay(state);
    }
  });
}

function _wireDrop(listArea, tab, state) {
  listArea.addEventListener('drop', function (e) {
    e.preventDefault();
    e.stopPropagation();
    _dragDropHideOverlay(state);
    if (!_canWriteToTab(tab)) {
      if (typeof toast === 'function') toast(t('files.uploadDirRequired'), 'error');
      return;
    }
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      _uploadFiles(tab, tab.path, e.dataTransfer.files);
    }
  });
}

function _setupDragDrop(listArea, tab) {
  var state = { overlay: null, dragCounter: 0 };
  _wireDragEnter(listArea, tab, state);
  _wireDragOverLeave(listArea, state);
  _wireDrop(listArea, tab, state);
}
