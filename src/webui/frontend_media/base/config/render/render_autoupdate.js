// ========================= autoupdate 配置分节 — 完整面板（字段 + 检查/应用） =========================

function _autoupdateSectionDef() {
  return {
    id: 'autoupdate',
    title: 'autoupdate',
    fields: [
      { key: 'enabled', type: 'boolean' },
      { key: 'diff_update', type: 'boolean' },
      { key: 'branch', type: 'select', options: ['dev', 'main', 'classical'] },
      { key: 'interval', type: 'number', min: 30, step: 30 },
      { key: 'mirrors', type: 'list' },
    ],
  };
}

function _renderAutoupdateSection(sectionData) {
  var s = sectionData || {};
  var enabledLabel = typeof t === 'function' ? t('autoupdate.enableLabel') : '启用自动更新';
  var diffLabel = typeof t === 'function' ? t('autoupdate.diffUpdate') : '差异更新';
  var diffHint = typeof t === 'function' ? t('autoupdate.diffUpdateHint') : '';
  var branchLabel = typeof t === 'function' ? t('autoupdate.targetBranch') : '目标分支';
  var intervalLabel = typeof t === 'function' ? t('autoupdate.checkInterval') : '检查间隔（秒）';
  var mirrorsLabel = typeof t === 'function' ? t('autoupdate.mirrors') : '镜像源';
  var addMirrorLabel = typeof t === 'function' ? t('autoupdate.addMirror') : '+ 添加镜像源';
  var subtitle = typeof t === 'function' ? t('autoupdate.subtitle') : '';
  var checkLabel = typeof t === 'function' ? t('autoupdate.checkNow') : '立即检查';
  var applyLabel = typeof t === 'function' ? t('autoupdate.applyUpdate') : '应用更新';
  var statusLabel = typeof t === 'function' ? t('autoupdate.statusDisabled') : '未启用';
  var resultsLabel = typeof t === 'function' ? t('autoupdate.checkResults') : '检查结果';

  var html = '<div class="grid gap-3 grid-cols-[repeat(auto-fit,minmax(240px,1fr))]">';
  html += '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">';
  html += _field(enabledLabel, _renderToggle('autoupdate', 'enabled', !!s.enabled));
  html += '</div>';

  html += '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">';
  html += _field(diffLabel, _renderToggle('autoupdate', 'diff_update', s.diff_update !== false));
  if (diffHint) {
    html += '<div class="text-[11px] text-muted mt-1">' + escapeHtml(diffHint) + '</div>';
  }
  html += '</div>';

  html += '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">';
  html += _field(branchLabel, _renderSelect(
    'autoupdate', 'branch', s.branch || 'dev', ['dev', 'main', 'classical'], {}
  ));
  html += '</div>';

  html += '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">';
  html += _field(
    intervalLabel,
    _renderNumber('autoupdate', 'interval', s.interval != null ? s.interval : 300, { min: 30, step: 30 })
  );
  html += '</div>';
  html += '</div>';

  html += '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift mt-3">';
  html += '<div class="flex justify-between items-center mb-2">';
  html += '<div class="text-[13px] text-muted">' + escapeHtml(mirrorsLabel) + '</div>';
  html += '<button type="button" class="text-[12px] text-accent hover:underline cursor-pointer" id="autoupdateAddMirrorBtn">'
    + escapeHtml(addMirrorLabel) + '</button>';
  html += '</div>';
  html += '<div id="autoupdateMirrorsList"></div>';
  html += '</div>';

  html += '<div class="flex flex-wrap justify-between items-end gap-3 mt-4 pt-3 border-t border-border">';
  html += '<p class="m-0 text-muted leading-relaxed text-[13px]">' + escapeHtml(subtitle) + '</p>';
  html += '<div class="flex flex-wrap gap-2 items-center">';
  html += '<button class="ui-btn" id="autoupdateCheckBtn" type="button">' + escapeHtml(checkLabel) + '</button>';
  html += '<button class="ui-btn ui-btn--primary hidden" id="autoupdateApplyBtn" type="button">' + escapeHtml(applyLabel) + '</button>';
  html += '<span id="autoupdateStatus" class="status-saved flex items-center text-xs">' + escapeHtml(statusLabel) + '</span>';
  html += '</div></div>';

  html += '<div id="autoupdateResults" class="mt-3 hidden">';
  html += '<div class="border border-border rounded-xl p-3.5 bg-panel-alt card-hover-lift">';
  html += '<div class="flex justify-between items-center mb-2">';
  html += '<div class="text-[13px] font-semibold">' + escapeHtml(resultsLabel) + '</div>';
  html += '<span id="autoupdateResultStatus" class="text-[12px]"></span>';
  html += '</div>';
  html += '<div id="autoupdateResultMeta" class="text-[12px] text-muted mb-2"></div>';
  html += '<div class="flex flex-wrap gap-2 mb-2" id="autoupdateFileToolbar">';
  html += '<input type="text" id="autoupdateSearchInput" class="config-input" style="width:180px;display:none;"'
    + ' placeholder="' + escapeHtml(typeof t === 'function' ? t('autoupdate.searchFiles') : '') + '">';
  html += '<button type="button" class="text-[12px] text-accent hover:underline cursor-pointer" id="autoupdateSelectAllBtn" style="padding:2px 6px;">'
    + escapeHtml(typeof t === 'function' ? t('autoupdate.selectAll') : '全选') + '</button>';
  html += '<button type="button" class="text-[12px] text-muted hover:underline cursor-pointer" id="autoupdateSelectNoneBtn" style="padding:2px 6px;">'
    + escapeHtml(typeof t === 'function' ? t('autoupdate.selectNone') : '取消全选') + '</button>';
  html += '</div>';
  html += '<div id="autoupdateChangedFiles" class="text-[12px] font-mono" style="max-height:240px;overflow-y:auto;"></div>';
  html += '<div class="flex gap-2 mt-3" id="autoupdateActionBtns" style="display:none;">';
  html += '<button type="button" class="ui-btn ui-btn--primary text-[13px]" id="autoupdateConfirmBtn">'
    + escapeHtml(typeof t === 'function' ? t('autoupdate.confirmUpdate') : '确认更新') + '</button>';
  html += '<button type="button" class="ui-btn text-[13px]" id="autoupdateCancelBtn">'
    + escapeHtml(typeof t === 'function' ? t('autoupdate.cancel') : '取消') + '</button>';
  html += '<span id="autoupdateSelectedCount" class="text-[12px] text-muted flex items-center ml-2"></span>';
  html += '</div></div></div>';

  return _sectionCard('autoupdate', html);
}

function _finalizeAutoupdateSection() {
  if (_isFlatConfigTarget() || _activeConfigSection !== 'autoupdate') return;
  var au = (window._currentConfig && window._currentConfig.autoupdate) || {};
  if (typeof syncAutoupdateStatusFromConfig === 'function') {
    syncAutoupdateStatusFromConfig();
  }
  if (typeof _renderAutoupdateMirrors === 'function') {
    _renderAutoupdateMirrors(au.mirrors || []);
  }
  if (typeof _initAutoupdateConfigSection === 'function') {
    _initAutoupdateConfigSection();
  }
}

window._renderAutoupdateSection = _renderAutoupdateSection;
window._finalizeAutoupdateSection = _finalizeAutoupdateSection;
