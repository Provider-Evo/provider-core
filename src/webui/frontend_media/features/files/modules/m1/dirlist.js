/**
 * File Manager -- directory loading, lazy pagination, and navigation history.
 *
 * Part of the files.js split. Depends on state.js. Calls into
 * render.js (_renderContent), table.js (_sortEntries, _buildRow),
 * and tabs.js (_saveSession).
 */

async function _loadDirectory(tab, path) {
  tab.loading = true;
  tab._lazyOffset = 0;
  tab._lazyLoadingMore = false;
  tab._lazyAllLoaded = false;
  _renderContent();

  try {
    var url = '/v1/webui/files/list?path=' + encodeURIComponent(path) +
      '&offset=0&limit=' + tab._lazyLimit;
    var data = await Api.fetchJson(url);
    tab.entries = data.entries || [];
    tab.path = data.path || path;
    tab.isDrives = !!data.isDrives;
    tab.name = _pathDisplayName(tab.path);
    tab.loading = false;
    tab._lazyOffset = tab.entries.length;
    tab._lazyTotal = (data.total != null) ? data.total : tab.entries.length;
    tab._lazyLimit = (data.limit != null) ? data.limit : 200;
    tab._lazyAllLoaded = (tab._lazyOffset >= tab._lazyTotal);
    if (_bar) _bar.setTitle(tab.id, tab.name);
    _renderContent();
  } catch (e) {
    tab.loading = false;
    tab.entries = [];
    tab._lazyAllLoaded = true;
    tab._lazyTotal = 0;
    _renderContent();
    if (typeof toast === 'function') toast(t('files.loadDirFailed', { error: e.message }), 'error');
  }
}

/**
 * Load the next batch of entries for lazy-loading large directories.
 * Appends to tab.entries and updates the virtual scroll incrementally.
 */
async function _loadMore(tab) {
  if (tab._lazyLoadingMore || tab._lazyAllLoaded) return;
  if (tab._lazyOffset >= tab._lazyTotal) {
    tab._lazyAllLoaded = true;
    return;
  }

  tab._lazyLoadingMore = true;
  _showLazyLoadingIndicator(tab);

  try {
    var url = '/v1/webui/files/list?path=' + encodeURIComponent(tab.path) +
      '&offset=' + tab._lazyOffset + '&limit=' + tab._lazyLimit;
    var data = await Api.fetchJson(url);
    var newEntries = data.entries || [];
    tab.entries = tab.entries.concat(newEntries);
    tab._lazyOffset += newEntries.length;
    tab._lazyTotal = (data.total != null) ? data.total : tab._lazyOffset;
    tab._lazyAllLoaded = (tab._lazyOffset >= tab._lazyTotal);
    tab._lazyLoadingMore = false;
    _hideLazyLoadingIndicator(tab);
    _updateAfterLoadMore(tab);
  } catch (e) {
    tab._lazyLoadingMore = false;
    _hideLazyLoadingIndicator(tab);
    if (typeof toast === 'function') toast(t('files.loadMoreFailed', { error: e.message }), 'error');
  }
}

/**
 * Update the DOM after new entries have been appended via lazy loading.
 * Preserves scroll position. Switches to virtual scroll if the entry
 * count has crossed the virtual-scroll threshold.
 */
function _updateAfterLoadMore(tab) {
  var listArea = _body ? _body.querySelector('.files-list-area') : null;
  if (!listArea) {
    _renderContent();
    return;
  }

  var wasVirtual = tab.entries.length - (tab._lazyLimit || 200) > _VS_THRESHOLD;
  var nowVirtual = tab.entries.length > _VS_THRESHOLD;

  if (wasVirtual !== nowVirtual) {
    // Rendering mode changed — full re-render preserving scroll position
    var savedScroll = listArea.scrollTop;
    _renderContent();
    var newListArea = _body ? _body.querySelector('.files-list-area') : null;
    if (newListArea) newListArea.scrollTop = savedScroll;
  } else if (nowVirtual && tab._scrollContainer) {
    // Incremental update for virtual scroll — no full re-render needed
    var entries = _sortEntries(tab);
    var totalHeight = entries.length * _VS_ROW_HEIGHT;
    var inner = tab._scrollContainer.querySelector('.files-virtual-scroll-inner');
    if (inner) inner.style.height = totalHeight + 'px';
    // Re-render visible rows to include new entries
    var scrollTop = tab._scrollContainer.scrollTop;
    var containerHeight = tab._scrollContainer.clientHeight || 500;
    var startIndex = Math.max(0, Math.floor(scrollTop / _VS_ROW_HEIGHT) - _VS_BUFFER);
    var visibleCount = Math.ceil(containerHeight / _VS_ROW_HEIGHT) + _VS_BUFFER * 2;
    var endIndex = Math.min(entries.length, startIndex + visibleCount);
    var tbody = tab._scrollContainer.querySelector('.files-table tbody');
    if (tbody) {
      tbody.innerHTML = '';
      for (var i = startIndex; i < endIndex; i++) {
        var tr = _buildRow(entries[i], i, tab);
        tr.className = (tr.className ? tr.className + ' ' : '') + 'files-virtual-row';
        tr.style.top = (i * _VS_ROW_HEIGHT) + 'px';
        tr.style.height = _VS_ROW_HEIGHT + 'px';
        tbody.appendChild(tr);
      }
    }
  } else {
    // Normal table mode — full re-render (fast for <200 entries)
    var savedScroll2 = listArea.scrollTop;
    _renderContent();
    var newListArea2 = _body ? _body.querySelector('.files-list-area') : null;
    if (newListArea2) newListArea2.scrollTop = savedScroll2;
  }
}

/**
 * Show a small loading indicator at the bottom of the file list area.
 */
function _showLazyLoadingIndicator(tab) {
  if (!_body) return;
  var existing = _body.querySelector('.files-lazy-loading');
  if (existing) return;
  var listArea = _body.querySelector('.files-list-area');
  if (!listArea) return;
  var indicator = document.createElement('div');
  indicator.className = 'files-lazy-loading';
  indicator.textContent = t('files.loadMore');
  listArea.appendChild(indicator);
}

/**
 * Remove the lazy-loading indicator from the file list area.
 */
function _hideLazyLoadingIndicator(tab) {
  if (!_body) return;
  var indicator = _body.querySelector('.files-lazy-loading');
  if (indicator) indicator.remove();
}

function _navigateTo(tab, path, pushHistory) {
  if (pushHistory !== false) {
    // Trim forward history and push
    tab.history = tab.history.slice(0, tab.historyIdx + 1);
    tab.history.push(path);
    tab.historyIdx = tab.history.length - 1;
  }
  _loadDirectory(tab, path);
  _saveSession();
}

function _goBack(tab) {
  if (tab.historyIdx > 0) {
    tab.historyIdx--;
    _loadDirectory(tab, tab.history[tab.historyIdx]);
  }
}

function _goForward(tab) {
  if (tab.historyIdx < tab.history.length - 1) {
    tab.historyIdx++;
    _loadDirectory(tab, tab.history[tab.historyIdx]);
  }
}

function _goUp(tab) {
  var parent = _parentPath(tab.path);
  if (parent === tab.path) return; // already at root, nowhere to go
  _navigateTo(tab, parent);
}
