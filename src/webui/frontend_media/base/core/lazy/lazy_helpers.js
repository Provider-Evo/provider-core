/**
 * LazyLoader helper builders -- split out of lazy.js to keep the facade
 * IIFE under the line cap. Attaches methods onto the shared S state
 * object via _attachLazyLoaderMethods(S).
 */
function _attachLazyLoaderScript(S) {
  var _loaded = S._loaded;
  var _pending = S._pending;

  /**
   * Load a single <script> tag, deduplicating concurrent/completed loads.
   * Split out of the LazyLoader IIFE to keep it under the line cap.
   */
  function loadScript(url) {
    if (_loaded.has(url)) return Promise.resolve();
    if (_pending.has(url)) return _pending.get(url);
    var promise = new Promise(function(resolve, reject) {
      var el = document.createElement('script');
      el.src = url;
      el.onload = function() {
        _loaded.add(url);
        _pending.delete(url);
        resolve();
      };
      el.onerror = function() {
        _pending.delete(url);
        var hint = url.indexOf('http') === 0 && typeof t === 'function'
          ? ' ' + t('lazy.scriptLoadHint')
          : '';
        reject(new Error('Failed to load script: ' + url + hint));
      };
      document.head.appendChild(el);
    });
    _pending.set(url, promise);
    return promise;
  }

  S.loadScript = loadScript;
}

function _attachLazyLoaderCSS(S) {
  var _loaded = S._loaded;
  var _pending = S._pending;

  /**
   * Load a single <link rel="stylesheet"> tag, deduplicating concurrent/
   * completed loads. Split out of the LazyLoader IIFE to keep it under
   * the line cap.
   */
  function loadCSS(url) {
    if (_loaded.has(url)) return Promise.resolve();
    if (_pending.has(url)) return _pending.get(url);
    var promise = new Promise(function(resolve, reject) {
      var el = document.createElement('link');
      el.rel = 'stylesheet';
      el.href = url;
      el.onload = function() {
        _loaded.add(url);
        _pending.delete(url);
        resolve();
      };
      el.onerror = function() {
        _pending.delete(url);
        reject(new Error('Failed to load CSS: ' + url));
      };
      document.head.appendChild(el);
    });
    _pending.set(url, promise);
    return promise;
  }

  S.loadCSS = loadCSS;
}

function _attachLazyLoaderTabResources(S) {
  var TAB_RESOURCES = S.TAB_RESOURCES;
  var loadScript = S.loadScript;
  var loadCSS = S.loadCSS;

  /**
   * Load all resources registered for a tab: CSS in parallel, then JS
   * sequentially (each script may depend on the previous one).
   * Split out of the LazyLoader IIFE to keep it under the line cap.
   */
  function loadTabResources(tabName) {
    var resources = TAB_RESOURCES[tabName];
    if (!resources || resources.length === 0) return Promise.resolve();

    var cssItems = [];
    var jsItems = [];
    for (var i = 0; i < resources.length; i++) {
      if (resources[i].type === 'css') cssItems.push(resources[i]);
      else jsItems.push(resources[i]);
    }

    // CSS can load in parallel -- order does not matter for stylesheets
    var cssPromises = [];
    for (var c = 0; c < cssItems.length; c++) {
      cssPromises.push(loadCSS(cssItems[c].url));
    }

    return Promise.all(cssPromises).then(function() {
      // JS must load sequentially -- each script may depend on the previous one
      var chain = Promise.resolve();
      for (var j = 0; j < jsItems.length; j++) {
        (function(item) {
          chain = chain.then(function() { return loadScript(item.url); });
        })(jsItems[j]);
      }
      return chain;
    });
  }

  S.loadTabResources = loadTabResources;
}

function _attachLazyLoaderTabLoaded(S) {
  var _loaded = S._loaded;
  var TAB_RESOURCES = S.TAB_RESOURCES;

  /**
   * Check whether every resource registered for a tab has already
   * finished loading. Split out of the LazyLoader IIFE to keep it
   * under the line cap.
   */
  function isTabLoaded(tabName) {
    var resources = TAB_RESOURCES[tabName];
    if (!resources || resources.length === 0) return true;
    for (var i = 0; i < resources.length; i++) {
      if (!_loaded.has(resources[i].url)) return false;
    }
    return true;
  }

  S.isTabLoaded = isTabLoaded;
}

function _attachLazyLoaderMethods(S) {
  _attachLazyLoaderScript(S);
  _attachLazyLoaderCSS(S);
  _attachLazyLoaderTabResources(S);
  _attachLazyLoaderTabLoaded(S);
}
