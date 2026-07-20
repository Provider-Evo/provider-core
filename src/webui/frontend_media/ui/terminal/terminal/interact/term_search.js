// ========================= Terminal: Find / Search =========================
// Split from terminal.js. Handles the in-terminal find dialog: query,
// regex/case toggles, match navigation, and highlighting via xterm selection.

var _tsSearchState = {
  query: '',
  caseSensitive: false,
  regex: false,
  matches: [],
  currentIndex: -1,
};

function _tsEscapeRegex(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function _tsResetSearchState() {
  _tsSearchState = { query: '', caseSensitive: false, regex: false, matches: [], currentIndex: -1 };
  return _tsSearchState;
}

/**
 * Show an in-terminal find dialog for the given tab, anchored to the
 * tab's terminal pane (top-right corner) per NOTE.md 17.2.5.
 */
function _tsShowSearchDialog(ctx, tabId) {
  var tab = ctx.getTabById(tabId);
  if (!tab || !tab.xterm) return;

  var pane = document.getElementById('terminal-pane-' + tabId);
  if (!pane) return;

  var existing = pane.querySelector('.terminal-search-dialog');
  if (existing) {
    var input = existing.querySelector('.search-input');
    if (input) input.focus();
    return;
  }

  _tsResetSearchState();

  var dialog = document.createElement('div');
  dialog.className = 'terminal-search-dialog';
  dialog.innerHTML =
    '<div class="search-row">' +
    '<input type="text" class="search-input" placeholder="' + t('terminal.searchPlaceholder') + '">' +
    '<span class="search-count">0/0</span>' +
    '<button type="button" class="search-prev" title="' + t('terminal.searchPrev') + '">&uarr;</button>' +
    '<button type="button" class="search-next" title="' + t('terminal.searchNext') + '">&darr;</button>' +
    '<button type="button" class="search-case" title="' + t('terminal.searchCase') + '">Aa</button>' +
    '<button type="button" class="search-regex" title="' + t('terminal.searchRegex') + '">.*</button>' +
    '<button type="button" class="search-close" title="' + t('terminal.searchClose') + '">&times;</button>' +
    '</div>';

  pane.appendChild(dialog);
  _tsBindSearchEvents(tab, dialog);

  var searchInput = dialog.querySelector('.search-input');
  searchInput.focus();
}

function _tsHideSearchDialog(tab) {
  var pane = document.getElementById('terminal-pane-' + tab.id);
  if (!pane) return;
  var dialog = pane.querySelector('.terminal-search-dialog');
  if (dialog) dialog.remove();
  _tsClearSearchHighlights(tab);
}

function _tsClearSearchHighlights(tab) {
  if (tab.xterm && typeof tab.xterm.clearSelection === 'function') {
    tab.xterm.clearSelection();
  }
  _tsSearchState.matches = [];
  _tsSearchState.currentIndex = -1;
}

function _tsCollectSearchMatches(tab, query) {
  var buffer = tab.xterm.buffer.active;
  var matches = [];
  var pattern = _tsSearchState.regex ? query : _tsEscapeRegex(query);
  var regex = new RegExp(pattern, _tsSearchState.caseSensitive ? 'g' : 'gi');

  for (var i = 0; i < buffer.length; i++) {
    var line = buffer.getLine(i);
    if (!line) continue;
    var text = line.translateToString(true);
    regex.lastIndex = 0;
    var match;
    while ((match = regex.exec(text)) !== null) {
      matches.push({ line: i, col: match.index, length: match[0].length });
      if (match[0].length === 0) regex.lastIndex++;
    }
  }
  return matches;
}

/**
 * Perform a linear scan over the visible buffer for the search query.
 * Uses xterm.js's own line selection (select + scrollToLine) to
 * highlight matches, since no search addon is bundled in this project.
 */
function _tsPerformSearch(tab, dialog) {
  var query = _tsSearchState.query;
  var countEl = dialog.querySelector('.search-count');
  if (!query) {
    _tsClearSearchHighlights(tab);
    if (countEl) countEl.textContent = '0/0';
    return;
  }

  var matches;
  try {
    matches = _tsCollectSearchMatches(tab, query);
  } catch (e) {
    // Invalid regex pattern; treat as no matches rather than throwing
    if (countEl) countEl.textContent = '0/0';
    return;
  }

  _tsSearchState.matches = matches;
  _tsSearchState.currentIndex = matches.length > 0 ? 0 : -1;

  if (countEl) {
    countEl.textContent = matches.length > 0
      ? (_tsSearchState.currentIndex + 1) + '/' + matches.length
      : t('terminal.searchNotFound');
  }

  if (matches.length > 0) {
    _tsHighlightMatch(tab, matches[0]);
  }
}

function _tsHighlightMatch(tab, match) {
  if (!tab.xterm || typeof tab.xterm.select !== 'function') return;
  tab.xterm.select(match.col, match.line, match.length);
  if (typeof tab.xterm.scrollToLine === 'function') {
    tab.xterm.scrollToLine(match.line);
  }
}

function _tsSearchStep(tab, dialog, direction) {
  var matches = _tsSearchState.matches;
  if (matches.length === 0) return;
  _tsSearchState.currentIndex = (_tsSearchState.currentIndex + direction + matches.length) % matches.length;
  _tsHighlightMatch(tab, matches[_tsSearchState.currentIndex]);
  var countEl = dialog.querySelector('.search-count');
  if (countEl) countEl.textContent = (_tsSearchState.currentIndex + 1) + '/' + matches.length;
}

function _tsBindSearchInputEvents(tab, dialog) {
  var input = dialog.querySelector('.search-input');

  input.addEventListener('input', function () {
    _tsSearchState.query = input.value;
    _tsPerformSearch(tab, dialog);
  });

  input.addEventListener('keydown', function (e) {
    if (e.key === 'Enter') {
      e.preventDefault();
      _tsSearchStep(tab, dialog, e.shiftKey ? -1 : 1);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      _tsHideSearchDialog(tab);
    }
  });
}

function _tsBindSearchToggleEvents(tab, dialog) {
  var caseBtn = dialog.querySelector('.search-case');
  var regexBtn = dialog.querySelector('.search-regex');

  caseBtn.addEventListener('click', function () {
    _tsSearchState.caseSensitive = !_tsSearchState.caseSensitive;
    caseBtn.classList.toggle('active', _tsSearchState.caseSensitive);
    _tsPerformSearch(tab, dialog);
  });

  regexBtn.addEventListener('click', function () {
    _tsSearchState.regex = !_tsSearchState.regex;
    regexBtn.classList.toggle('active', _tsSearchState.regex);
    _tsPerformSearch(tab, dialog);
  });
}

function _tsBindSearchEvents(tab, dialog) {
  var prevBtn = dialog.querySelector('.search-prev');
  var nextBtn = dialog.querySelector('.search-next');
  var closeBtn = dialog.querySelector('.search-close');

  _tsBindSearchInputEvents(tab, dialog);
  _tsBindSearchToggleEvents(tab, dialog);

  prevBtn.addEventListener('click', function () { _tsSearchStep(tab, dialog, -1); });
  nextBtn.addEventListener('click', function () { _tsSearchStep(tab, dialog, 1); });
  closeBtn.addEventListener('click', function () { _tsHideSearchDialog(tab); });
}

function _attachSearchMethods(ctx) {
  ctx.showSearchDialog = function (tabId) { _tsShowSearchDialog(ctx, tabId); };
}


