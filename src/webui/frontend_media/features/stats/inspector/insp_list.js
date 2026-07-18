/**
 * RequestInspector list rendering and filtering.
 *
 * Attaches _matchFilter / _getFilteredItems / _getTotalPages / renderList
 * onto the shared instance created in inspector_core.js. See that file's
 * header comment for the overall split rationale.
 */
function _attachListMethods(instance) {
  _attachListMethodsSubFilter(instance);
  _attachListMethodsSubRenderItems(instance);
  _attachListMethodsSubPagination(instance);
  _attachListMethodsSubRenderList(instance);
}

function _attachListMethodsSubFilter(instance) {

  instance._matchFilter = function (req) {
    // Time filter
    if (instance._timeFilter > 0) {
      var cutoff = Date.now() / 1000 - instance._timeFilter;
      if (req.ts < cutoff) return false;
    }
    // Status filter
    if (instance._statusFilter) {
      if (instance._statusFilter === 'pending' && req.status !== 'pending') return false;
      if (instance._statusFilter === '200' && req.status !== 200) return false;
      if (instance._statusFilter === '4xx' && (req.status < 400 || req.status >= 500)) return false;
      if (instance._statusFilter === '5xx' && (req.status < 500 || req.status >= 600)) return false;
    }
    // Text search
    if (instance._searchText) {
      var haystack = ((req.model || '') + ' ' + (req.platform || '') + ' ' + req.id).toLowerCase();
      if (haystack.indexOf(instance._searchText) === -1) return false;
    }
    return true;
  };

  instance._getFilteredItems = function () {
    var items = [];
    for (var i = 0; i < instance._order.length; i++) {
      var req = instance._requests[instance._order[i]];
      if (req && instance._matchFilter(req)) items.push(req);
    }
    return items;
  };

  instance._getTotalPages = function () {
    var count = instance._getFilteredItems().length;
    return Math.max(1, Math.ceil(count / instance._pageSize));
  };

}

function _attachListMethodsSubRenderItems(instance) {

  instance._renderListItemsHtml = function (filtered, start, end) {
    var html = '';
    for (var i = start; i < end; i++) {
      var req = filtered[i];
      var cls = 'req-item' + (instance._selectedId === req.id ? ' req-selected' : '');
      var statusCls = req.status === 'pending' ? 'req-pending' : (req.status >= 400 ? 'req-error' : 'req-ok');
      var time = new Date(req.ts * 1000);
      var ts = instance.pad(time.getHours()) + ':' + instance.pad(time.getMinutes()) + ':' + instance.pad(time.getSeconds());
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
    return html;
  };
}

function _attachListMethodsSubPagination(instance) {

  instance._updatePaginationControls = function (totalItems, totalPages) {
    var pagination = document.getElementById('requestPagination');
    if (pagination) {
      pagination.style.display = totalPages > 1 ? '' : 'none';
    }

    var pageInput = document.getElementById('reqPageInput');
    var pageTotal = document.getElementById('reqPageTotal');
    var totalCount = document.getElementById('reqTotalCount');
    if (pageInput) { pageInput.textContent = instance._currentPage; }
    if (pageTotal) { pageTotal.textContent = '/' + totalPages; }
    if (totalCount) { totalCount.textContent = t('requests.totalCount', { count: totalItems }); }
  };
}

function _attachListMethodsSubRenderList(instance) {

  instance.renderList = function () {
    var list = document.getElementById('requestList');
    if (!list) return;

    var filtered = instance._getFilteredItems();
    var totalItems = filtered.length;
    var totalPages = Math.max(1, Math.ceil(totalItems / instance._pageSize));

    // Clamp current page
    if (instance._currentPage > totalPages) instance._currentPage = totalPages;
    if (instance._currentPage < 1) instance._currentPage = 1;

    // Search input is always visible
    var searchInput = document.getElementById('requestSearchInput');
    if (searchInput) {
      searchInput.style.display = '';
    }

    instance._updatePaginationControls(totalItems, totalPages);

    // Render current page items
    var start = (instance._currentPage - 1) * instance._pageSize;
    var end = Math.min(start + instance._pageSize, totalItems);
    var html = '';

    if (totalItems === 0) {
      html = '<div class="text-muted" style="padding:12px;text-align:center;">' +
        (instance._order.length > 0 ? 'No matching requests' : 'No requests yet') + '</div>';
    } else {
      html = instance._renderListItemsHtml(filtered, start, end);
    }
    list.innerHTML = html;
  };
}
