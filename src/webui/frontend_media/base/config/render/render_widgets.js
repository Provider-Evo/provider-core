// ========================= Dynamic widget enrichment (models / audio devices) =========================
// 拆分自 render.js。依赖 render_state.js / render_data.js（_configSetValue/_onWebuiConfigFieldChange）。

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

function _modelIds(models, filterFn) {
  var opts = [];
  for (var i = 0; i < models.length; i++) {
    if (filterFn(models[i])) opts.push(models[i].id);
  }
  return opts;
}

function _fillModelSelect(el, value, models, filterFn) {
  if (!el) return;
  el.setAttribute('data-dynamic', 'true');
  var ids = _modelIds(models, filterFn);
  var emptyLabel = ids.length
    ? (typeof t === 'function' ? t('common.notUsing') : '')
    : (typeof t === 'function' ? t('models.noMatch') : '无可用模型');
  var html = '<option value="">' + escapeHtml(emptyLabel) + '</option>';
  for (var i = 0; i < ids.length; i++) {
    html += '<option value="' + escapeHtml(ids[i]) + '"' + (ids[i] === value ? ' selected' : '') + '>' + escapeHtml(ids[i]) + '</option>';
  }
  el.innerHTML = html;
  if (el._customDropdown && typeof el._customDropdown.destroy === 'function') {
    el._customDropdown.destroy();
    el._customDropdown = null;
  }
  if (typeof CustomDropdown !== 'undefined') {
    el._customDropdown = new CustomDropdown(el, {
      onChange: function(val) {
        var section = el.getAttribute('data-section');
        var key = el.getAttribute('data-key');
        _configSetValue(window._currentConfig, section, key, val);
        _onWebuiConfigFieldChange(key, val);
        scheduleConfigSave();
      }
    });
  }
}

async function _loadModelsForWidgets() {
  var models = state.models || [];
  if (models.length || typeof fetchJson !== 'function') return models;
  try {
    var summary = await fetchJson('/v1/webui/summary');
    models = (summary && Array.isArray(summary.models)) ? summary.models : [];
    if (models.length) {
      state.summary = summary;
      state.models = models;
      state.modelsLoaded = true;
    }
  } catch (e) { /* ignore */ }
  return models;
}

async function _enrichAudioDeviceSelect(config) {
  if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) return;
  try {
    var devices = await navigator.mediaDevices.enumerateDevices();
    var audioInputs = devices.filter(function(d) { return d.kind === 'audioinput'; });
    var recSel = configGrid.querySelector('select.config-input[data-key="recordingDeviceId"]');
    if (!recSel) return;
    recSel.setAttribute('data-dynamic', 'true');
    var current = config.recordingDeviceId || '';
    var html = '<option value="">' + escapeHtml(typeof t === 'function' ? t('portable.defaultDevice') : '默认设备') + '</option>';
    for (var i = 0; i < audioInputs.length; i++) {
      var dev = audioInputs[i];
      html += '<option value="' + escapeHtml(dev.deviceId) + '"' + (dev.deviceId === current ? ' selected' : '') + '>'
        + escapeHtml(dev.label || ('Mic ' + (i + 1))) + '</option>';
    }
    recSel.innerHTML = html;
    if (recSel._customDropdown && typeof recSel._customDropdown.destroy === 'function') {
      recSel._customDropdown.destroy();
      recSel._customDropdown = null;
    }
    if (typeof CustomDropdown !== 'undefined') {
      recSel._customDropdown = new CustomDropdown(recSel, {
        onChange: function(value) {
          var section = recSel.getAttribute('data-section');
          var key = recSel.getAttribute('data-key');
          _configSetValue(window._currentConfig, section, key, value);
          scheduleConfigSave();
        }
      });
    }
  } catch (e) { /* ignore */ }
}

async function _enrichWebuiWidgets(config) {
  if (!configGrid) return;
  var models = await _loadModelsForWidgets();
  _fillModelSelect(configGrid.querySelector('select.config-input[data-key="sttModel"]'), config.sttModel || '', models, _isSttModel);
  _fillModelSelect(configGrid.querySelector('select.config-input[data-key="ttsModel"]'), config.ttsModel || '', models, _isTtsModel);
  await _enrichAudioDeviceSelect(config);
}
