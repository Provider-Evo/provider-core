/**
 * File Manager -- main content rendering: list-area container (table vs
 * virtual scroll) and lazy-load scroll trigger wiring.
 *
 * Part of the files.js split. Depends on state.js. Calls into
 * table.js (_buildTable, _buildVirtualScroll), dirlist.js
 * (_loadMore), toolbar.js (_buildToolbar), upload.js (_setupDragDrop).
 */

function _renderContent() {
  if (!_body) return;
  _body.innerHTML = '';

  var tab = _getActiveTab();
  if (!tab) {
    _body.innerHTML =
      '<div class="files-empty">' +
      '<div class="files-empty-icon">&#128193;</div>' +
      '<div class="files-empty-text">' + t('files.noOpenTabs') + '</div>' +
      '</div>';
    return;
  }

  // Toolbar
  var toolbar = _buildToolbar(tab);
  _body.appendChild(toolbar);

  // File list area
  var listArea = _buildListArea(tab);
  _body.appendChild(listArea);
  _wireLazyLoadScrollTrigger(listArea, tab);

  // Drag-and-drop upload support on the list area
  _setupDragDrop(listArea, tab);

  _body.style.display = 'flex';
  _body.style.flexDirection = 'column';
}

function _buildListArea(tab) {
  var listArea = document.createElement('div');
  listArea.className = 'files-list-area';
  listArea.style.cssText = 'flex:1;min-height:0;';

  if (tab.loading) {
    listArea.innerHTML = '<div class="files-loading">' + t('files.loading') + '</div>';
    tab._scrollContainer = null;
  } else if (tab.entries.length === 0) {
    listArea.innerHTML = '<div class="files-empty"><div class="files-empty-text">' + t('files.emptyDir') + '</div></div>';
    tab._scrollContainer = null;
  } else if (tab.entries.length > _VS_THRESHOLD) {
    listArea.appendChild(_buildVirtualScroll(tab));
  } else {
    tab._scrollContainer = null; // no virtual scroll — use full re-render on load-more
    listArea.appendChild(_buildTable(tab));
  }

  return listArea;
}

/**
 * Lazy-load scroll trigger for normal (non-virtual) table mode.
 * Virtual scroll mode wires its own trigger inside table.js.
 */
function _wireLazyLoadScrollTrigger(listArea, tab) {
  if (tab._scrollContainer || tab._lazyAllLoaded || tab._lazyTotal <= tab.entries.length) return;
  _body.addEventListener('scroll', function () {
    if (tab._lazyLoadingMore || tab._lazyAllLoaded) return;
    var scrollBottom = _body.scrollTop + _body.clientHeight;
    if (scrollBottom >= _body.scrollHeight - 200) {
      _loadMore(tab);
    }
  });
}
