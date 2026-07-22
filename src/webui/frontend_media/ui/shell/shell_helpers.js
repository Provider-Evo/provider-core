/**
 * WebUI shell inner methods extracted from shell.js IIFE.
 * Free-standing helpers that read/write state via ctx.
 */

var SHELL_TAB_ALIASES = {
  overview: 'dashboard',
  stats: 'dashboard',
  platforms: 'routing',
  models: 'routing',
  config: 'settings',
  autoupdate: 'settings',
};

var SHELL_PRIMARY_TABS = ['dashboard', 'routing', 'keys', 'plugins', 'requests', 'settings'];
var SHELL_TOOL_TABS = ['chat', 'terminal', 'files', 'logs'];

function _shellResolveTab(tab) {
  return SHELL_TAB_ALIASES[tab] || tab;
}

function _shellIsPrimaryTab(tab) {
  return SHELL_PRIMARY_TABS.indexOf(tab) !== -1;
}

function _shellIsToolTab(tab) {
  return SHELL_TOOL_TABS.indexOf(tab) !== -1;
}

function _shellSettingsSectionForTab(tab) {
  if (tab === 'autoupdate' || tab === 'config') return 'config';
  return null;
}

function _shellSyncSettingsPanes(ctx) {
  document.querySelectorAll('.settings-pane').forEach(function (node) {
    var active = node.dataset.settingsPane === ctx.settingsSection;
    node.classList.toggle('active', active);
    node.classList.toggle('hidden', !active);
  });
}

function _shellSyncSettingsSubnav(ctx) {
  document.querySelectorAll('.settings-subnav-btn').forEach(function (node) {
    node.classList.toggle('active', node.dataset.settingsSection === ctx.settingsSection);
  });
}

function _shellSyncNavActive(activeTab) {
  document.querySelectorAll('.sidebar-nav-item[data-tab]').forEach(function (node) {
    var tab = node.dataset.tab;
    node.classList.toggle('active', !!activeTab && tab === activeTab);
  });
}

function _shellSetSettingsSection(ctx, section) {
  var next = section || 'config';
  if (next === 'autoupdate') next = 'config';
  ctx.settingsSection = next;
  localStorage.setItem('provider.webui.settingsSection', ctx.settingsSection);
  _shellSyncSettingsPanes(ctx);
  _shellSyncSettingsSubnav(ctx);
}

function _shellSetLastPrimaryTab(ctx, tab) {
  if (!_shellIsPrimaryTab(tab)) return;
  ctx.lastPrimaryTab = tab;
  localStorage.setItem('provider.webui.lastPrimaryTab', tab);
}

function _shellSyncToolViewBar(tab) {
  var bar = document.getElementById('toolViewBar');
  var titleEl = document.getElementById('toolViewTitle');
  var bodyEl = document.getElementById('webuiBody');
  if (!bar) return;
  var isTool = _shellIsToolTab(tab);
  bar.classList.toggle('hidden', !isTool);
  bar.setAttribute('aria-hidden', isTool ? 'false' : 'true');
  if (bodyEl) bodyEl.classList.toggle('is-tool-view', isTool);
  if (titleEl && isTool) {
    var labelNode = document.getElementById('tab-' + tab + '-button');
    titleEl.textContent = labelNode ? labelNode.textContent.trim() : tab;
  }
  if (isTool) {
    var content = document.querySelector('.webui-content');
    if (content) content.scrollTop = 0;
  }
}

function _shellOnTabActivated(ctx, tab) {
  var resolved = _shellResolveTab(tab);
  if (_shellIsPrimaryTab(tab)) _shellSetLastPrimaryTab(ctx, tab);
  if (resolved === 'settings') _shellSetLastPrimaryTab(ctx, 'settings');
  if (tab === 'autoupdate') {
    if (typeof setConfigTarget === 'function') setConfigTarget('main');
    if (typeof setActiveConfigSection === 'function') setActiveConfigSection('autoupdate');
  }
  if (resolved === 'settings') {
    var section = _shellSettingsSectionForTab(tab);
    if (section) _shellSetSettingsSection(ctx, section);
    else _shellSyncSettingsPanes(ctx);
  }
  _shellSyncNavActive(_shellIsPrimaryTab(tab) || _shellIsToolTab(tab) ? tab : resolved);
  _shellSyncToolViewBar(tab);
}

function _shellBind(ctx, leaveTools) {
  if (ctx.settingsSection === 'autoupdate') {
    ctx.settingsSection = 'config';
    localStorage.setItem('provider.webui.settingsSection', 'config');
  }
  _wsBindSettingsSubnav();
  var backBtn = document.getElementById('toolViewBackBtn');
  if (backBtn && !backBtn.dataset.bound) {
    backBtn.dataset.bound = '1';
    backBtn.addEventListener('click', function () { leaveTools(); });
  }
  _wsBindToolViewEscape();
  _wsBindSidebarCollapse();
  _shellSyncSettingsPanes(ctx);
  _shellSyncSettingsSubnav(ctx);
}
