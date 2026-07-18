// === RESTORED FROM BACKUP v2.2.266 ===
// Content lost during iterative split; recovered from .backup/.
// Loaded in order by init.js. Some post-v2.2.266 features may be missing.
//

/**
 * Terminal Tab -- xterm.js-based terminal with local and SSH support.
 *
 * Uses @xterm/xterm v5 for rendering and keyboard capture (loaded via CDN).
 * Uses @xterm/addon-fit for automatic resize to container dimensions.
 *
 * Features:
 * - xterm.js for full VT100/xterm emulation (ANSI, cursor, scrollback, etc.)
 * - Unified TabBar for tab rendering (horizontal/vertical/compressed layouts)
 * - Local terminal via WebSocket to backend (ConPTY or pipe mode)
 * - SSH remote terminal via paramiko on backend
 * - ResizeObserver-based resize propagation to backend
 * - Right-click context menu
 * - SSH dialog with quick-parse (user@host:port, user:pass@host:port)
 * - Saved SSH connections via persist API
 *
 * Requires (loaded by LazyLoader before this script):
 * - @xterm/xterm v5.5.0  (global: Terminal)
 * - @xterm/addon-fit v0.10.0  (global: FitAddon)
 * - TabBar (global: TabBar)
 *
 * Implementation is split across this file and the sibling files under
 * ./terminal/ (terminal/core/term_links.js, terminal/core/term_pane.js,
 * terminal/core/term_resize.js, terminal/core/term_init.js,
 * term_thumb.js, term_theme.js, term_color.js,
 * term_search.js, term_ctxmenu.js, term_split.js,
 * term_chooser.js, term_ssh.js, term_wsock.js). Each sibling
 * defines a global `_attachXxxMethods(ctx)` function that hangs its methods
 * off the shared `ctx` object created below, so all submodules operate on
 * the same closure state (tabs, active tab, TabBar instance, etc.) as this
 * file. Load order (enforced by lazy.js) guarantees the sibling globals
 * exist before this IIFE runs.
 *
 * This file itself retains only: tab-record public-API wrappers and the
 * `TerminalManager` object literal itself. TabBar construction and
 * activation wiring live in terminal/core/term_init.js; resize/visibility
 * tracking lives in terminal/core/term_resize.js; tab/pane creation and
 * xterm wiring live in terminal/core/term_pane.js; link detection lives
 * in terminal/core/term_links.js.
 */

// ========================= TerminalManager =========================

var TerminalManager = (function () {
  // Shared context object: holds all mutable state and cross-module method
  // references. Sibling terminal_*.js files receive this same object via
  // their _attachXxxMethods(ctx) call and read/write it directly. Built by
  // _createTerminalManagerCtx() in terminal/core/term_tabops.js so this IIFE
  // stays a thin facade.
  var ctx = _createTerminalManagerCtx();

  // Wire up submodules: each attach function hangs its methods onto ctx.
  // Must run before init()/createTab() are invoked, and before any of
  // this file's own functions that call ctx.<method> execute.
  _wireTerminalManagerSubmodules(ctx);

  // ========================= Initialization =========================
  //
  // TabBar construction, background/resize control wiring, body click
  // handlers, and Router activate/deactivate registration all live in
  // terminal/core/term_init.js as ctx.runInit(). This file just
  // forwards init() to it.

  function init() {
    ctx.runInit();
  }

  // ========================= Public API =========================
  //
  // Built by _buildTerminalManagerPublicApi() in terminal/core/term_tabops.js.

  return _buildTerminalManagerPublicApi(ctx, init);
})();

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function () { TerminalManager.init(); });
} else {
  TerminalManager.init();
}
