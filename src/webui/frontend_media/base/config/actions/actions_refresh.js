async function refreshAll() {
  try {
    const [summaryResult, healthResult] = await Promise.allSettled([
      fetchJson('/v1/webui/summary'),
      fetchJson('/health')
    ]);
    if (summaryResult.status === 'fulfilled') {
      state.summary = summaryResult.value;
      var models = Array.isArray(summaryResult.value.models) ? summaryResult.value.models : [];
      state.models = models;
      state.modelsLoaded = true;
      renderOverview(summaryResult.value);
      if (typeof renderConfig === 'function') renderConfig(summaryResult.value);
      if (state.activeTab === 'config' && typeof activateConfigPanel === 'function') {
        activateConfigPanel(summaryResult.value);
      }
      renderModels(models);
      renderPlatforms(summaryResult.value.platforms || {});
      if (typeof populateModelDropdowns === 'function') {
        populateModelDropdowns(models);
      }
    } else {
      state.modelsLoaded = false;
      if (typeof populateModelDropdowns === 'function') {
        populateModelDropdowns(null, { error: true });
      }
      // API failed, show error state
      if (document.getElementById('versionValue')) {
        document.getElementById('versionValue').textContent = t('overview.loadFailed');
      }
      if (document.getElementById('modelsValue')) {
        document.getElementById('modelsValue').textContent = t('overview.loadFailed');
      }
      if (modelGrid) {
        modelGrid.innerHTML = '<div class="text-muted p-[18px] border border-dashed border-border rounded-xl text-center">' + t('overview.loadFailed') + '</div>';
      }
    }
    if (healthResult.status === 'fulfilled') {
      document.getElementById('healthValue').textContent = healthResult.value && healthResult.value.status ? healthResult.value.status : 'degraded';
    } else {
      if (document.getElementById('healthValue')) {
        document.getElementById('healthValue').textContent = t('overview.unknown');
      }
    }
    document.getElementById('lastRefresh').textContent = new Date().toLocaleTimeString();
  } catch (error) {
    toast(t('overview.refreshFailed', { error: String(error) }), 'error');
  }
}

async function refreshModels() {
  try {
    const result = await fetchJson('/v1/admin/refresh_models', { method: 'POST' });
    toast(t('actions.modelsRefreshOk'), 'ok');
    await refreshAll();
  } catch (error) {
    toast(t('actions.modelsRefreshFailed', { error: String(error) }), 'error');
  }
}

function _modelCaps(model) {
  return typeof resolveModelCapabilities === 'function'
    ? resolveModelCapabilities(model)
    : (model.capabilities || {});
}

function _isSttModel(model) {
  var caps = _modelCaps(model);
  var id = String(model.id || '').toLowerCase();
  if (caps.audio_transcription || caps.audio_in) return true;
  if (caps.chat && caps.vision) return true;
  if (/whisper|transcribe|paraformer|speech-to-text/.test(id)) return true;
  return false;
}

function _isTtsModel(model) {
  var caps = _modelCaps(model);
  var ownedBy = String(model.owned_by || '');
  if (!caps.audio_gen && !caps.tts) return false;
  if (ownedBy === 'edgetts' || ownedBy === 'gtts' || ownedBy === 'openaifm') return true;
  return !!(caps.audio_gen && !caps.chat);
}

function _populateChatDropdown(models) {
  var chatOpts = [];
  var autoSelect = null;
  for (var i = 0; i < models.length; i++) {
    var caps = _modelCaps(models[i]);
    if (!caps.chat) continue;
    // 排除纯 embedding/rerank 模型：即使平台默认带 chat，纯嵌入模型也不应出现在聊天列表
    if (caps.embedding && !caps.completions && !caps.vision && !caps.tools) continue;
    if (caps.rerank) continue;
    chatOpts.push({ value: models[i].id, text: models[i].id });
    if (models[i].id === 'qwen3.7-max') autoSelect = models[i].id;
  }
  var chatDropdown = window._dropdowns && window._dropdowns['chatModelSelect'];
  if (!chatDropdown) return;
  if (!chatOpts.length) {
    chatDropdown.setOptions([{ value: '', text: t('models.noMatch') }], false);
    return;
  }
  chatDropdown.setOptions(chatOpts, false);
  var saved = (typeof window._savedChatModel === 'string' && window._savedChatModel) ? window._savedChatModel : null;
  if (saved) {
    for (var j = 0; j < chatOpts.length; j++) {
      if (chatOpts[j].value === saved) {
        chatDropdown.setValue(saved);
        if (typeof window !== 'undefined') window._savedChatModel = null;
        saved = null;
        break;
      }
    }
  }
  if (saved === null && autoSelect) chatDropdown.setValue(autoSelect);
  else if (saved === null && chatOpts.length > 0) chatDropdown.setValue(chatOpts[0].value);
}

function _populateVoiceDropdowns(models) {
  var sttOpts = [{ value: '', text: t('common.notUsing') }];
  var ttsOpts = [{ value: '', text: t('common.notUsing') }];
  for (var k = 0; k < models.length; k++) {
    if (_isSttModel(models[k])) {
      sttOpts.push({ value: models[k].id, text: models[k].id });
    }
    if (_isTtsModel(models[k])) {
      ttsOpts.push({ value: models[k].id, text: models[k].id });
    }
  }
  var sttDropdown = window._dropdowns && window._dropdowns['voiceSttModel'];
  var ttsDropdown = window._dropdowns && window._dropdowns['voiceTtsModel'];
  if (sttDropdown) {
    if (sttOpts.length <= 1) {
      sttDropdown.setOptions([{ value: '', text: t('models.noMatch') }], false);
    } else {
      sttDropdown.setOptions(sttOpts, false);
      var vs = (typeof loadVoiceSettings === 'function') ? loadVoiceSettings() : {};
      if (vs.sttModel) sttDropdown.setValue(vs.sttModel);
    }
  }
  if (ttsDropdown) {
    if (ttsOpts.length <= 1) {
      ttsDropdown.setOptions([{ value: '', text: t('models.noMatch') }], false);
    } else {
      ttsDropdown.setOptions(ttsOpts, false);
      var vs2 = (typeof loadVoiceSettings === 'function') ? loadVoiceSettings() : {};
      if (vs2.ttsModel) ttsDropdown.setValue(vs2.ttsModel);
    }
  }
}

function populateModelDropdowns(models, options) {
  options = options || {};
  if (options.error) {
    var errOpt = [{ value: '', text: t('overview.loadFailed') }];
    ['chatModelSelect', 'voiceSttModel', 'voiceTtsModel'].forEach(function(id) {
      var dd = window._dropdowns && window._dropdowns[id];
      if (dd) dd.setOptions(errOpt, false);
    });
    return;
  }
  if (!Array.isArray(models)) return;
  _populateChatDropdown(models);
  _populateVoiceDropdowns(models);
}
