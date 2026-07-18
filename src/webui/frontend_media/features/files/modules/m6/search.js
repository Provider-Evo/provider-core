/**
 * File Manager -- in-directory file search (search box, debounce, results
 * list, keyboard navigation, and click-to-navigate).
 *
 * Part of the files.js split. Depends on state.js (_searchInput,
 * _searchResults, _searchDebounceTimer, _searchAbortCtrl, _searchActiveIdx,
 * _escapeHtml, _fileIcon, _parentPath) and view/tabs.js (_getActiveTab,
 * _navigateTo).
 */

function _focusSearch() {
  if (_searchInput) {
    _searchInput.focus();
    _searchInput.select();
  }
}

function _clearSearch() {
  if (_searchInput) {
    _searchInput.value = '';
  }
  _hideSearchResults();
  if (_searchDebounceTimer) {
    clearTimeout(_searchDebounceTimer);
    _searchDebounceTimer = null;
  }
  if (_searchAbortCtrl) {
    _searchAbortCtrl.abort();
    _searchAbortCtrl = null;
  }
  // Remove has-query class from wrapper
  if (_searchInput && _searchInput.parentElement) {
    _searchInput.parentElement.classList.remove('has-query');
  }
}

function _hideSearchResults() {
  if (_searchResults) {
    _searchResults.classList.remove('visible');
  }
  _searchActiveIdx = -1;
}

function _debounceSearch(query, tab) {
  if (_searchDebounceTimer) {
    clearTimeout(_searchDebounceTimer);
    _searchDebounceTimer = null;
  }
  if (_searchAbortCtrl) {
    _searchAbortCtrl.abort();
    _searchAbortCtrl = null;
  }
  if (!query || query.length === 0) {
    _hideSearchResults();
    if (_searchResults) _searchResults.innerHTML = '';
    return;
  }
  _searchDebounceTimer = setTimeout(function () {
    _performSearch(query, tab);
  }, 300);
}

async function _performSearch(query, tab) {
  if (!_searchResults) return;

  // Show loading state
  _searchResults.innerHTML = '<div class="files-search-loading">Searching...</div>';
  _searchResults.classList.add('visible');
  _searchActiveIdx = -1;

  _searchAbortCtrl = new AbortController();
  var dirPath = tab.path || '/';

  try {
    var url = '/v1/webui/files/search?dir=' + encodeURIComponent(dirPath) +
      '&query=' + encodeURIComponent(query) + '&recursive=true&max_results=100';

    var resp = await fetch(url, { signal: _searchAbortCtrl.signal });
    var data = await resp.json();

    if (!resp.ok) {
      _searchResults.innerHTML = '<div class="files-search-empty">' + _escapeHtml(data.error || t('files.searchFailed')) + '</div>';
      return;
    }

    var results = data.results || [];
    _renderSearchResults(results, dirPath);
  } catch (e) {
    if (e.name === 'AbortError') return;
    _searchResults.innerHTML = '<div class="files-search-empty">' + t('files.searchError', { error: _escapeHtml(e.message) }) + '</div>';
  }
}

function _buildSearchResultItem(entry, searchDir) {
  var item = document.createElement('div');
  item.className = 'files-search-result';
  item.dataset.path = entry.path;
  item.dataset.isDir = entry.is_dir ? '1' : '0';

  var icon = document.createElement('span');
  icon.className = 'files-search-result-icon';
  icon.textContent = entry.is_dir ? '📁' : _fileIcon(entry.name);
  item.appendChild(icon);

  var info = document.createElement('div');
  info.className = 'files-search-result-info';

  var nameEl = document.createElement('div');
  nameEl.className = 'files-search-result-name';
  nameEl.textContent = entry.name;
  info.appendChild(nameEl);

  // Show relative path from search directory
  var relPath = _searchRelativePath(entry.path, searchDir);
  if (relPath) {
    var pathEl = document.createElement('div');
    pathEl.className = 'files-search-result-path';
    pathEl.textContent = relPath;
    info.appendChild(pathEl);
  }
  item.appendChild(info);

  item.addEventListener('click', function (ev) {
    ev.stopPropagation();
    _handleSearchResultClick(entry);
  });

  return item;
}

function _renderSearchResults(results, searchDir) {
  if (!_searchResults) return;
  _searchResults.innerHTML = '';
  _searchActiveIdx = -1;

  if (results.length === 0) {
    _searchResults.innerHTML = '<div class="files-search-empty">' + t('files.noSearchResults') + '</div>';
    _searchResults.classList.add('visible');
    return;
  }

  for (var i = 0; i < results.length; i++) {
    _searchResults.appendChild(_buildSearchResultItem(results[i], searchDir));
  }

  _searchResults.classList.add('visible');
}

function _searchRelativePath(filePath, searchDir) {
  // Normalise both paths to use forward slashes for comparison
  var normDir = (searchDir || '/').replace(/\\/g, '/').replace(/\/$/, '') || '/';
  var normPath = (filePath || '').replace(/\\/g, '/').replace(/\/$/, '');

  // Get parent directory of the result
  var lastSlash = normPath.lastIndexOf('/');
  var parentDir = lastSlash > 0 ? normPath.substring(0, lastSlash) : '/';

  if (parentDir === normDir || parentDir === searchDir) return null;

  // If parent starts with search dir, show relative
  var dirPrefix = normDir === '/' ? '/' : normDir + '/';
  if (normDir === '/' && parentDir !== '/') {
    return parentDir;
  }
  if (parentDir.indexOf(dirPrefix) === 0) {
    return parentDir.substring(dirPrefix.length);
  }

  return parentDir;
}

function _highlightSearchResultRow(entryPath) {
  var rows = _body ? _body.querySelectorAll('.files-table tbody tr') : [];
  for (var i = 0; i < rows.length; i++) {
    if (rows[i].dataset.path === entryPath) {
      rows[i].classList.add('selected');
      rows[i].scrollIntoView({ block: 'nearest' });
      break;
    }
  }
}

function _handleSearchResultClick(entry) {
  var tab = _getActiveTab();
  if (!tab) return;

  _hideSearchResults();

  if (entry.is_dir) {
    // Navigate into the directory
    _navigateTo(tab, entry.path);
  } else {
    // Navigate to parent directory, then highlight the file
    var parentDir = _parentPath(entry.path);
    if (!parentDir) parentDir = '/';

    _navigateTo(tab, parentDir);

    // Highlight the file after directory loads (wait for render)
    setTimeout(function () {
      _highlightSearchResultRow(entry.path);
    }, 200);
  }

  // Clear search after navigation
  _clearSearch();
}

function _navigateSearchResults(direction) {
  if (!_searchResults || !_searchResults.classList.contains('visible')) return;

  var items = _searchResults.querySelectorAll('.files-search-result');
  if (items.length === 0) return;

  // Remove active from current
  if (_searchActiveIdx >= 0 && _searchActiveIdx < items.length) {
    items[_searchActiveIdx].classList.remove('active');
  }

  _searchActiveIdx += direction;
  if (_searchActiveIdx < 0) _searchActiveIdx = items.length - 1;
  if (_searchActiveIdx >= items.length) _searchActiveIdx = 0;

  items[_searchActiveIdx].classList.add('active');
  items[_searchActiveIdx].scrollIntoView({ block: 'nearest' });
}
