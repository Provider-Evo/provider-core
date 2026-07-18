/**
 * TerminalSidebar -- right-side collapsible sidebar for the terminal page.
 *
 * Three sub-tabs:
 * - servers: saved SSH connections (CRUD + connect)
 * - audit: session recording audit log (list/detail/delete + record toggle)
 * - commands: quick command list (CRUD + import/export + send-to-terminal)
 *
 * Implementation lives in sidebar/core.js, sidebar/servers.js, sidebar/
 * audit.js, sidebar/cmds.js, sidebar/dialogs.js -- each attaches its
 * methods onto a shared ctx object. This file only builds ctx and wires the
 * modules together, matching term.js conventions: ES5, var only,
 * showConfirmDialog/toast for UI feedback, t() for i18n strings.
 */

var TerminalSidebar = (function () {
  var ctx = {
    auditPage: 1,
    auditPageSize: 20,
    auditTotal: 0,
    auditEnabled: false,
    servers: [],
    commands: [],
    stripAnsiSequences: function (text) {
      if (!text) return '';
      return text.replace(/\x1b\[[0-9;?]*[a-zA-Z]/g, '').replace(/\x1b\][^\x07]*\x07/g, '');
    },
  };

  window._attachTerminalSidebarServers(ctx);
  window._attachTerminalSidebarAudit(ctx);
  window._attachTerminalSidebarCommands(ctx);
  window._attachTerminalSidebarDialogs(ctx);
  window._attachTerminalSidebarCore(ctx);

  return {
    init: ctx.init,
  };
})();

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function () { TerminalSidebar.init(); });
} else {
  TerminalSidebar.init();
}
