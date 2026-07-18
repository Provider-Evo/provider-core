/**
 * Virtual Keys 管理页 — /v1/admin/keys
 * 状态与渲染/创建/删除逻辑拆分到 keys_helpers.js，本文件为薄封装。
 */
var KeysFeature = (function () {
  var S = { _tableBody: null, _keys: [] };
  _attachKeysFeatureMethods(S);

  function init() {
    S._tableBody = document.getElementById('keysTableBody');
    var createBtn = document.getElementById('keysCreateBtn');
    if (createBtn && !createBtn.dataset.bound) {
      createBtn.dataset.bound = '1';
      createBtn.addEventListener('click', S.openCreateModal);
    }
    S.refresh();
  }

  return { init: init, refresh: S.refresh };
})();

function _initKeysTab() {
  if (typeof KeysFeature !== 'undefined') KeysFeature.init();
  var refreshBtn = document.getElementById('keysRefreshBtn');
  if (refreshBtn && !refreshBtn.dataset.bound) {
    refreshBtn.dataset.bound = '1';
    refreshBtn.addEventListener('click', function () {
      if (typeof KeysFeature !== 'undefined') KeysFeature.refresh();
    });
  }
}
