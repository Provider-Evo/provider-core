/**
 * Chat attachment tiles + media/file preview (NavoIM viewer + files preview patterns).
 */
var ChatAttachments = (function() {
  'use strict';

  var _installed = false;
  var _viewerState = null;
  var _turnStore = new WeakMap();

  var _ctx = {
    turnStore: _turnStore,
    getViewerState: function() { return _viewerState; },
    setViewerState: function(state) { _viewerState = state; },
    isInstalled: function() { return _installed; },
    setInstalled: function(value) { _installed = value; },
  };

  _attachAttachmentsHelperMethods(_ctx);
  _attachAttachmentsViewerMethods(_ctx);
  _attachAttachmentsPreviewMethods(_ctx);
  _attachAttachmentsCollectMethods(_ctx);
  _attachAttachmentsEventsMethods(_ctx);

  return {
    collectAttachments: _ctx.collectAttachments,
    buildHtml: _ctx.buildHtml,
    mountInto: _ctx.mountInto,
    install: _ctx.install,
  };
})();
