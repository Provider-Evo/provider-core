/**
 * File Manager -- toolbar construction: nav buttons, breadcrumb, search
 * box, clipboard indicator, and action buttons.
 *
 * Part of the files.js split. Depends on state.js. Calls into
 * dirlist.js (_goBack/_goForward/_goUp/_navigateTo/_loadDirectory),
 * files-search.js (_debounceSearch etc.), upload.js (_triggerFilePicker),
 * ops.js (_promptNewFolder). Used by render.js (_renderContent).
 */

function _buildNavButtons(tab) {
  var frag = document.createDocumentFragment();

  var backBtn = document.createElement('button');
  backBtn.className = 'files-nav-btn';
  backBtn.innerHTML = '&#9664;';
  backBtn.title = t('files.back');
  backBtn.disabled = tab.historyIdx <= 0;
  backBtn.addEventListener('click', function () { _goBack(tab); });
  frag.appendChild(backBtn);

  var fwdBtn = document.createElement('button');
  fwdBtn.className = 'files-nav-btn';
  fwdBtn.innerHTML = '&#9654;';
  fwdBtn.title = t('files.forward');
  fwdBtn.disabled = tab.historyIdx >= tab.history.length - 1;
  fwdBtn.addEventListener('click', function () { _goForward(tab); });
  frag.appendChild(fwdBtn);

  var upBtn = document.createElement('button');
  upBtn.className = 'files-nav-btn';
  upBtn.innerHTML = '&#9650;';
  upBtn.title = t('files.parentDir');
  upBtn.disabled = _isRootView(tab.path);
  upBtn.addEventListener('click', function () { _goUp(tab); });
  frag.appendChild(upBtn);

  return frag;
}

function _buildBreadcrumbWinSegments(breadcrumb, tab, normPath) {
  var driveLetter = normPath.substring(0, 2); // e.g. "C:"
  var rest = normPath.substring(2); // e.g. "/Users/Foo" or "" or "/"
  var segments = rest.split('/').filter(Boolean);

  var sep0 = document.createElement('span');
  sep0.className = 'files-breadcrumb-sep';
  sep0.textContent = '/';
  breadcrumb.appendChild(sep0);

  var driveSeg = document.createElement('span');
  driveSeg.className = 'files-breadcrumb-seg' + (segments.length === 0 ? ' current' : '');
  driveSeg.textContent = driveLetter;
  (function (dl) {
    driveSeg.addEventListener('click', function () {
      _navigateTo(tab, dl + '\\');
    });
  })(driveLetter);
  breadcrumb.appendChild(driveSeg);

  for (var wi = 0; wi < segments.length; wi++) {
    var wsep = document.createElement('span');
    wsep.className = 'files-breadcrumb-sep';
    wsep.textContent = '/';
    breadcrumb.appendChild(wsep);

    var wseg = document.createElement('span');
    wseg.className = 'files-breadcrumb-seg' + (wi === segments.length - 1 ? ' current' : '');
    wseg.textContent = segments[wi];
    (function (dl, segs, idx) {
      wseg.addEventListener('click', function () {
        var p = dl + '\\' + segs.slice(0, idx + 1).join('\\');
        _navigateTo(tab, p);
      });
    })(driveLetter, segments, wi);
    breadcrumb.appendChild(wseg);
  }
}

function _buildBreadcrumbUnixSegments(breadcrumb, tab, normPath) {
  var segments = normPath.split('/').filter(Boolean);
  for (var i = 0; i < segments.length; i++) {
    var sep = document.createElement('span');
    sep.className = 'files-breadcrumb-sep';
    sep.textContent = '/';
    breadcrumb.appendChild(sep);

    var seg = document.createElement('span');
    seg.className = 'files-breadcrumb-seg' + (i === segments.length - 1 ? ' current' : '');
    seg.textContent = segments[i];
    (function (idx) {
      seg.addEventListener('click', function () {
        var p = '/' + segments.slice(0, idx + 1).join('/');
        _navigateTo(tab, p);
      });
    })(i);
    breadcrumb.appendChild(seg);
  }
}

function _buildBreadcrumb(tab, toolbar) {
  var breadcrumb = document.createElement('div');
  breadcrumb.className = 'files-breadcrumb';

  var normPath = (tab.path || '/').replace(/\\/g, '/');
  var isWinDrive = /^[a-zA-Z]:/.test(normPath);

  var rootSeg = document.createElement('span');
  rootSeg.className = 'files-breadcrumb-seg' + (_isRootView(tab.path) ? ' current' : '');
  rootSeg.textContent = '/';
  rootSeg.addEventListener('click', function () { _navigateTo(tab, '/'); });
  breadcrumb.appendChild(rootSeg);

  if (isWinDrive) {
    _buildBreadcrumbWinSegments(breadcrumb, tab, normPath);
  } else {
    _buildBreadcrumbUnixSegments(breadcrumb, tab, normPath);
  }

  breadcrumb.addEventListener('dblclick', function (e) {
    e.stopPropagation();
    _showPathInput(tab, toolbar, breadcrumb);
  });

  return breadcrumb;
}

function _handleSearchInputKeydown(e) {
  if (e.key === 'Enter') {
    e.preventDefault();
    var items = _searchResults ? _searchResults.querySelectorAll('.files-search-result') : [];
    var idx = _searchActiveIdx >= 0 ? _searchActiveIdx : 0;
    if (items.length > idx) {
      items[idx].click();
    }
  } else if (e.key === 'ArrowDown') {
    e.preventDefault();
    _navigateSearchResults(1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    _navigateSearchResults(-1);
  } else if (e.key === 'Escape') {
    e.preventDefault();
    _clearSearch();
    _searchInput.blur();
  }
}

function _wireSearchInput(searchWrapper, tab) {
  _searchInput.addEventListener('input', function () {
    var val = _searchInput.value.trim();
    if (val.length > 0) {
      searchWrapper.classList.add('has-query');
    } else {
      searchWrapper.classList.remove('has-query');
    }
    _debounceSearch(val, tab);
  });

  _searchInput.addEventListener('keydown', _handleSearchInputKeydown);

  _searchInput.addEventListener('focus', function () {
    var val = _searchInput.value.trim();
    if (val.length > 0 && _searchResults && _searchResults.children.length > 0) {
      _searchResults.classList.add('visible');
    }
  });
}

function _buildSearchWrapper(tab) {
  var searchWrapper = document.createElement('div');
  searchWrapper.className = 'files-search-wrapper';

  _searchInput = document.createElement('input');
  _searchInput.type = 'text';
  _searchInput.className = 'files-search-input';
  _searchInput.placeholder = t('files.searchPlaceholder');
  _searchInput.autocomplete = 'off';
  _searchInput.spellcheck = false;

  _wireSearchInput(searchWrapper, tab);

  var clearBtn = document.createElement('button');
  clearBtn.className = 'files-search-clear';
  clearBtn.type = 'button';
  clearBtn.innerHTML = '&times;';
  clearBtn.title = t('files.clearSearch');
  clearBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    _clearSearch();
    _searchInput.focus();
  });

  _searchResults = document.createElement('div');
  _searchResults.className = 'files-search-results';

  searchWrapper.appendChild(_searchInput);
  searchWrapper.appendChild(clearBtn);
  searchWrapper.appendChild(_searchResults);

  document.addEventListener('click', function (e) {
    if (!searchWrapper.contains(e.target)) {
      _hideSearchResults();
    }
  });

  return searchWrapper;
}

function _buildClipboardIndicator() {
  var clipIndicator = document.createElement('span');
  clipIndicator.className = 'files-clipboard-indicator';
  clipIndicator.textContent = t('files.clipboard', { count: _clipboard.paths.length });
  clipIndicator.title = _clipboard.action === 'cut' ? t('files.cutToClipboard') : t('files.copyToClipboard');
  var clipClearBtn = document.createElement('span');
  clipClearBtn.className = 'files-clipboard-clear';
  clipClearBtn.textContent = '×';
  clipClearBtn.title = t('files.clearClipboardTitle');
  clipClearBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    _clipboard = { action: null, paths: [] };
    _renderContent();
  });
  clipIndicator.appendChild(clipClearBtn);
  return clipIndicator;
}

function _buildToolbarActions(tab) {
  var actions = document.createElement('div');
  actions.className = 'files-toolbar-actions';

  var canWrite = _canWriteToTab(tab);

  var uploadBtn = document.createElement('button');
  uploadBtn.className = 'files-toolbar-btn files-upload-btn';
  uploadBtn.textContent = t('files.upload');
  uploadBtn.title = canWrite ? t('files.uploadToDir') : t('files.enterDirFirst');
  uploadBtn.disabled = !canWrite;
  uploadBtn.addEventListener('click', function () { _triggerFilePicker(); });
  actions.appendChild(uploadBtn);

  var newFolderBtn = document.createElement('button');
  newFolderBtn.className = 'files-toolbar-btn';
  newFolderBtn.textContent = t('files.newFolderShort');
  newFolderBtn.title = canWrite ? t('files.newFolder') : t('files.enterDirFirst');
  newFolderBtn.disabled = !canWrite;
  newFolderBtn.addEventListener('click', function () { _promptNewFolder(tab); });
  actions.appendChild(newFolderBtn);

  var refreshBtn = document.createElement('button');
  refreshBtn.className = 'files-toolbar-btn';
  refreshBtn.textContent = t('files.refresh');
  refreshBtn.addEventListener('click', function () { _loadDirectory(tab, tab.path); });
  actions.appendChild(refreshBtn);

  return actions;
}

function _buildToolbar(tab) {
  var toolbar = document.createElement('div');
  toolbar.className = 'files-toolbar';

  toolbar.appendChild(_buildNavButtons(tab));
  toolbar.appendChild(_buildBreadcrumb(tab, toolbar));

  if (_projectRoot) {
    var projBtn = document.createElement('button');
    projBtn.className = 'files-nav-btn files-project-btn';
    projBtn.innerHTML = '&#128193;';
    projBtn.title = t('files.projectRoot');
    projBtn.addEventListener('click', function () { _navigateTo(tab, _projectRoot); });
    toolbar.appendChild(projBtn);
  }

  toolbar.appendChild(_buildSearchWrapper(tab));

  if (_clipboard.paths.length > 0) {
    toolbar.appendChild(_buildClipboardIndicator());
  }

  toolbar.appendChild(_buildToolbarActions(tab));
  return toolbar;
}

function _showPathInput(tab, toolbar, breadcrumb) {
  breadcrumb.style.display = 'none';
  var input = document.createElement('input');
  input.type = 'text';
  input.className = 'files-path-input';
  input.style.display = 'block';
  input.value = tab.path;

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      var val = input.value.trim();
      if (val) _navigateTo(tab, val);
      input.remove();
      breadcrumb.style.display = '';
    } else if (e.key === 'Escape') {
      input.remove();
      breadcrumb.style.display = '';
    }
  });

  input.addEventListener('blur', function () {
    input.remove();
    breadcrumb.style.display = '';
  });

  // Insert after nav buttons
  var navBtns = toolbar.querySelectorAll('.files-nav-btn');
  var lastNav = navBtns[navBtns.length - 1];
  if (lastNav && lastNav.nextSibling) {
    toolbar.insertBefore(input, lastNav.nextSibling);
  } else {
    toolbar.appendChild(input);
  }
  input.focus();
  input.select();
}
