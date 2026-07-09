/**
 * Core Router — 基于 hash 的 Tab 路由。
 *
 * 每个 feature 模块通过 Router.register(tabName, { render, activate, deactivate }) 注册。
 * 路由切换时自动调用 activate/deactivate 生命周期。
 */
var Router = (function () {
  var _routes = {};
  var _current = null;

  function register(tabName, handlers) {
    _routes[tabName] = handlers;
  }

  function navigate(tabName) {
    if (_current && _routes[_current] && _routes[_current].deactivate) {
      _routes[_current].deactivate();
    }
    _current = tabName;
    window.location.hash = '#/' + tabName;
    if (_routes[tabName] && _routes[tabName].activate) {
      _routes[tabName].activate();
    }
  }

  function current() { return _current; }

  function init() {
    var hash = window.location.hash.replace('#/', '') || '';
    if (hash && _routes[hash]) {
      navigate(hash);
    }
    window.addEventListener('hashchange', function () {
      var tab = window.location.hash.replace('#/', '');
      if (tab && tab !== _current && _routes[tab]) {
        navigate(tab);
      }
    });
  }

  return { register: register, navigate: navigate, current: current, init: init };
})();
