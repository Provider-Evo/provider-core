/**
 * KeysFeature 方法层：渲染 / 创建 / 删除 / 展示 逻辑挂载到状态对象 S 上。
 */
function _keysEsc(text) {
  if (typeof escapeHtml === 'function') return escapeHtml(text);
  var d = document.createElement('div');
  d.textContent = String(text);
  return d.innerHTML;
}

function _keysRenderRow(k) {
  var quota = k.quota_total > 0
    ? k.quota_used + ' / ' + k.quota_total
    : t('keys.unlimited');
  var expires = k.expires_at > 0
    ? new Date(k.expires_at * 1000).toLocaleString()
    : t('keys.never');
  var models = (k.models && k.models.length) ? k.models.join(', ') : t('keys.allModels');
  var enabled = k.enabled !== false;
  return '<tr data-key-id="' + k.id + '">'
    + '<td><strong>' + _keysEsc(k.name || k.id) + '</strong><div class="text-[11px] text-muted font-mono">' + _keysEsc(k.id) + '</div></td>'
    + '<td>' + quota + '</td>'
    + '<td>' + _keysEsc(models) + '</td>'
    + '<td>' + expires + '</td>'
    + '<td>' + (enabled ? '<span class="ui-chip ui-chip--ok">' + t('keys.enabled') + '</span>' : '<span class="ui-chip ui-chip--err">' + t('keys.disabled') + '</span>') + '</td>'
    + '<td><button type="button" class="ui-btn ui-btn--danger ui-btn--sm keys-delete-btn" data-id="' + k.id + '">' + t('keys.delete') + '</button></td>'
    + '</tr>';
}

function _keysRender(S) {
  if (!S._keys.length) {
    S._tableBody.innerHTML = '<tr><td colspan="6"><div class="ui-empty"><p class="ui-empty__title">' + t('keys.emptyTitle') + '</p><p class="ui-empty__desc">' + t('keys.emptyDesc') + '</p></div></td></tr>';
    return;
  }
  S._tableBody.innerHTML = S._keys.map(_keysRenderRow).join('');

  S._tableBody.querySelectorAll('.keys-delete-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      S.deleteKey(btn.dataset.id);
    });
  });
}

async function _keysRefresh(S) {
  if (!S._tableBody) return;
  S._tableBody.innerHTML = '<tr><td colspan="6" class="text-muted">' + t('common.loading') + '</td></tr>';
  try {
    var resp = await Api.fetchJson('/v1/admin/keys');
    S._keys = resp.keys || [];
    S.render();
  } catch (e) {
    S._tableBody.innerHTML = '<tr><td colspan="6" class="text-err">' + t('keys.loadFailed', { error: e.message }) + '</td></tr>';
  }
}

function _keysShowReveal(created) {
  if (!created.key) return;
  var backdrop = document.createElement('div');
  backdrop.className = 'ui-modal-backdrop';
  backdrop.innerHTML = ''
    + '<div class="ui-modal" role="dialog">'
    + '<h3 class="ui-modal__title">' + t('keys.revealTitle') + '</h3>'
    + '<p class="text-muted text-[13px] m-0">' + t('keys.revealDesc') + '</p>'
    + '<div class="ui-key-reveal" id="keysRevealValue">' + _keysEsc(created.key) + '</div>'
    + '<div class="ui-modal__actions">'
    + '<button type="button" class="ui-btn ui-btn--primary" id="keysRevealCopy">' + t('keys.copy') + '</button>'
    + '<button type="button" class="ui-btn" id="keysRevealClose">' + t('common.close') + '</button>'
    + '</div></div>';
  document.body.appendChild(backdrop);
  backdrop.querySelector('#keysRevealClose').addEventListener('click', function () { backdrop.remove(); });
  backdrop.querySelector('#keysRevealCopy').addEventListener('click', function () {
    if (typeof copyText === 'function') copyText(created.key, t('keys.copied'));
  });
}

function _keysBindCreateForm(S, backdrop) {
  backdrop.querySelector('#keysFormCancel').addEventListener('click', function () {
    backdrop.remove();
  });
  backdrop.addEventListener('click', function (e) {
    if (e.target === backdrop) backdrop.remove();
  });
  backdrop.querySelector('#keysFormSubmit').addEventListener('click', async function () {
    var name = (document.getElementById('keysFormName').value || '').trim();
    var quota = parseInt(document.getElementById('keysFormQuota').value || '0', 10) || 0;
    var modelsRaw = (document.getElementById('keysFormModels').value || '').trim();
    var models = modelsRaw ? modelsRaw.split(',').map(function (s) { return s.trim(); }).filter(Boolean) : [];
    try {
      var resp = await Api.fetchJson('/v1/admin/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name, quota_total: quota, models: models }),
      });
      backdrop.remove();
      _keysShowReveal(resp.key || {});
      S.refresh();
      toast(t('keys.createOk'), 'ok');
    } catch (e) {
      toast(t('keys.createFailed', { error: e.message }), 'error');
    }
  });
}

function _keysOpenCreateModal(S) {
  var backdrop = document.createElement('div');
  backdrop.className = 'ui-modal-backdrop';
  backdrop.innerHTML = ''
    + '<div class="ui-modal" role="dialog">'
    + '<h3 class="ui-modal__title">' + t('keys.createTitle') + '</h3>'
    + '<div class="ui-field"><label>' + t('keys.nameLabel') + '</label><input id="keysFormName" type="text" placeholder="' + t('keys.namePlaceholder') + '"></div>'
    + '<div class="ui-field"><label>' + t('keys.quotaLabel') + '</label><input id="keysFormQuota" type="number" min="0" value="0" placeholder="0"></div>'
    + '<div class="ui-field"><label>' + t('keys.modelsLabel') + '</label><input id="keysFormModels" type="text" placeholder="' + t('keys.modelsPlaceholder') + '"></div>'
    + '<div class="ui-modal__actions">'
    + '<button type="button" class="ui-btn" id="keysFormCancel">' + t('common.cancel') + '</button>'
    + '<button type="button" class="ui-btn ui-btn--primary" id="keysFormSubmit">' + t('keys.create') + '</button>'
    + '</div></div>';
  document.body.appendChild(backdrop);
  _keysBindCreateForm(S, backdrop);
}

async function _keysDeleteKey(S, id) {
  if (!id) return;
  if (!await showConfirmDialog(t('keys.deleteConfirm'), { title: t('keys.deleteKey') || 'Delete Key' })) return;
  try {
    await Api.fetchJson('/v1/admin/keys/' + encodeURIComponent(id), { method: 'DELETE' });
    toast(t('keys.deleteOk'), 'ok');
    S.refresh();
  } catch (e) {
    toast(t('keys.deleteFailed', { error: e.message }), 'error');
  }
}

function _attachKeysFeatureMethods(S) {
  S.render = function () { return _keysRender(S); };
  S.refresh = function () { return _keysRefresh(S); };
  S.openCreateModal = function () { return _keysOpenCreateModal(S); };
  S.deleteKey = function (id) { return _keysDeleteKey(S, id); };
}
