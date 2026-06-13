/**
 * Core API — 统一的 fetch 封装与后端通信。
 * 所有 feature 模块通过 Api 对象与后端交互。
 */
var Api = (function () {
  var _timeout = 30000;

  function setTimeout_(ms) { _timeout = ms; }

  async function fetchJson(url, options) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, _timeout);
    try {
      var resp = await fetch(url, Object.assign({ signal: controller.signal }, options || {}));
      if (!resp.ok) throw new Error(resp.status + ' ' + resp.statusText);
      return await resp.json();
    } finally {
      clearTimeout(timer);
    }
  }

  async function post(url, body) {
    return fetchJson(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  async function put(url, body) {
    return fetchJson(url, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  return { setTimeout: setTimeout_, fetchJson: fetchJson, post: post, put: put };
})();
