/**
 * 插件管理面板（Provider-V2 式：列表行 + 配置编辑器 + 市场）
 * 状态与方法集中在内部对象 P 上（_buildPluginsPanelInternal 构建），具体逻辑拆分到 plugins_*.js。
 */
function _createPluginsPanelState() {
  return {
    _loaded: false,
    _plugins: [],
    _market: [],
    _marketById: {},
    _hostVersion: null,
    _marketConfig: null,
    _activeTab: 'installed',
    _editorPluginId: '',
    _editorPlugin: null,
    _editorBundle: null,
    _editorTab: 'visual',
    _editorDraft: {},
    _editorPanelHandle: null,
    _editorPanelId: '',
    _actingPluginId: '',
    _showUpdatesOnly: false,
    _searchQuery: '',
    _installTarget: { url: '', pluginId: '' },
    el: function (id) { return document.getElementById(id); },
  };
}

function _buildPluginsPanelInternal() {
  var P = _createPluginsPanelState();
  _attachPluginsHelpers(P);
  _attachPluginsRenderListMethods(P);
  _attachPluginsRenderMarketMethods(P);
  _attachPluginsRenderEditorMethods(P);
  _attachPluginsActionMethods(P);
  _attachPluginsEventMethods(P);
  return P;
}

var PluginsPanel = (function () {
  var P = _buildPluginsPanelInternal();

  function init() {
    if (P._loaded) {
      P.refresh();
      return;
    }
    P._loaded = true;
    P.bindEvents();
    P.setTab('installed');
    P.showMainView(false);
    P.refresh().then(function () { return P.loadMarket(); });
  }

  return {
    init: init,
    refresh: function refresh() { return P.refresh(); },
    onProgress: function onProgress(data) { return P.onProgressFromSocket(data); },
  };
})();

function initPluginsPanel() {
  PluginsPanel.init();
}

if (typeof window !== 'undefined') {
  window.PluginsPanel = PluginsPanel;
}
