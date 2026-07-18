/**
 * File Manager -- file table rendering (sortable columns) and virtual
 * scrolling for large directories.
 *
 * Part of the files.js split. Depends on state.js. Calls into
 * dirlist.js (_navigateTo, _loadMore) and preview.js
 * (_previewFile) and menu.js (_showEntryContextMenu).
 */

function _sortEntries(tab) {
  var entries = tab.entries.slice();
  var col = tab.sortCol;
  var asc = tab.sortAsc;

  entries.sort(function (a, b) {
    // Dirs always first
    if (a.type !== b.type) return a.type === 'dir' ? -1 : 1;

    var va, vb;
    if (col === 'size') {
      va = a.size || 0; vb = b.size || 0;
    } else if (col === 'modified') {
      va = a.modified || 0; vb = b.modified || 0;
    } else {
      va = a.name.toLowerCase(); vb = b.name.toLowerCase();
    }

    if (va < vb) return asc ? -1 : 1;
    if (va > vb) return asc ? 1 : -1;
    return 0;
  });

  return entries;
}

function _tableColDef() {
  return [
    { key: 'name', label: t('files.name'), cls: '' },
    { key: 'size', label: t('files.size'), cls: 'file-size' },
    { key: 'modified', label: t('files.modified'), cls: 'file-modified' },
  ];
}

/**
 * Build a <table> containing just the sortable header row, shared by
 * both the normal table view and the virtual-scroll header.
 */
function _buildTableHeader(tab, onSortClick) {
  var headerTable = document.createElement('table');
  headerTable.className = 'files-table';

  var thead = document.createElement('thead');
  var headerRow = document.createElement('tr');
  var cols = _tableColDef();

  for (var c = 0; c < cols.length; c++) {
    var th = document.createElement('th');
    th.className = cols[c].cls;
    th.textContent = cols[c].label;

    if (tab.sortCol === cols[c].key) {
      var arrow = document.createElement('span');
      arrow.className = 'sort-arrow';
      arrow.textContent = tab.sortAsc ? '▲' : '▼';
      th.appendChild(arrow);
    }

    (function (colKey) {
      th.addEventListener('click', function () {
        if (tab.sortCol === colKey) {
          tab.sortAsc = !tab.sortAsc;
        } else {
          tab.sortCol = colKey;
          tab.sortAsc = true;
        }
        onSortClick();
      });
    })(cols[c].key);

    headerRow.appendChild(th);
  }
  thead.appendChild(headerRow);
  headerTable.appendChild(thead);
  return headerTable;
}

function _buildRowNameCell(entry) {
  var tdName = document.createElement('td');
  var nameCell = document.createElement('div');
  nameCell.className = 'file-name-cell';

  var icon = document.createElement('span');
  icon.className = 'file-icon';
  icon.textContent = entry.type === 'dir' ? '📁' : _fileIcon(entry.name);
  nameCell.appendChild(icon);

  var nameSpan = document.createElement('span');
  nameSpan.className = 'file-name' + (entry.type === 'dir' ? ' dir-name' : '');
  nameSpan.textContent = entry.name;
  nameCell.appendChild(nameSpan);

  tdName.appendChild(nameCell);
  return tdName;
}

function _buildRowDataCells(entry) {
  var tdSize = document.createElement('td');
  tdSize.className = 'file-size';
  tdSize.textContent = entry.type === 'file' ? _formatSize(entry.size) : '-';

  var tdMod = document.createElement('td');
  tdMod.className = 'file-modified';
  tdMod.textContent = _formatDate(entry.modified);

  return [tdSize, tdMod];
}

function _wireRowEvents(tr, entry, idx, tab) {
  tr.addEventListener('click', function () {
    _selectedIndex = idx;
    _lastSelectedPath = entry.path;
    if (entry.type === 'dir') {
      _navigateTo(tab, entry.path);
    } else {
      _previewFile(entry);
    }
  });
  tr.addEventListener('contextmenu', function (ev) {
    ev.preventDefault();
    _showEntryContextMenu(ev, tab, entry);
  });
}

function _buildRow(entry, idx, tab) {
  var tr = document.createElement('tr');
  tr.dataset.path = entry.path;
  tr.dataset.type = entry.type;

  if (_clipboard.action === 'cut' && _clipboard.paths.indexOf(entry.path) !== -1) {
    tr.className = 'files-row-cut';
  }
  if (idx === _selectedIndex) {
    tr.className = (tr.className ? tr.className + ' ' : '') + 'files-row-selected';
  }

  tr.appendChild(_buildRowNameCell(entry));
  var dataCells = _buildRowDataCells(entry);
  tr.appendChild(dataCells[0]);
  tr.appendChild(dataCells[1]);

  _wireRowEvents(tr, entry, idx, tab);

  return tr;
}

function _buildTable(tab) {
  var entries = _sortEntries(tab);
  var headerTable = _buildTableHeader(tab, function () { _renderContent(); });

  var tbody = document.createElement('tbody');
  for (var i = 0; i < entries.length; i++) {
    tbody.appendChild(_buildRow(entries[i], i, tab));
  }
  headerTable.appendChild(tbody);
  return headerTable;
}

/**
 * Build the scrollable inner container for virtual-scroll mode, plus a
 * closure that re-renders the currently visible row window.
 */
function _buildVsScrollContainer(tab, entries) {
  var scrollContainer = document.createElement('div');
  scrollContainer.className = 'files-virtual-scroll';
  tab._scrollContainer = scrollContainer; // saved for incremental lazy-load updates

  var inner = document.createElement('div');
  inner.className = 'files-virtual-scroll-inner';
  inner.style.height = (entries.length * _VS_ROW_HEIGHT) + 'px';

  var bodyTable = document.createElement('table');
  bodyTable.className = 'files-table';
  var tbody = document.createElement('tbody');
  bodyTable.appendChild(tbody);
  inner.appendChild(bodyTable);
  scrollContainer.appendChild(inner);

  function renderVisibleRows() {
    var scrollTop = scrollContainer.scrollTop;
    var containerHeight = scrollContainer.clientHeight || 500;
    var startIndex = Math.max(0, Math.floor(scrollTop / _VS_ROW_HEIGHT) - _VS_BUFFER);
    var visibleCount = Math.ceil(containerHeight / _VS_ROW_HEIGHT) + _VS_BUFFER * 2;
    var endIndex = Math.min(entries.length, startIndex + visibleCount);

    tbody.innerHTML = '';
    for (var i = startIndex; i < endIndex; i++) {
      var tr = _buildRow(entries[i], i, tab);
      tr.className = (tr.className ? tr.className + ' ' : '') + 'files-virtual-row';
      tr.style.top = (i * _VS_ROW_HEIGHT) + 'px';
      tr.style.height = _VS_ROW_HEIGHT + 'px';
      tbody.appendChild(tr);
    }
  }

  return { scrollContainer: scrollContainer, renderVisibleRows: renderVisibleRows };
}

function _wireVsScroll(scrollContainer, tab, renderVisibleRows) {
  var rafPending = false;
  scrollContainer.addEventListener('scroll', function () {
    if (!rafPending) {
      rafPending = true;
      requestAnimationFrame(function () {
        rafPending = false;
        renderVisibleRows();
      });
    }

    // Lazy-load trigger: when scrolling near the bottom of the scrollable area
    if (!tab._lazyAllLoaded && !tab._lazyLoadingMore) {
      var scrollBottom = scrollContainer.scrollTop + scrollContainer.clientHeight;
      var totalScrollHeight = scrollContainer.scrollHeight;
      if (scrollBottom >= totalScrollHeight - 500) {
        _loadMore(tab);
      }
    }
  });
}

function _buildVirtualScroll(tab) {
  var entries = _sortEntries(tab);

  var wrapper = document.createElement('div');
  wrapper.className = 'files-virtual-wrap';

  var headerTable = _buildTableHeader(tab, function () {
    _selectedIndex = -1;
    _renderContent();
  });
  wrapper.appendChild(headerTable);

  var vs = _buildVsScrollContainer(tab, entries);
  wrapper.appendChild(vs.scrollContainer);

  _wireVsScroll(vs.scrollContainer, tab, vs.renderVisibleRows);

  // Initial render after the container is in the DOM and has dimensions
  requestAnimationFrame(function () {
    vs.renderVisibleRows();
  });

  return wrapper;
}
