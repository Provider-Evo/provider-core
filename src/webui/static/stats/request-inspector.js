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

  // Pagination state
  var _currentPage = 1;
  var _pageSize = 7;

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
        _currentPage = 1;
        renderList();
        renderDetail();
      });
    }

    // Pagination controls
    var pageInput = document.getElementById('reqPageInput');
    var prevBtn = document.getElementById('reqPagePrev');
    var nextBtn = document.getElementById('reqPageNext');
    if (pageInput) {
      pageInput.addEventListener('change', function () {
        var val = parseInt(pageInput.value) || 1;
        var total = _getTotalPages();
        _currentPage = Math.max(1, Math.min(val, total));
        renderList();
      });
    }
    if (prevBtn) {
      prevBtn.addEventListener('click', function () {
        if (_currentPage > 1) { _currentPage--; renderList(); }
      });
    }
    if (nextBtn) {
      nextBtn.addEventListener('click', function () {
        if (_currentPage < _getTotalPages()) { _currentPage++; renderList(); }
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
        messages: msg.messages || [],
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
      _currentPage = 1;
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

  function _getFilteredItems() {
    var items = [];
    for (var i = 0; i < _order.length; i++) {
      var req = _requests[_order[i]];
      if (req && _matchFilter(req)) items.push(req);
    }
    return items;
  }

  function _getTotalPages() {
    var count = _getFilteredItems().length;
    return Math.max(1, Math.ceil(count / _pageSize));
  }

  function renderList() {
    var list = document.getElementById('requestList');
    if (!list) return;

    var filtered = _getFilteredItems();
    var totalItems = filtered.length;
    var totalPages = Math.max(1, Math.ceil(totalItems / _pageSize));

    // Clamp current page
    if (_currentPage > totalPages) _currentPage = totalPages;
    if (_currentPage < 1) _currentPage = 1;

    // Search input is always visible
    var searchInput = document.getElementById('requestSearchInput');
    if (searchInput) {
      searchInput.style.display = '';
    }

    // Show/hide pagination
    var pagination = document.getElementById('requestPagination');
    if (pagination) {
      pagination.style.display = totalPages > 1 ? '' : 'none';
    }

    // Update pagination controls
    var pageInput = document.getElementById('reqPageInput');
    var pageTotal = document.getElementById('reqPageTotal');
    var totalCount = document.getElementById('reqTotalCount');
    if (pageInput) { pageInput.value = _currentPage; pageInput.max = totalPages; }
    if (pageTotal) { pageTotal.textContent = '/' + totalPages; }
    if (totalCount) { totalCount.textContent = totalItems + ' 条'; }

    // Render current page items
    var start = (_currentPage - 1) * _pageSize;
    var end = Math.min(start + _pageSize, totalItems);
    var html = '';

    if (totalItems === 0) {
      html = '<div class="text-muted" style="padding:12px;text-align:center;">' +
        (_order.length > 0 ? 'No matching requests' : 'No requests yet') + '</div>';
    } else {
      for (var i = start; i < end; i++) {
        var req = filtered[i];
        var cls = 'req-item' + (_selectedId === req.id ? ' req-selected' : '');
        var statusCls = req.status === 'pending' ? 'req-pending' : (req.status >= 400 ? 'req-error' : 'req-ok');
        var time = new Date(req.ts * 1000);
        var ts = pad(time.getHours()) + ':' + pad(time.getMinutes()) + ':' + pad(time.getSeconds());
        var modelShort = (req.model || '').split('/').pop().split('-').slice(0, 2).join('-');
        var platformShort = (req.platform || '').charAt(0).toUpperCase() + (req.platform || '').slice(1);
        var latency = req.latency_ms !== null ? req.latency_ms + 'ms' : '...';
        html += '<div class="' + cls + '" data-req-id="' + req.id + '" onclick="RequestInspector.select(\'' + req.id + '\')">';
        html += '<span class="req-ts">' + ts + '</span>';
        html += '<span class="req-model">' + escapeHtml(modelShort) + '</span>';
        if (platformShort) html += '<span class="req-platform">' + escapeHtml(platformShort) + '</span>';
        html += '<span class="req-status ' + statusCls + '">' + (req.status === 'pending' ? '...' : req.status) + '</span>';
        html += '<span class="req-latency">' + latency + '</span>';
        html += '</div>';
      }
    }
    list.innerHTML = html;
  }

  function select(id) {
    _selectedId = id;
    renderList();
    showDetailModal(id);
  }

  function showDetailModal(id) {
    var req = _requests[id];
    if (!req) return;

    // Remove any existing modal
    var existing = document.getElementById('requestDetailModal');
    if (existing) existing.remove();

    var overlay = document.createElement('div');
    overlay.id = 'requestDetailModal';
    overlay.className = 'confirm-overlay';

    var html = '<div class="req-modal">';
    html += '<div class="req-modal-header">';
    html += '<div class="req-modal-title">Request ' + escapeHtml(req.id) + '</div>';
    html += '<button type="button" class="req-modal-close" aria-label="Close">&times;</button>';
    html += '</div>';

    // Status and metadata
    html += '<div class="req-modal-meta">';
    html += '<span class="req-status ' + (req.status >= 400 ? 'req-error' : 'req-ok') + '">';
    html += req.status === 'pending' ? 'In Progress' : 'Status ' + req.status;
    html += '</span>';
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
      html += '<div class="req-modal-section">';
      html += '<div class="req-modal-section-header">';
      html += '<div class="req-modal-label">Response (' + content.length + ' chars)</div>';
      html += '<button type="button" class="req-copy-btn" data-copy-target="response" title="复制">复制</button>';
      html += '</div>';
      html += '<pre class="req-modal-content" id="req-response-content">' + escapeHtml(content) + '</pre>';
      html += '</div>';
    } else if (req.status === 'pending') {
      html += '<div class="req-modal-section"><div class="text-muted" style="padding:12px;text-align:center;">Waiting for response...</div></div>';
    } else {
      html += '<div class="req-modal-section"><div class="text-muted" style="padding:12px;text-align:center;">No response content captured</div></div>';
    }

    // Request messages
    if (req.messages && req.messages.length > 0) {
      var messagesJson = JSON.stringify(req.messages, null, 2);
      html += '<div class="req-modal-section">';
      html += '<div class="req-modal-section-header">';
      html += '<div class="req-modal-label">Request Messages (' + req.messages.length + ')</div>';
      html += '<button type="button" class="req-copy-btn" data-copy-target="messages" title="复制">复制</button>';
      html += '</div>';
      html += '<pre class="req-modal-content" id="req-messages-content">' + escapeHtml(messagesJson) + '</pre>';
      html += '</div>';
    }

    html += '</div>';
    overlay.innerHTML = html;
    document.body.appendChild(overlay);

    requestAnimationFrame(function() { overlay.classList.add('is-visible'); });

    // Close handlers
    function closeModal() {
      overlay.classList.remove('is-visible');
      document.removeEventListener('keydown', escHandler);
      setTimeout(function() { overlay.remove(); }, 180);
    }

    function escHandler(e) {
      if (e.key === 'Escape') closeModal();
    }

    overlay.querySelector('.req-modal-close').addEventListener('click', closeModal);
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) closeModal();
    });
    document.addEventListener('keydown', escHandler);

    // Copy button handlers
    overlay.querySelectorAll('.req-copy-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var target = btn.dataset.copyTarget;
        var el = target === 'response'
          ? document.getElementById('req-response-content')
          : document.getElementById('req-messages-content');
        if (!el) return;
        var text = el.textContent || '';
        navigator.clipboard.writeText(text).then(function() {
          btn.textContent = '已复制';
          setTimeout(function() { btn.textContent = '复制'; }, 1500);
        }, function() {
          btn.textContent = '失败';
          setTimeout(function() { btn.textContent = '复制'; }, 1500);
        });
      });
    });
  }

  function renderDetail() {
    // Live-update the modal if it is currently open for the selected request
    var modal = document.getElementById('requestDetailModal');
    if (!modal || !_selectedId) return;
    var req = _requests[_selectedId];
    if (!req) return;

    // Update response content section
    var sections = modal.querySelectorAll('.req-modal-section');
    var content = req.content || req.chunks.join('');
    if (sections.length > 0) {
      var firstSection = sections[0];
      if (content) {
        firstSection.innerHTML = '<div class="req-modal-section-header">'
          + '<div class="req-modal-label">Response (' + content.length + ' chars)</div>'
          + '<button type="button" class="req-copy-btn" data-copy-target="response" title="复制">复制</button>'
          + '</div>'
          + '<pre class="req-modal-content" id="req-response-content">' + escapeHtml(content) + '</pre>';
        // Re-bind copy button
        var newBtn = firstSection.querySelector('.req-copy-btn');
        if (newBtn) {
          newBtn.addEventListener('click', function() {
            var el = document.getElementById('req-response-content');
            if (!el) return;
            navigator.clipboard.writeText(el.textContent || '').then(function() {
              newBtn.textContent = '已复制';
              setTimeout(function() { newBtn.textContent = '复制'; }, 1500);
            }, function() {
              newBtn.textContent = '失败';
              setTimeout(function() { newBtn.textContent = '复制'; }, 1500);
            });
          });
        }
      } else if (req.status === 'pending') {
        firstSection.innerHTML = '<div class="text-muted" style="padding:12px;text-align:center;">Waiting for response...</div>';
      }
    }

    // Update status badge in meta section
    var meta = modal.querySelector('.req-modal-meta');
    if (meta) {
      var statusSpan = meta.querySelector('.req-status');
      if (statusSpan) {
        statusSpan.className = 'req-status ' + (req.status >= 400 ? 'req-error' : 'req-ok');
        statusSpan.textContent = req.status === 'pending' ? 'In Progress' : 'Status ' + req.status;
      }
    }
  }

  function pad(n) { return n < 10 ? '0' + n : '' + n; }

  return { init: init, select: select };
})();
