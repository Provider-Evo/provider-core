/**
 * Prompt-template locale mapping and fetch helper (used by chat prompt
 * loading, distinct from the UI locale set in I18nCore).
 * Split out of i18n.js as a sibling module; must load before i18n.js.
 */
var I18nPrompt = (function() {
  'use strict';

  var PROMPT_LOCALE_MAP = { zh: 'zh-CN', en: 'en-US', ja: 'ja-JP', ko: 'ko-KR' };
  var PROMPT_LOCALE_FALLBACK = ['zh-CN', 'en-US'];

  function promptLocale(lng) {
    lng = lng || I18nCore.language;
    return PROMPT_LOCALE_MAP[lng] || PROMPT_LOCALE_FALLBACK[0];
  }

  function promptLocaleCandidates(lng) {
    var primary = promptLocale(lng);
    var out = [primary];
    PROMPT_LOCALE_FALLBACK.forEach(function(code) {
      if (out.indexOf(code) === -1) out.push(code);
    });
    return out;
  }

  async function fetchPromptTemplate(name, lng) {
    var candidates = promptLocaleCandidates(lng);
    var lastError = null;
    for (var i = 0; i < candidates.length; i++) {
      var url = '/prompts/' + candidates[i] + '/' + name + '.prompt';
      try {
        var resp = await fetch(url);
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        return (await resp.text()).trim();
      } catch (e) {
        lastError = e;
      }
    }
    throw lastError || new Error('prompt not found');
  }

  return {
    promptLocale: promptLocale,
    promptLocaleCandidates: promptLocaleCandidates,
    fetchPromptTemplate: fetchPromptTemplate,
  };
})();
