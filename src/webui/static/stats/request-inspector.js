/**
 * Feature: 请求检查器 — 实时显示 API 请求和响应。
 * 支持搜索、状态筛选、时间范围筛选、详细视图。
 */
var RequestInspector = (function () {
  var _ws = null;
  var _requests = {};  // id -> request data
  var _order = [];     // id order (newest first)
  var _selectedId = null;
  var _maxItems = 200;

  // Filter state
  var _searchText = '';
  var _statusFilter = '';
  var _timeFilter = 0;  // seconds, 0 = all

  function init() {
    var panel = document.getElementById('requestInspector');
    if (!panel) return;
    connect();
    bindFilters();
    setInterval(function () {
      var tab = document.getElementById('tab-stats');
      if (tab && tab.classList.contains('active')) {
        renderList();
      }
    }, 2000);
  }

  function bindFilters() {
    var searchInput = document.getElementById('requestSearchInput');
    var statusFilter = document.getElementById('requestStatusFilter');
    var timeFilter = document.getElementById('requestTimeFilter');
    var clearBtn = document.getElementById('requestClearBtn');

    if (searchInput) {
      searchInput.addEventListener('input', function () {
        _searchText = searchInput.value.toLowerCase();
        renderList();
      });
    }
    if (statusFilter) {
      statusFilter.addEventListener('change', function () {
        _statusFilter = statusFilter.value;
        renderList();
      });
    }
    if (timeFilter) {
      timeFilter.addEventListener('change', function () {
        _timeFilter = parseInt(timeFilter.value) || 0;
        renderList();
      });
    }
    if (clearBtn) {
      clearBtn.addEventListener('click', function () {
        _requests = {};
        _order = [];
        _selectedId = null;
        renderList();
        renderDetail();
      });
    }
  }

  function connect() {
    if (_ws && (_ws.readyState === WebSocket.CONNECTING || _ws.readyState === WebSocket.OPEN)) return;
    var proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    _ws = new WebSocket(proto + '//' + location.host + '/v1/webui/ws/requests');
    _ws.onopen = function () {
      var notice = document.getElementById('requestWsNotice');
      if (notice) notice.textContent = 'WebSocket: connected';
    };
    _ws.onmessage = function (e) {
      try { handleMessage(JSON.parse(e.data)); } catch (err) {}
    };
    _ws.onclose = function () {
      var notice = document.getElementById('requestWsNotice');
      if (notice) notice.textContent = 'WebSocket: disconnected';
      setTimeout(connect, 3000);
    };
    _ws.onerror = function () {};
  }

  function handleMessage(msg) {
    if (msg.type === 'request_start') {
      _requests[msg.id] = {
        id: msg.id, ts: msg.ts, model: msg.model || '',
        messages_count: msg.messages_count || 0,
        has_tools: msg.has_tools || false,
        stream: msg.stream || false,
        status: 'pending', latency_ms: null, platform: '',
        chunks: [], content: ''
      };
      _order.unshift(msg.id);
      if (_order.length > _maxItems) {
        var old = _order.pop();
        delete _requests[old];
      }
    } else if (msg.type === 'request_chunk') {
      var req = _requests[msg.id];
      if (req) {
        req.chunks.push(msg.delta || '');
        req.content += (msg.delta || '');
        if (_selectedId === msg.id) renderDetail();
      }
    } else if (msg.type === 'request_end') {
      var req = _requests[msg.id];
      if (req) {
        req.status = msg.status;
        req.latency_ms = msg.latency_ms;
        req.platform = msg.platform || '';
        req.model = req.model || msg.model || '';
      }
    }
    renderList();
    if (_selectedId === msg.id) renderDetail();
  }

  function _matchFilter(req) {
    // Time filter
    if (_timeFilter > 0) {
      var cutoff = Date.now() / 1000 - _timeFilter;
      if (req.ts < cutoff) return false;
    }
    // Status filter
    if (_statusFilter) {
      if (_statusFilter === 'pending' && req.status !== 'pending') return false;
      if (_statusFilter === '200' && req.status !== 200) return false;
      if (_statusFilter === '4xx' && (req.status < 400 || req.status >= 500)) return false;
      if (_statusFilter === '5xx' && (req.status < 500 || req.status >= 600)) return false;
    }
    // Text search
    if (_searchText) {
      var haystack = ((req.model || '') + ' ' + (req.platform || '') + ' ' + req.id).toLowerCase();
      if (haystack.indexOf(_searchText) === -1) return false;
    }
    return true;
  }

  function renderList() {
    var list = document.getElementById('requestList');
    if (!list) return;
    var html = '';
    var visibleCount = 0;
    for (var i = 0; i < _order.length; i++) {
      var req = _requests[_order[i]];
      if (!req || !_matchFilter(req)) continue;
      visibleCount++;
      var cls = 'req-item' + (_selectedId === req.id ? ' req-selected' : '');
      var statusCls = req.status === 'pending' ? 'req-pending' : (req.status >= 400 ? 'req-error' : 'req-ok');
      var time = new Date(req.ts * 1000);
      var ts = pad(time.getHours()) + ':' + pad(time.getMinutes()) + ':' + pad(time.getSeconds());
      var modelShort = (req.model || '').split('/').pop().split('-').slice(0, 2).join('-');
      var latency = req.latency_ms !== null ? req.latency_ms + 'ms' : '...';
      html += '<div class="' + cls + '" data-req-id="' + req.id + '" onclick="RequestInspector.select(\'' + req.id + '\')">';
      html += '<span class="req-ts">' + ts + '</span>';
      html += '<span class="req-model">' + escapeHtml(modelShort) + '</span>';
      html += '<span class="req-status ' + statusCls + '">' + (req.status === 'pending' ? '...' : req.status) + '</span>';
      html += '<span class="req-latency">' + latency + '</span>';
      html += '</div>';
    }
    list.innerHTML = html || '<div class="text-muted" style="padding:12px;text-align:center;">' +
      (_order.length > 0 ? 'No matching requests' : 'No requests yet') + '</div>';
  }

  function select(id) {
    _selectedId = id;
    renderList();
    renderDetail();
  }

  function renderDetail() {
    var detail = document.getElementById('requestDetail');
    if (!detail || !_selectedId) return;
    var req = _requests[_selectedId];
    if (!req) { detail.innerHTML = ''; return; }

    var html = '<div class="req-detail">';
    html += '<div class="req-detail-header">';
    html += '<strong style="font-size:13px;">Request ' + req.id + '</strong>';
    html += '<span class="req-status ' + (req.status >= 400 ? 'req-error' : 'req-ok') + '">' + (req.status === 'pending' ? 'In Progress' : 'Status ' + req.status) + '</span>';
    html += '</div>';

    // Meta info
    html += '<div class="req-detail-meta">';
    html += '<span>Model: <strong>' + escapeHtml(req.model || 'unknown') + '</strong></span>';
    html += '<span>Platform: <strong>' + escapeHtml(req.platform || 'unknown') + '</strong></span>';
    html += '<span>Messages: ' + req.messages_count + '</span>';
    html += '<span>Tools: ' + (req.has_tools ? 'yes' : 'no') + '</span>';
    html += '<span>Stream: ' + (req.stream ? 'yes' : 'no') + '</span>';
    if (req.latency_ms !== null) html += '<span>Latency: <strong>' + req.latency_ms + 'ms</strong></span>';
    var time = new Date(req.ts * 1000);
    html += '<span>Time: ' + time.toLocaleString() + '</span>';
    html += '</div>';

    // Response content
    var content = req.content || req.chunks.join('');
    if (content) {
      html += '<div class="req-detail-section">';
      html += '<div class="req-detail-label">Response (' + content.length + ' chars)</div>';
      html += '<pre class="req-detail-content">' + escapeHtml(content) + '</pre>';
      html += '</div>';
    } else if (req.status === 'pending') {
      html += '<div class="req-detail-section"><div class="text-muted" style="padding:8px;">Waiting for response...</div></div>';
    } else {
      html += '<div class="req-detail-section"><div class="text-muted" style="padding:8px;">No response content captured</div></div>';
    }

    html += '</div>';
    detail.innerHTML = html;
  }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  return { init: init, select: select };
})();
