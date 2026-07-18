/**
 * LazyLoader -- dynamic script/style loader with per-tab resource tracking.
 * Loads JS sequentially (order matters) and CSS in parallel (order-independent).
 */
var LazyLoader = (function() {
  var S = {};
  S._loaded = new Set();
  S._pending = new Map();

  // TAB_RESOURCES is defined in the sibling file lazy_assets.js, which
  // must be loaded before this script (see index.html script order).
  S.TAB_RESOURCES = window.LAZY_TAB_RESOURCES;

  // loadScript/loadCSS/loadTabResources/isTabLoaded attached from
  // lazy_helpers.js (must load before this file, see index.html script order).
  _attachLazyLoaderMethods(S);

  return {
    loadScript: S.loadScript,
    loadCSS: S.loadCSS,
    loadTabResources: S.loadTabResources,
    isTabLoaded: S.isTabLoaded,
  };
})();
