/**
 * Feature: 请求检查器 — 核心状态与 WebSocket 处理。
 *
 * Split across inspector_core.js / inspector_list.js / inspector_detail.js.
 * All three share a single `instance` state object (shared state object
 * pattern, mirrors base/core/tabbar/tabbar_core.js). The _attachXxxMethods
 * helper functions are defined as top-level globals in the other files and
 * are only invoked from inside create(), after all scripts have loaded, so
 * script load order between the three files does not matter as long as
 * inspector_core.js loads last (it wires everything together).
 *
 * Top-level helpers below (clipboard, WS connect/message handling, filter
 * binding) are kept outside the IIFE so the IIFE body itself stays short.
 */

// Clipboard helper with fallback for insecure contexts (HTTP).
function _inspectorCopyToClipboard(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text);
  }
  var textarea = document.createElement('textarea');
  textarea.value = text;
  textarea.style.position = 'fixed';
  textarea.style.left = '-9999px';
  textarea.style.top = '-9999px';
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  var success = false;
  try {
    success = document.execCommand('copy');
  } catch (e) {
    console.error('Copy failed:', e);
  }
  document.body.removeChild(textarea);
  return success ? Promise.resolve() : Promise.reject(new Error('Copy failed'));
}

function _inspectorPad(n) { return n < 10 ? '0' + n : '' + n; }

function _inspectorFormatTime(ts, padFn) {
  if (ts == null || !isFinite(ts)) return '--:--:--';
  var time = new Date(ts * 1000);
  if (isNaN(time.getTime())) return '--:--:--';
  return padFn(time.getHours()) + ':' + padFn(time.getMinutes()) + ':' + padFn(time.getSeconds());
}

function _inspectorFormatDateTime(ts) {
  if (ts == null || !isFinite(ts)) return '--';
  var time = new Date(ts * 1000);
  if (isNaN(time.getTime())) return '--';
  return time.toLocaleString();
}

function _inspectorRequestContent(req) {
  if (!req) return '';
  if (req.content) return req.content;
  if (req.response) return req.response;
  if (req.chunks && req.chunks.length) return req.chunks.join('');
  return '';
}

function _inspectorApplyResponse(req, responseText) {
  if (!req || !responseText) return;
  req.content = responseText;
  req.response = responseText;
  req.chunks = [responseText];
}

function _inspectorInit(instance) {
  var panel = document.getElementById('requestInspector');
  if (!panel) return;
  _inspectorConnect(instance);
  _inspectorBindFilters(instance);
  // No polling needed — WebSocket messages trigger renderList() via handleMessage()
}

function _inspectorBindFilters(instance) {
  if (instance._bound) return;
  instance._bound = true;
  _inspectorBindFilterInputs(instance);
  _inspectorBindPaginationControls(instance);
}

/**
 * Bind the search/status/time filter inputs and the clear button.
 * Split out of _inspectorBindFilters to keep it under the line cap.
 */
function _inspectorBindFilterInputs(instance) {
  var searchInput = document.getElementById('requestSearchInput');
  var statusFilter = document.getElementById('requestStatusFilter');
  var timeFilter = document.getElementById('requestTimeFilter');
  var clearBtn = document.getElementById('requestClearBtn');

  if (searchInput) {
    searchInput.addEventListener('input', function () {
      instance._searchText = searchInput.value.toLowerCase();
      instance.renderList();
    });
  }
  if (statusFilter) {
    statusFilter.addEventListener('change', function () {
      instance._statusFilter = statusFilter.value;
      instance.renderList();
    });
  }
  if (timeFilter) {
    timeFilter.addEventListener('change', function () {
      instance._timeFilter = parseInt(timeFilter.value) || 0;
      instance.renderList();
    });
  }
  if (clearBtn) {
    clearBtn.addEventListener('click', function () {
      instance._requests = {};
      instance._order = [];
      instance._selectedId = null;
      instance._currentPage = 1;
      instance.renderList();
      instance.renderDetail();
    });
  }
}

/**
 * Bind the previous/next pagination buttons.
 * Split out of _inspectorBindFilters to keep it under the line cap.
 */
function _inspectorBindPaginationControls(instance) {
  var prevBtn = document.getElementById('reqPagePrev');
  var nextBtn = document.getElementById('reqPageNext');
  if (prevBtn) {
    prevBtn.addEventListener('click', function () {
      if (instance._currentPage > 1) { instance._currentPage--; instance.renderList(); }
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener('click', function () {
      if (instance._currentPage < instance._getTotalPages()) {
        instance._currentPage++;
        instance.renderList();
      }
    });
  }
}

function _inspectorConnect(instance) {
  if (instance._ws && (instance._ws.readyState === WebSocket.CONNECTING || instance._ws.readyState === WebSocket.OPEN)) return;
  var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  instance._ws = new WebSocket(proto + '//' + location.host + '/v1/webui/ws/requests');
  instance._ws.onopen = function () {
    var notice = document.getElementById('requestWsNotice');
    if (notice) notice.textContent = 'WebSocket: connected';
  };
  instance._ws.onmessage = function (e) {
    try { _inspectorHandleMessage(instance, JSON.parse(e.data)); } catch (err) {}
  };
  instance._ws.onclose = function () {
    var notice = document.getElementById('requestWsNotice');
    if (notice) notice.textContent = 'WebSocket: disconnected';
    if (!document.hidden) {
      setTimeout(function () { _inspectorConnect(instance); }, 3000);
    }
  };
  instance._ws.onerror = function () {};
}

function _inspectorHandleMessage(instance, msg) {
  if (msg.type === 'request_start') {
    _inspectorHandleRequestStart(instance, msg);
  } else if (msg.type === 'request_chunk') {
    _inspectorHandleRequestChunk(instance, msg);
  } else if (msg.type === 'request_end') {
    _inspectorHandleRequestEnd(instance, msg);
  }
  instance.renderList();
  if (instance._selectedId === msg.id) instance.renderDetail();
}

function _inspectorHandleRequestStart(instance, msg) {
  instance._requests[msg.id] = {
    id: msg.id, ts: msg.ts, model: msg.model || '',
    messages_count: msg.messages_count || 0,
    messages: msg.messages || [],
    has_tools: msg.has_tools || false,
    stream: msg.stream || false,
    status: 'pending', latency_ms: null, platform: '',
    chunks: [], content: ''
  };
  instance._order.unshift(msg.id);
  if (instance._order.length > instance._maxItems) {
    var old = instance._order.pop();
    delete instance._requests[old];
  }
  instance._currentPage = 1;
}

function _inspectorHandleRequestChunk(instance, msg) {
  var req = instance._requests[msg.id];
  if (req) {
    req.chunks.push(msg.delta || '');
    req.content += (msg.delta || '');
  }
}

/**
 * Handle a request_end WS message: either create a history-sourced record
 * directly (no matching in-memory request), or finalize the existing one.
 * Split out of _inspectorHandleMessage to keep it under the line cap.
 */
function _inspectorHandleRequestEnd(instance, msg) {
  var req = instance._requests[msg.id];
  var responseText = msg.response || '';
  if (!req) {
    // History entry from SQLite — create record directly
    req = {
      id: msg.id, ts: msg.ts, model: msg.model || '',
      messages_count: msg.messages_count || 0,
      messages: msg.messages || [],
      has_tools: msg.has_tools || false,
      stream: msg.stream || false,
      status: msg.status, latency_ms: msg.latency_ms,
      platform: msg.platform || '',
      chunks: responseText ? [responseText] : [],
      content: responseText,
      response: responseText
    };
    instance._requests[msg.id] = req;
    instance._order.unshift(msg.id);
    if (instance._order.length > instance._maxItems) {
      var old = instance._order.pop();
      delete instance._requests[old];
    }
  } else {
    req.status = msg.status;
    req.latency_ms = msg.latency_ms;
    req.platform = msg.platform || '';
    if (msg.ts != null && isFinite(msg.ts)) req.ts = msg.ts;
    req.model = req.model || msg.model || '';
    if (msg.messages && msg.messages.length) req.messages = msg.messages;
    if (msg.messages_count) req.messages_count = msg.messages_count;
    if (responseText) _inspectorApplyResponse(req, responseText);
  }
}

function _inspectorCreate() {
  var instance = {
    _ws: null,
    _requests: {},   // id -> request data
    _order: [],      // id order (newest first)
    _selectedId: null,
    _maxItems: 200,

    // Filter state
    _searchText: '',
    _statusFilter: '',
    _timeFilter: 0,  // seconds, 0 = all

    // Pagination state
    _currentPage: 1,
    _pageSize: 7,
    _bound: false,

    _requestContent: _inspectorRequestContent,
    _applyResponse: _inspectorApplyResponse,
    copyToClipboard: _inspectorCopyToClipboard,
    pad: _inspectorPad,
  };

  _attachListMethods(instance);
  _attachDetailMethods(instance);

  instance.init = function () { _inspectorInit(instance); };
  instance.select = function (id) { instance._select(id); };

  return instance;
}

var RequestInspector = (function () {
  var instance = _inspectorCreate();
  return { init: instance.init, select: instance.select };
})();
