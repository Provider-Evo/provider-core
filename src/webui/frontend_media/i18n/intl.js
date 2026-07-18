/**
 * Provider WebUI i18n — vanilla i18next 风格 API。
 * localStorage: provider-locale | 语言: zh / en / ja / ko | fallback: en
 * Facade over I18nCore / I18nSwitcher / I18nPrompt, which must load before
 * this file (see index.html script order).
 */
(function(global) {
  'use strict';

  function init() {
    I18nCore.loadAllLocales();
    I18nCore.setCurrentLng(I18nCore.detect());
    document.documentElement.lang = I18nCore.htmlLang(I18nCore.language);
    I18nCore.applyPageI18n();
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', I18nSwitcher.init);
    } else {
      I18nSwitcher.init();
    }
  }

  global.t = I18nCore.t;
  global.applyPageI18n = I18nCore.applyPageI18n;
  global.i18n = {
    t: I18nCore.t,
    changeLanguage: I18nSwitcher.changeLanguageAndUpdate,
    onLanguageChanged: I18nCore.onLanguageChanged,
    promptLocale: I18nPrompt.promptLocale,
    promptLocaleCandidates: I18nPrompt.promptLocaleCandidates,
    fetchPromptTemplate: I18nPrompt.fetchPromptTemplate,
    get language() { return I18nCore.language; },
    get languages() { return I18nCore.SUPPORTED.slice(); },
  };

  init();
})(window);
