/**
 * TerminalState -- shared state for TerminalManager modules.
 * Loaded before other terminal-*.js files by LazyLoader.
 */
var TerminalState = (function () {
  var S = _createTerminalStateData();
  _attachTerminalStateMethods(S);

  return _buildTerminalStatePublicApi(S);
})();
