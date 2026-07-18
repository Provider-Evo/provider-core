/**
 * TerminalState 方法层：挂载 getter/setter 到状态对象 S 上。
 * 由 state.js 组装为公开 API。
 */
function _attachTerminalStateAccessors(S) {
  S.getTabs = function () { return S._tabs; };
  S.getActiveTabId = function () { return S._activeTabId; };
  S.setActiveTabId = function (id) { S._activeTabId = id; };
  S.getTabCounter = function () { return S._tabCounter; };
  S.incrementTabCounter = function () { S._tabCounter++; };
  S.getSavedConnections = function () { return S._savedConnections; };
  S.setSavedConnections = function (conns) { S._savedConnections = conns; };
  S.getContextMenu = function () { return S._contextMenu; };
  S.setContextMenu = function (menu) { S._contextMenu = menu; };
  S.isDiscoveryProcessed = function () { return S._discoveryProcessed; };
  S.setDiscoveryProcessed = function (val) { S._discoveryProcessed = val; };
  S.getTerminalBgMode = function () { return S._terminalBgMode; };
  S.setTerminalBgMode = function (mode) { S._terminalBgMode = mode; };
  S.getDAResponse = function () { return S._DA_RESPONSE; };
  S.getCustomBgImage = function () { return S._customBgImage; };
  S.setCustomBgImage = function (img) { S._customBgImage = img; };
  S.getCustomBgOpacity = function () { return S._customBgOpacity; };
  S.setCustomBgOpacity = function (val) { S._customBgOpacity = val; };
}

function _attachTerminalStateDomAccessors(S) {
  S.getContainer = function () { return S._container; };
  S.setContainer = function (el) { S._container = el; };
  S.getTabBarEl = function () { return S._tabBarEl; };
  S.setTabBarEl = function (el) { S._tabBarEl = el; };
  S.getBody = function () { return S._body; };
  S.setBody = function (el) { S._body = el; };
  S.getBar = function () { return S._bar; };
  S.setBar = function (bar) { S._bar = bar; };
  S.getColorPicker = function () { return S._colorPicker; };
  S.setColorPicker = function (picker) { S._colorPicker = picker; };
  S.getSavedTabColors = function () { return S._savedTabColors; };
  S.setSavedTabColors = function (colors) { S._savedTabColors = colors; };
  S.getSearchState = function () { return S._searchState; };
  S.setSearchState = function (state) { S._searchState = state; };
}

function _attachTerminalStateConstants(S) {
  S.getPresetColors = function () { return S._PRESET_COLORS; };
  S.getUrlRegex = function () { return S._TERMINAL_URL_RE; };
  S.getPathRegex = function () { return S._TERMINAL_PATH_RE; };
}

function _attachTerminalStateLookups(S) {
  S.getTabById = function (tabId) {
    for (var i = 0; i < S._tabs.length; i++) {
      if (S._tabs[i].id === tabId) return S._tabs[i];
    }
    return null;
  };
  S.getActiveTab = function () {
    return S.getTabById(S._activeTabId);
  };
}

function _attachTerminalStateMethods(S) {
  _attachTerminalStateAccessors(S);
  _attachTerminalStateDomAccessors(S);
  _attachTerminalStateConstants(S);
  _attachTerminalStateLookups(S);
}

/**
 * Preset colors for the tab color picker. Extracted from
 * _createTerminalStateData so that function stays under the line budget.
 */
function _getTerminalStatePresetColors() {
  return [
    { name: 'terminal.red', value: '#dc3545' },
    { name: 'terminal.red', value: '#ff4444' },
    { name: 'terminal.red', value: '#ff6b9d' },
    { name: 'terminal.red', value: '#e91e63' },
    { name: 'terminal.orange', value: '#fd7e14' },
    { name: 'terminal.orange', value: '#ff8800' },
    { name: 'terminal.orange', value: '#ffc107' },
    { name: 'terminal.orange', value: '#ffcd38' },
    { name: 'terminal.green', value: '#28a745' },
    { name: 'terminal.green', value: '#44cc44' },
    { name: 'terminal.green', value: '#20c997' },
    { name: 'terminal.green', value: '#17a2b8' },
    { name: 'terminal.blue', value: '#007bff' },
    { name: 'terminal.blue', value: '#4488ff' },
    { name: 'terminal.blue', value: '#6f42c1' },
    { name: 'terminal.blue', value: '#aa44ff' },
  ];
}

/**
 * Default search-state shape. Extracted from _createTerminalStateData so
 * that function stays under the line budget.
 */
function _getTerminalStateDefaultSearchState() {
  return {
    query: '',
    caseSensitive: false,
    regex: false,
    matches: [],
    currentIndex: -1,
  };
}

/**
 * Builds the raw mutable state object backing TerminalState.
 * Extracted from state.js so the IIFE there stays a thin facade.
 */
function _createTerminalStateData() {
  return {
    _tabs: [],
    _activeTabId: null,
    _tabCounter: 0,
    _savedConnections: [],
    _contextMenu: null,
    _discoveryProcessed: false,
    _terminalBgMode: 'theme',
    _DA_RESPONSE: /\x1b\[\?[0-9;]*c/g,
    _customBgImage: '',
    _customBgOpacity: 0.3,

    // DOM references (set in init)
    _container: null,
    _tabBarEl: null,
    _body: null,
    _bar: null,

    // Color picker
    _colorPicker: null,
    _savedTabColors: {},

    // Search state
    _searchState: _getTerminalStateDefaultSearchState(),

    // Preset colors for tab color picker
    _PRESET_COLORS: _getTerminalStatePresetColors(),

    // URL and path regex for link detection
    _TERMINAL_URL_RE: /https?:\/\/[^\s"'`<>]+/g,
    _TERMINAL_PATH_RE: /(?:~\/|\.{1,2}\/|\/|[A-Za-z]:[\\/]|\\\\)[^\s"'`<>]+/g,
  };
}

/**
 * Builds the public getter/setter API object returned by the
 * TerminalState IIFE, delegating to the methods attached onto S.
 */
function _buildTerminalStatePublicApi(S) {
  return {
    getTabs: S.getTabs,
    getActiveTabId: S.getActiveTabId,
    setActiveTabId: S.setActiveTabId,
    getTabCounter: S.getTabCounter,
    incrementTabCounter: S.incrementTabCounter,
    getSavedConnections: S.getSavedConnections,
    setSavedConnections: S.setSavedConnections,
    getContextMenu: S.getContextMenu,
    setContextMenu: S.setContextMenu,
    isDiscoveryProcessed: S.isDiscoveryProcessed,
    setDiscoveryProcessed: S.setDiscoveryProcessed,
    getTerminalBgMode: S.getTerminalBgMode,
    setTerminalBgMode: S.setTerminalBgMode,
    getDAResponse: S.getDAResponse,
    getCustomBgImage: S.getCustomBgImage,
    setCustomBgImage: S.setCustomBgImage,
    getCustomBgOpacity: S.getCustomBgOpacity,
    setCustomBgOpacity: S.setCustomBgOpacity,
    getContainer: S.getContainer,
    setContainer: S.setContainer,
    getTabBarEl: S.getTabBarEl,
    setTabBarEl: S.setTabBarEl,
    getBody: S.getBody,
    setBody: S.setBody,
    getBar: S.getBar,
    setBar: S.setBar,
    getColorPicker: S.getColorPicker,
    setColorPicker: S.setColorPicker,
    getSavedTabColors: S.getSavedTabColors,
    setSavedTabColors: S.setSavedTabColors,
    getSearchState: S.getSearchState,
    setSearchState: S.setSearchState,
    getPresetColors: S.getPresetColors,
    getUrlRegex: S.getUrlRegex,
    getPathRegex: S.getPathRegex,
    getTabById: S.getTabById,
    getActiveTab: S.getActiveTab,
  };
}
