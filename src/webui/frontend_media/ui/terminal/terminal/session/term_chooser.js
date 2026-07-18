// ========================= Terminal: Chooser Tab (New Tab Page) =========================
// Split from terminal.js. Handles the "new tab" chooser page and its
// conversion into a real local or SSH terminal tab.

function _attachChooserMethods(ctx) {
  var m = {};

  _attachChooserMethodsSubCreate(ctx, m);
  _attachChooserMethodsSubWelcome(ctx, m);
  _attachChooserMethodsSubConvert(ctx, m);

  ctx.createChooserTab = m._createChooserTab;
  ctx.convertChooserToLocal = m._convertChooserToLocal;
  ctx.convertChooserToSSH = m._convertChooserToSSH;
}

function _attachChooserMethodsSubCreate(ctx, m) {
  _attachChooserMethodsSubCreateTab(ctx, m);
  _attachChooserMethodsSubCreatePane(ctx, m);
}

function _attachChooserMethodsSubCreateTab(ctx, m) {

  /**
   * Create a new chooser tab — similar to Chrome's new-tab page.
   * The tab renders the welcome/guide page inside its pane, with buttons
   * for "本地终端" and "远程终端".  Clicking either converts the tab
   * into a real terminal of that type.
   */
  m._createChooserTab = function _createChooserTab() {
    // Ensure the terminal sidebar tab is visible
    if (typeof switchTab === 'function') {
      switchTab('terminal');
    }

    var tabId = 'chooser-' + Date.now();
    var name = t('terminal.newTabPage');

    var tab = {
      id: tabId,
      kind: 'chooser',
      name: name,
      status: 'idle',
      xterm: null,
      fitAddon: null,
      ws: null,
      sessionId: null,
      options: {},
      _resizeObserver: null,
      _container: null,
    };

    ctx.tabs.push(tab);

    m._createChooserPane(tabId, tab, name);
  };
}

function _attachChooserMethodsSubCreatePane(ctx, m) {

  /**
   * Create the DOM pane for a chooser tab, wire it into the TabBar and
   * body, and hook up the welcome page buttons.
   */
  m._createChooserPane = function _createChooserPane(tabId, tab, name) {
    var paneDiv = document.createElement('div');
    paneDiv.className = 'terminal-pane';
    paneDiv.id = 'terminal-pane-' + tabId;
    paneDiv.style.cssText = 'width:100%;height:100%;display:none;';

    var welcomeEl = m._renderWelcomePage();
    paneDiv.appendChild(welcomeEl);
    ctx.body.appendChild(paneDiv);

    // Add tab to TabBar
    if (ctx.bar) {
      ctx.bar.addTab({
        id: tabId,
        type: 'terminal',
        icon: '+',
        title: name,
        closable: true,
      });
      ctx.bar.setActive(tabId);
    }

    ctx.activeTabId = tabId;
    ctx.showTabPane(tabId);

    // Wire up the welcome page buttons
    m._wireWelcomePageButtons(welcomeEl, tabId);
  };
}

function _attachChooserMethodsSubWelcome(ctx, m) {

  /**
   * Render the welcome/guide page element — the same UI shown in the
   * zero-tab empty state, but reusable inside any tab pane.
   * Returns a DOM element.
   */
  m._renderWelcomePage = function _renderWelcomePage() {
    var div = document.createElement('div');
    div.className = 'terminal-empty-state';
    div.innerHTML =
      '<div class="terminal-empty-state-icon">&#9002;_</div>' +
      '<div class="terminal-empty-state-text">' + t('terminal.chooseType') + '</div>' +
      '<div class="terminal-empty-state-actions">' +
      '<button type="button" class="welcome-local-btn">' + t('terminal.addLocal') + '</button>' +
      '<button type="button" class="welcome-ssh-btn">' + t('terminal.addSSH') + '</button>' +
      '</div>';
    return div;
  };

  /**
   * Wire up the Local / Remote buttons inside a welcome page element
   * to convert the owning chooser tab into a real terminal tab.
   */
  m._wireWelcomePageButtons = function _wireWelcomePageButtons(el, tabId) {
    var localBtn = el.querySelector('.welcome-local-btn');
    var sshBtn = el.querySelector('.welcome-ssh-btn');

    if (localBtn) {
      localBtn.addEventListener('click', function () {
        m._convertChooserToLocal(tabId);
      });
    }

    if (sshBtn) {
      sshBtn.addEventListener('click', function () {
        m._convertChooserToSSH(tabId);
      });
    }
  };
}

function _attachChooserMethodsSubConvert(ctx, m) {

  /**
   * Convert a chooser tab into a local terminal tab.
   * Updates tab metadata, tab bar display, then initialises xterm.js + WS.
   */
  m._convertChooserToLocal = function _convertChooserToLocal(tabId) {
    var tab = ctx.getTabById(tabId);
    if (!tab || tab.kind !== 'chooser') return;

    ctx.tabCounter++;
    tab.kind = 'local';
    tab.name = t('terminal.localN', { index: ctx.tabCounter });
    tab.status = 'connecting';

    // Update TabBar display
    if (ctx.bar) {
      ctx.bar.setTitle(tabId, tab.name);
      ctx.bar.setIcon(tabId, '');
      ctx.bar.setStatus(tabId, 'connecting');
    }

    // _initTerminal removes the old pane and creates a fresh xterm pane
    ctx.initTerminal(tab);
  };

  /**
   * Convert a chooser tab into an SSH terminal tab.
   * Opens the SSH dialog; on successful connection the tab is converted.
   * If the user cancels, the chooser tab remains unchanged.
   */
  m._convertChooserToSSH = function _convertChooserToSSH(tabId) {
    ctx.showSSHDialog(tabId);
  };
}
