/**
 * i18n core: locale resource loading, key resolution, interpolation,
 * and page-wide [data-i18n] attribute application.
 * Split out of i18n.js as a sibling module; must load before i18n.js.
 */
var I18nCore = (function() {
  'use strict';

  var S = {
    STORAGE_KEY: 'provider-locale',
    SUPPORTED: ['zh', 'en', 'ja', 'ko'],
    FALLBACK: 'en',
    resources: {},
    currentLng: 'en',
    listeners: [],
  };
  _attachI18nCoreMethods(S);

  return {
    SUPPORTED: S.SUPPORTED,
    FALLBACK: S.FALLBACK,
    t: S.t,
    detect: S.detect,
    htmlLang: S.htmlLang,
    changeLanguage: S.changeLanguage,
    onLanguageChanged: S.onLanguageChanged,
    applyPageI18n: S.applyPageI18n,
    loadAllLocales: S.loadAllLocales,
    setCurrentLng: S.setCurrentLng,
    get language() { return S.currentLng; },
  };
})();
