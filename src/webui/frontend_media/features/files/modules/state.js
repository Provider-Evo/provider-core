/**
 * File Manager -- shared module state, path helpers, and formatting utilities.
 *
 * This file is part of the files.js split (see files.js for the full module
 * list and load order). It must be loaded before any other files-*.js file
 * because it declares the shared state variables (_tabs, _activeTabId, ...)
 * and small helper functions that the rest of the modules read and call.
 *
 * All identifiers below are intentionally declared at top level (not inside
 * an IIFE) so that they become ordinary globals shared across the sibling
 * files-*.js files, mirroring how the previous single-IIFE file exposed the
 * same names to itself. No behavior changes were made during this split.
 */
var _tabs = [];
var _activeTabId = null;
var _tabCounter = 0;
var _contextMenu = null;
var _clipboard = { action: null, paths: [] }; // action: 'copy' or 'cut'
var _lastSelectedPath = null; // last right-clicked entry path for keyboard shortcuts
var _closedTabs = []; // history of closed tabs for Ctrl+Shift+T reopen
var _selectedIndex = -1; // keyboard-selected row index in sorted entries
var _restoringSession = false; // flag to suppress _saveSession during restoration

// Search state
var _searchInput = null;
var _searchResults = null;
var _searchDebounceTimer = null;
var _searchActiveIdx = -1;
var _searchAbortCtrl = null;

// Filesystem root state (drives on Windows, ["/"] on Linux)
var _drives = null;       // cached from GET /v1/webui/files/drives
var _projectRoot = null;  // cached from GET /v1/webui/files/project-root

// DOM references
var _container = null;
var _tabBar = null;
var _body = null;

// TabBar instance
var _bar = null;

// Virtual scrolling constants (shared by table.js, dirlist.js, files-toolbar.js)
var _VS_ROW_HEIGHT = 36;
var _VS_THRESHOLD = 200;
var _VS_BUFFER = 10;

// ========================= Root / Path Helpers =========================

async function _fetchDrives() {
  try {
    var data = await Api.fetchJson('/v1/webui/files/drives');
    _drives = data.drives || ['/'];
  } catch (e) {
    _drives = ['/'];
  }
}

async function _fetchProjectRoot() {
  try {
    var data = await Api.fetchJson('/v1/webui/files/project-root');
    _projectRoot = data.path || '/';
  } catch (e) {
    _projectRoot = '/';
  }
}

/**
 * Return true when *path* represents the OS "root" view
 * (the drives list on Windows, or "/" on Linux).
 */
function _isRootView(path) {
  if (!path || path === '/') return true;
  return false;
}

function _canWriteToTab(tab) {
  if (!tab) return false;
  if (tab.isDrives || _isRootView(tab.path)) return false;
  return true;
}

/**
 * Return the parent of *path*, or "/" if already at the root.
 * Works with both Unix (/home/user) and Windows (C:\Users) paths.
 */
function _parentPath(path) {
  if (!path || path === '/') return '/';

  // Normalise separators
  var norm = path.replace(/\\/g, '/');

  // Windows drive root: "C:/" → "/"  (drives view)
  if (/^[a-zA-Z]:\/?$/.test(norm)) return '/';

  // Strip trailing separator
  norm = norm.replace(/[\/\\]+$/, '');

  var lastSlash = norm.lastIndexOf('/');
  if (lastSlash <= 0) {
    // Check if it's a Windows path like "C:" (no slash at all after norm)
    if (/^[a-zA-Z]:$/.test(norm)) return '/';
    // Plain Unix path like "/foo" → parent is "/"
    return '/';
  }

  var parent = norm.substring(0, lastSlash);

  // Windows: "C:/Users" → "C:\"
  var winMatch = parent.match(/^([a-zA-Z]:)$/);
  if (winMatch) return winMatch[1] + '\\';

  // Windows: "C:/Users" parent might be "C:" → that's the drive root
  // Already handled above by the regex test

  return parent;
}

/**
 * Join a directory path with a child name, cross-platform.
 */
function _pathJoin(basePath, name) {
  if (!basePath || basePath === '/') return '/' + name;
  var norm = basePath.replace(/\\/g, '/');
  if (norm.endsWith('/')) return norm + name;
  // Windows drive root: "C:\" → "C:\name"
  if (/^[a-zA-Z]:\\$/.test(basePath)) return basePath + name;
  return basePath.replace(/[\/\\]+$/, '') + '/' + name;
}

function _pathDisplayName(path) {
  if (!path || path === '/') return 'Root';
  // Windows drive letter: "C:\", "C:\Users", etc.
  var winMatch = path.match(/^([a-zA-Z]:\\?)(.*)/);
  if (winMatch) {
    var rest = winMatch[2];
    if (!rest || rest === '\\') return winMatch[1].replace(/\\$/, '');
    var parts = rest.split(/[\/\\]/).filter(Boolean);
    return parts[parts.length - 1] || winMatch[1].replace(/\\$/, '');
  }
  // Unix paths
  var parts = path.replace(/[\/\\]+$/, '').split(/[\/\\]/).filter(Boolean);
  return parts[parts.length - 1] || 'Root';
}

// ========================= Formatting Utilities =========================

function _formatSize(bytes) {
  if (bytes == null) return '-';
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  if (bytes < 1024 * 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB';
}

function _formatDate(ts) {
  if (!ts) return '-';
  var d = new Date(ts * 1000);
  var y = d.getFullYear();
  var m = String(d.getMonth() + 1).padStart(2, '0');
  var day = String(d.getDate()).padStart(2, '0');
  var h = String(d.getHours()).padStart(2, '0');
  var min = String(d.getMinutes()).padStart(2, '0');
  return y + '-' + m + '-' + day + ' ' + h + ':' + min;
}

function _fileIcon(name) {
  var ext = (name || '').split('.').pop().toLowerCase();
  var map = {
    'js': '\u{1F7E8}', 'ts': '\u{1F535}', 'py': '\u{1F40D}',
    'json': '{}', 'html': '\u{1F310}', 'css': '\u{1F3A8}',
    'md': '\u{1F4DD}', 'txt': '\u{1F4C4}', 'yml': '\u{2699}',
    'yaml': '\u{2699}', 'toml': '\u{2699}', 'sh': '\u{1F4BB}',
    'png': '\u{1F5BC}', 'jpg': '\u{1F5BC}', 'jpeg': '\u{1F5BC}',
    'gif': '\u{1F5BC}', 'svg': '\u{1F5BC}',
  };
  return map[ext] || '\u{1F4C4}';
}

function _detectLanguage(filename) {
  var ext = (filename || '').split('.').pop().toLowerCase();
  var map = {
    'py': 'python', 'js': 'javascript', 'ts': 'typescript',
    'html': 'html', 'css': 'css', 'json': 'json',
    'toml': 'ini', 'yaml': 'yaml', 'yml': 'yaml',
    'md': 'markdown', 'sh': 'bash', 'bash': 'bash',
    'sql': 'sql', 'xml': 'xml', 'java': 'java',
    'go': 'go', 'rs': 'rust', 'rb': 'ruby',
    'php': 'php', 'c': 'c', 'cpp': 'cpp', 'h': 'c',
    'cs': 'csharp', 'swift': 'swift', 'kt': 'kotlin',
  };
  return map[ext] || 'plaintext';
}

function _escapeHtml(text) {
  var d = document.createElement('div');
  d.textContent = String(text);
  return d.innerHTML;
}

function _escapeAttr(text) {
  return String(text).replace(/&/g, '&amp;').replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function _getTabById(tabId) {
  for (var i = 0; i < _tabs.length; i++) {
    if (_tabs[i].id === tabId) return _tabs[i];
  }
  return null;
}

function _getTabById(tabId) {
  for (var i = 0; i < _tabs.length; i++) {
    if (_tabs[i].id === tabId) return _tabs[i];
  }
  return null;
}
