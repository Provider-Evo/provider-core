async function _saveConfigSource(isWebui) {
  var editor = document.getElementById('configTomlEditor');
  var rawContent = editor ? editor.value : '';
  var rawUrl = isWebui ? '/v1/webui/config/raw' : '/v1/config/raw';
  var rawResponse = await fetch(rawUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ raw_content: rawContent }),
  });
  var rawResult = await rawResponse.json();
  if (!rawResponse.ok || rawResult.error) {
    var errEl = document.getElementById('configTomlError');
    var errMsg = rawResult.error || (typeof t === 'function' ? t('actions.unknownError') : 'unknown error');
    if (errEl) {
      errEl.textContent = errMsg;
      errEl.classList.remove('hidden');
    }
    toast(t('actions.configSaveFailed', { error: errMsg }), 'error');
    return;
  }
  state.configDirty = false;
  updateConfigSaveStatus();
  if (typeof _updateConfigSaveBtn === 'function') _updateConfigSaveBtn();
  var errHide = document.getElementById('configTomlError');
  if (errHide) errHide.classList.add('hidden');
  toast(t('actions.configSaveOk'), 'ok');
  if (typeof _lastConfigSaveTime !== 'undefined') _lastConfigSaveTime = Date.now();
  if (isWebui && typeof _applyWebuiRuntime === 'function') {
    var cfgResp = await fetch('/v1/webui/config');
    if (cfgResp.ok) _applyWebuiRuntime(await cfgResp.json());
  } else if (!isWebui) {
    await refreshAll();
  }
}

async function _saveConfigStructured(isWebui) {
  if (typeof _syncConfigFromDOM === 'function') _syncConfigFromDOM();
  var url = isWebui ? '/v1/webui/config' : '/v1/config';
  var configData;
  if (window._currentConfig) {
    configData = window._currentConfig;
  } else {
    configData = await fetchJson(url);
  }
  var response = await fetch(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(configData)
  });
  var result = await response.json();
  if (result.status === 'ok') {
    state.configDirty = false;
    updateConfigSaveStatus();
    if (typeof _updateConfigSaveBtn === 'function') _updateConfigSaveBtn();
    toast(t('actions.configSaveOk'), 'ok');
    if (typeof _lastConfigSaveTime !== 'undefined') _lastConfigSaveTime = Date.now();
    if (isWebui && typeof _applyWebuiRuntime === 'function') _applyWebuiRuntime(configData);
    if (!isWebui) await refreshAll();
  } else {
    toast(t('actions.configSaveFailed', { error: result.error || t('actions.unknownError') }), 'error');
  }
}

async function saveConfig() {
  try {
    var isWebui = typeof getConfigTarget === 'function' && getConfigTarget() === 'webui';
    var isSource = typeof getConfigEditMode === 'function' && getConfigEditMode() === 'source';

    if (isSource) {
      await _saveConfigSource(isWebui);
      return;
    }
    await _saveConfigStructured(isWebui);
  } catch (error) {
    toast(t('actions.configSaveFailed', { error: String(error) }), 'error');
  }
}

function _applyConfigReloadResult(isWebui, isSource) {
  if (isSource && typeof _loadConfigRaw === 'function') {
    _loadConfigRaw();
    return;
  }
  if (typeof forceRenderConfig === 'function') {
    forceRenderConfig(state.summary);
    return;
  }
  if (isWebui && typeof renderConfig === 'function') {
    renderConfig(state.summary);
    return;
  }
  return refreshAll();
}

async function reloadConfigFromFile() {
  try {
    const isWebui = typeof getConfigTarget === 'function' && getConfigTarget() === 'webui';
    const isSource = typeof getConfigEditMode === 'function' && getConfigEditMode() === 'source';
    const url = isWebui ? '/v1/webui/config/reload' : '/v1/config/reload';
    const response = await fetch(url, { method: 'POST' });
    const result = await response.json();
    if (result.status !== 'ok') {
      toast(t('config.reloadFailed', { error: result.error || t('common.failed') }), 'error');
      return;
    }
    state.configDirty = false;
    updateConfigSaveStatus();
    if (typeof _updateConfigSaveBtn === 'function') _updateConfigSaveBtn();
    toast(t('config.reloadOk'), 'ok');
    await _applyConfigReloadResult(isWebui, isSource);
  } catch (error) {
    toast(t('config.reloadFailed', { error: String(error) }), 'error');
  }
}
