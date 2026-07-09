/**
 * LazyLoader -- dynamic script/style loader with per-tab resource tracking.
 * Loads JS sequentially (order matters) and CSS in parallel (order-independent).
 */
var LazyLoader = (function() {
  var _loaded = new Set();
  var _pending = new Map();

  var TAB_RESOURCES = {
    terminal: [
      { type: 'css', url: 'https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/css/xterm.css' },
      { type: 'css', url: '/static/base/core/tabbar/tabbar.css' },
      { type: 'css', url: '/static/ui/terminal/terminal.css' },
      { type: 'js',  url: 'https://cdn.jsdelivr.net/npm/@xterm/xterm@5.5.0/lib/xterm.js' },
      { type: 'js',  url: 'https://cdn.jsdelivr.net/npm/@xterm/addon-fit@0.10.0/lib/addon-fit.js' },
      { type: 'js',  url: '/static/base/core/tabbar/tabbar.js' },
      { type: 'js',  url: '/static/ui/terminal/terminal.js?v=20260709-4' },
    ],
    files: [
      { type: 'css', url: 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css' },
      { type: 'js',  url: 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js' },
      { type: 'css', url: '/static/base/core/tabbar/tabbar.css' },
      { type: 'css', url: '/static/files/files.css?v=20260709-5' },
      { type: 'js',  url: '/static/base/core/tabbar/tabbar.js' },
      { type: 'js',  url: '/static/files/files.js?v=20260709-5' },
    ],
    chat: [
      { type: 'css', url: 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/styles/github-dark.min.css' },
      { type: 'css', url: '/static/files/files.css?v=20260709-6' },
      { type: 'css', url: '/static/ui/widgets/input-box.css' },
      { type: 'js',  url: 'https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js' },
      { type: 'js',  url: '/static/ui/widgets/input-box.js?v=20260709-6' },
      { type: 'js',  url: '/static/ui/chat/chat-attachments.js?v=20260709-10' },
      { type: 'js',  url: '/static/ui/chat/chat-media-persist.js?v=20260709-10' },
      { type: 'js',  url: '/static/ui/chat/chat.js?v=20260709-12' },
    ],
    stats: [
      { type: 'js', url: '/static/stats/stats.js' },
      { type: 'js', url: '/static/stats/request-inspector.js' },
    ],
    config: [],
    autoupdate: [
      { type: 'css', url: '/static/ui/sortable-list/sortable-list.css' },
      { type: 'js',  url: '/static/ui/sortable-list/sortable-list.js' },
    ],
    plugins: [
      { type: 'css', url: '/static/plugins/plugins.css?v=20260709-2' },
      { type: 'js', url: '/static/plugins/plugins.js?v=20260709-2' },
    ],
  };

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
        reject(new Error('Failed to load script: ' + url));
      };
      document.head.appendChild(el);
    });
    _pending.set(url, promise);
    return promise;
  }

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

  function isTabLoaded(tabName) {
    var resources = TAB_RESOURCES[tabName];
    if (!resources || resources.length === 0) return true;
    for (var i = 0; i < resources.length; i++) {
      if (!_loaded.has(resources[i].url)) return false;
    }
    return true;
  }

  return {
    loadScript: loadScript,
    loadCSS: loadCSS,
    loadTabResources: loadTabResources,
    isTabLoaded: isTabLoaded,
  };
})();
