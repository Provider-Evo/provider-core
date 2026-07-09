/**
 * Provider WebUI i18n — vanilla i18next 风格 API。
 * localStorage: provider-locale | 语言: zh / en / ja / ko | fallback: en
 */
(function(global) {
  'use strict';

  var STORAGE_KEY = 'provider-locale';
  var SUPPORTED = ['zh', 'en', 'ja', 'ko'];
  var FALLBACK = 'en';
  var resources = {};
  var currentLng = FALLBACK;
  var listeners = [];

  function loadLocaleSync(lng) {
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

  function getNode(lng, key) {
    var parts = String(key).split('.');
    var node = resources[lng];
    for (var i = 0; i < parts.length; i++) {
      if (!node || typeof node !== 'object') return undefined;
      node = node[parts[i]];
    }
    return node;
  }

  function resolve(key) {
    var val = getNode(currentLng, key);
    if (typeof val === 'string') return val;
    if (currentLng !== FALLBACK) {
      val = getNode(FALLBACK, key);
      if (typeof val === 'string') return val;
    }
    if (currentLng !== 'zh') {
      val = getNode('zh', key);
      if (typeof val === 'string') return val;
    }
    return key;
  }

  function interpolate(str, opts) {
    if (!opts || typeof str !== 'string') return str;
    return str.replace(/\{\{(\w+)\}\}/g, function(_, name) {
      return opts[name] != null ? String(opts[name]) : '';
    });
  }

  function t(key, opts) {
    return interpolate(resolve(key), opts);
  }

  function detect() {
    try {
      var stored = localStorage.getItem(STORAGE_KEY);
      if (stored && SUPPORTED.indexOf(stored) !== -1) return stored;
    } catch (e) { /* ignore */ }
    var nav = (navigator.language || navigator.userLanguage || 'en').toLowerCase();
    var short = nav.split('-')[0];
    if (SUPPORTED.indexOf(short) !== -1) return short;
    return FALLBACK;
  }

  function htmlLang(lng) {
    if (lng === 'zh') return 'zh-CN';
    if (lng === 'en') return 'en';
    if (lng === 'ja') return 'ja';
    if (lng === 'ko') return 'ko';
    return lng;
  }

  function changeLanguage(lng) {
    if (SUPPORTED.indexOf(lng) === -1) return;
    currentLng = lng;
    try { localStorage.setItem(STORAGE_KEY, lng); } catch (e) { /* ignore */ }
    document.documentElement.lang = htmlLang(lng);
    for (var i = 0; i < listeners.length; i++) {
      try { listeners[i](lng); } catch (err) { console.error(err); }
    }
    applyPageI18n();
    updateLanguageSwitcher();
  }

  function onLanguageChanged(fn) {
    listeners.push(fn);
  }

  function applyPageI18n(root) {
    root = root || document;
    var nodes = root.querySelectorAll('[data-i18n]');
    for (var i = 0; i < nodes.length; i++) {
      var el = nodes[i];
      var key = el.getAttribute('data-i18n');
      if (!key) continue;
      var attr = el.getAttribute('data-i18n-attr');
      var text = t(key);
      if (attr) {
        el.setAttribute(attr, text);
      } else if (el.getAttribute('data-i18n-html') === 'true') {
        el.innerHTML = text;
      } else {
        el.textContent = text;
      }
    }
    var placeholders = root.querySelectorAll('[data-i18n-placeholder]');
    for (var j = 0; j < placeholders.length; j++) {
      var pKey = placeholders[j].getAttribute('data-i18n-placeholder');
      if (pKey) placeholders[j].setAttribute('placeholder', t(pKey));
    }
    var options = root.querySelectorAll('option[data-i18n]');
    for (var k = 0; k < options.length; k++) {
      var oKey = options[k].getAttribute('data-i18n');
      if (oKey) options[k].textContent = t(oKey);
    }
  }

  function updateLanguageSwitcher() {
    var menu = document.getElementById('langSwitcherMenu');
    if (!menu) return;
    var items = menu.querySelectorAll('[data-lang]');
    for (var i = 0; i < items.length; i++) {
      var code = items[i].getAttribute('data-lang');
      items[i].classList.toggle('is-active', code === currentLng);
    }
    var btn = document.getElementById('langSwitcherBtn');
    if (btn) {
      btn.setAttribute('title', t('header.switchLanguage'));
      btn.setAttribute('aria-label', t('header.switchLanguage'));
    }
  }

  function initLanguageSwitcher() {
    var btn = document.getElementById('langSwitcherBtn');
    var menu = document.getElementById('langSwitcherMenu');
    if (!btn || !menu) return;
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      menu.classList.toggle('is-open');
    });
    menu.querySelectorAll('[data-lang]').forEach(function(item) {
      item.addEventListener('click', function() {
        changeLanguage(item.getAttribute('data-lang'));
        menu.classList.remove('is-open');
      });
    });
    document.addEventListener('click', function() {
      menu.classList.remove('is-open');
    });
    updateLanguageSwitcher();
  }

  function init() {
    for (var i = 0; i < SUPPORTED.length; i++) {
      resources[SUPPORTED[i]] = loadLocaleSync(SUPPORTED[i]);
    }
    currentLng = detect();
    document.documentElement.lang = htmlLang(currentLng);
    applyPageI18n();
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', initLanguageSwitcher);
    } else {
      initLanguageSwitcher();
    }
  }

  global.t = t;
  global.applyPageI18n = applyPageI18n;
  global.i18n = {
    t: t,
    changeLanguage: changeLanguage,
    onLanguageChanged: onLanguageChanged,
    get language() { return currentLng; },
    get languages() { return SUPPORTED.slice(); },
  };

  init();
})(window);
