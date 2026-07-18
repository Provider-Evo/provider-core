/**
 * Language-switcher UI wiring (dropdown button + menu).
 * Split out of i18n.js as a sibling module; depends on I18nCore and must
 * load before i18n.js.
 */
var I18nSwitcher = (function() {
  'use strict';

  var Core = I18nCore;

  function updateLanguageSwitcher() {
    var menu = document.getElementById('langSwitcherMenu');
    if (!menu) return;
    var items = menu.querySelectorAll('[data-lang]');
    for (var i = 0; i < items.length; i++) {
      var code = items[i].getAttribute('data-lang');
      items[i].classList.toggle('is-active', code === Core.language);
    }
    var btn = document.getElementById('langSwitcherBtn');
    if (btn) {
      btn.setAttribute('title', Core.t('header.switchLanguage'));
      btn.setAttribute('aria-label', Core.t('header.switchLanguage'));
    }
  }

  function changeLanguageAndUpdate(lng) {
    Core.changeLanguage(lng, updateLanguageSwitcher);
  }

  function init() {
    var btn = document.getElementById('langSwitcherBtn');
    var menu = document.getElementById('langSwitcherMenu');
    if (!btn || !menu) return;
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      menu.classList.toggle('is-open');
    });
    menu.querySelectorAll('[data-lang]').forEach(function(item) {
      item.addEventListener('click', function() {
        changeLanguageAndUpdate(item.getAttribute('data-lang'));
        menu.classList.remove('is-open');
      });
    });
    document.addEventListener('click', function() {
      menu.classList.remove('is-open');
    });
    updateLanguageSwitcher();
  }

  return {
    init: init,
    update: updateLanguageSwitcher,
    changeLanguageAndUpdate: changeLanguageAndUpdate,
  };
})();
