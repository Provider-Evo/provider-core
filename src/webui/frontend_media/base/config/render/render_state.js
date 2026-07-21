// ========================= Schema-driven rendering: shared state =========================
// 拆分自 render.js。模块级共享状态与 target/mode 存取函数，供其余 render/*.js 子模块使用。

var _configPanelSchema = null;
var _webuiConfigPanelSchema = null;
var _activeConfigSchema = null;
var _lastConfigSaveTime = 0;
var _activeConfigSection = null;
var _configSourceNoticeDismissed = localStorage.getItem('provider.configSourceNoticeDismissed') === 'true';

function getConfigEditMode() {
  var mode = window._configEditMode || localStorage.getItem('provider.configEditMode') || 'visual';
  return mode === 'source' ? 'source' : 'visual';
}

function setConfigEditMode(mode) {
  window._configEditMode = mode;
  localStorage.setItem('provider.configEditMode', mode);
}

function getConfigTarget() {
  return window._configTarget || localStorage.getItem('provider.configTarget') || 'main';
}

function setConfigTarget(target) {
  window._configTarget = target;
  localStorage.setItem('provider.configTarget', target);
}

function _isFlatConfigTarget() {
  return getConfigTarget() === 'webui';
}

function _configSetValue(config, section, key, val) {
  if (_isFlatConfigTarget() || section === '_root') {
    config[key] = val;
    return;
  }
  if (!config[section]) config[section] = {};
  config[section][key] = val;
}

function _configGetValue(config, section, key) {
  if (_isFlatConfigTarget() || section === '_root') {
    return config[key];
  }
  return config[section] && config[section][key];
}

window.getConfigTarget = getConfigTarget;
window.setConfigTarget = setConfigTarget;
window.getConfigEditMode = getConfigEditMode;
window.setConfigEditMode = setConfigEditMode;
