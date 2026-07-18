/**
 * I18nCore 方法层：locale 加载、key 解析、插值、页面属性应用。
 * 挂载到状态对象 S 上，供 i18n_core.js 组装为公开 API。
 */
function _i18nLoadLocaleSync(S, lng) {
  var xhr = new XMLHttpRequest();
  xhr.open('GET', '/static/i18n/locales/' + lng + '.json', false);
  try {
    xhr.send(null);
    if (xhr.status >= 200 && xhr.status < 300 && xhr.responseText) {
      return JSON.parse(xhr.responseText);
    }
  } catch (e) {
    console.warn('locale load failed:', lng, e);
  }
  return {};
}

function _i18nGetNode(S, lng, key) {
  var parts = String(key).split('.');
  var node = S.resources[lng];
  for (var i = 0; i < parts.length; i++) {
    if (!node || typeof node !== 'object') return undefined;
    node = node[parts[i]];
  }
  return node;
}

function _i18nResolve(S, key) {
  var val = S.getNode(S.currentLng, key);
  if (typeof val === 'string') return val;
  if (S.currentLng !== S.FALLBACK) {
    val = S.getNode(S.FALLBACK, key);
    if (typeof val === 'string') return val;
  }
  if (S.currentLng !== 'zh') {
    val = S.getNode('zh', key);
    if (typeof val === 'string') return val;
  }
  return key;
}

function _i18nInterpolate(S, str, opts) {
  if (!opts || typeof str !== 'string') return str;
  return str.replace(/\{\{(\w+)\}\}/g, function(_, name) {
    return opts[name] != null ? String(opts[name]) : '';
  });
}

function _i18nT(S, key, opts) {
  return S.interpolate(S.resolve(key), opts);
}

function _i18nDetect(S) {
  try {
    var stored = localStorage.getItem(S.STORAGE_KEY);
    if (stored && S.SUPPORTED.indexOf(stored) !== -1) return stored;
  } catch (e) { /* ignore */ }
  var nav = (navigator.language || navigator.userLanguage || 'en').toLowerCase();
  var short = nav.split('-')[0];
  if (S.SUPPORTED.indexOf(short) !== -1) return short;
  return S.FALLBACK;
}

function _i18nHtmlLang(S, lng) {
  if (lng === 'zh') return 'zh-CN';
  if (lng === 'en') return 'en';
  if (lng === 'ja') return 'ja';
  if (lng === 'ko') return 'ko';
  return lng;
}

function _i18nChangeLanguage(S, lng, onChanged) {
  if (S.SUPPORTED.indexOf(lng) === -1) return;
  S.currentLng = lng;
  try { localStorage.setItem(S.STORAGE_KEY, lng); } catch (e) { /* ignore */ }
  document.documentElement.lang = S.htmlLang(lng);
  for (var i = 0; i < S.listeners.length; i++) {
    try { S.listeners[i](lng); } catch (err) { console.error(err); }
  }
  S.applyPageI18n();
  if (onChanged) onChanged(lng);
}

function _i18nOnLanguageChanged(S, fn) {
  S.listeners.push(fn);
}

function _i18nApplyPageI18nAttrs(S, root) {
  var nodes = root.querySelectorAll('[data-i18n]');
  for (var i = 0; i < nodes.length; i++) {
    var el = nodes[i];
    var key = el.getAttribute('data-i18n');
    if (!key) continue;
    var attr = el.getAttribute('data-i18n-attr');
    var text = S.t(key);
    if (attr) {
      el.setAttribute(attr, text);
    } else if (el.getAttribute('data-i18n-html') === 'true') {
      el.innerHTML = text;
    } else {
      el.textContent = text;
    }
  }
}

function _i18nApplyPagePlaceholders(S, root) {
  var placeholders = root.querySelectorAll('[data-i18n-placeholder]');
  for (var j = 0; j < placeholders.length; j++) {
    var pKey = placeholders[j].getAttribute('data-i18n-placeholder');
    if (pKey) placeholders[j].setAttribute('placeholder', S.t(pKey));
  }
  var options = root.querySelectorAll('option[data-i18n]');
  for (var k = 0; k < options.length; k++) {
    var oKey = options[k].getAttribute('data-i18n');
    if (oKey) options[k].textContent = S.t(oKey);
  }
}

function _i18nApplyPageI18n(S, root) {
  root = root || document;
  S.applyPageI18nAttrs(root);
  S.applyPagePlaceholders(root);
}

function _i18nLoadAllLocales(S) {
  for (var i = 0; i < S.SUPPORTED.length; i++) {
    S.resources[S.SUPPORTED[i]] = S.loadLocaleSync(S.SUPPORTED[i]);
  }
}

function _i18nSetCurrentLng(S, lng) {
  S.currentLng = lng;
}

function _attachI18nCoreMethods(S) {
  S.loadLocaleSync = function(lng) { return _i18nLoadLocaleSync(S, lng); };
  S.getNode = function(lng, key) { return _i18nGetNode(S, lng, key); };
  S.resolve = function(key) { return _i18nResolve(S, key); };
  S.interpolate = function(str, opts) { return _i18nInterpolate(S, str, opts); };
  S.t = function(key, opts) { return _i18nT(S, key, opts); };
  S.detect = function() { return _i18nDetect(S); };
  S.htmlLang = function(lng) { return _i18nHtmlLang(S, lng); };
  S.changeLanguage = function(lng, onChanged) { return _i18nChangeLanguage(S, lng, onChanged); };
  S.onLanguageChanged = function(fn) { return _i18nOnLanguageChanged(S, fn); };
  S.applyPageI18nAttrs = function(root) { return _i18nApplyPageI18nAttrs(S, root); };
  S.applyPagePlaceholders = function(root) { return _i18nApplyPagePlaceholders(S, root); };
  S.applyPageI18n = function(root) { return _i18nApplyPageI18n(S, root); };
  S.loadAllLocales = function() { return _i18nLoadAllLocales(S); };
  S.setCurrentLng = function(lng) { return _i18nSetCurrentLng(S, lng); };
}
