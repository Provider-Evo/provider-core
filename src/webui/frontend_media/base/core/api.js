/**
 * Parse an error body from a failed fetch response into an Error message.
 * Split out of the Api IIFE to keep fetchJson's caller under the line cap.
 */
async function _apiReadErrorMessage(resp) {
  var errBody = null;
  try {
    errBody = await resp.json();
  } catch (_e) {
    errBody = null;
  }
  return (errBody && errBody.error) ? String(errBody.error) : (resp.status + ' ' + resp.statusText);
}

/**
 * Parse the JSON body of a postForm response, tolerating non-JSON bodies.
 * Split out of the Api IIFE to keep postForm under the line cap.
 */
async function _apiReadFormResponseData(resp) {
  try {
    return await resp.json();
  } catch (_e) {
    return null;
  }
}

/**
 * POST/PUT JSON helpers built on top of Api.fetchJson.
 * Split out of the Api IIFE to keep it under the line cap.
 */
function _apiPostJson(fetchJson, url, body) {
  return fetchJson(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

function _apiPutJson(fetchJson, url, body) {
  return fetchJson(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

/**
 * multipart/form-data POST helper. Split out of the Api IIFE to keep it
 * under the line cap.
 */
async function _apiPostForm(getTimeout, url, formData) {
  var controller = new AbortController();
  var timer = setTimeout(function () { controller.abort(); }, getTimeout());
  try {
    var resp = await fetch(url, {
      method: 'POST',
      body: formData,
      signal: controller.signal,
    });
    var data = await _apiReadFormResponseData(resp);
    if (!resp.ok) {
      var msg = (data && data.error) ? data.error : (resp.status + ' ' + resp.statusText);
      var err = new Error(msg);
      err.status = resp.status;
      err.data = data;
      throw err;
    }
    return data;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Core API — 统一的 fetch 封装与后端通信。
 * 所有 feature 模块通过 Api 对象与后端交互。
 */
var Api = (function () {
  var _timeout = 30000;

  function setTimeout_(ms) { _timeout = ms; }
  function getTimeout_() { return _timeout; }

  async function fetchJson(url, options) {
    var controller = new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, _timeout);
    try {
      var resp = await fetch(url, Object.assign({ signal: controller.signal, credentials: 'same-origin' }, options || {}));
      if (!resp.ok) {
        throw new Error(await _apiReadErrorMessage(resp));
      }
      return await resp.json();
    } finally {
      clearTimeout(timer);
    }
  }

  function post(url, body) { return _apiPostJson(fetchJson, url, body); }
  function put(url, body) { return _apiPutJson(fetchJson, url, body); }
  function postForm(url, formData) { return _apiPostForm(getTimeout_, url, formData); }

  return {
    setTimeout: setTimeout_,
    fetchJson: fetchJson,
    post: post,
    put: put,
    postForm: postForm,
  };
})();
