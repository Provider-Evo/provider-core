/**
 * Persist chat multimodal blobs to /v1/webui/chat-media and hydrate on load.
 * Facade over mediapersist_util.js / mediapersist_export.js /
 * mediapersist_hydrate.js, which must load before this file.
 */
var ChatMediaPersist = (function() {
  'use strict';

  return {
    REF_PREFIX: ChatMediaPersistUtil.REF_PREFIX,
    isRef: ChatMediaPersistUtil.isRef,
    exportHistory: ChatMediaPersistExport.exportHistory,
    hydrateHistory: ChatMediaPersistHydrate.hydrateHistory,
  };
})();
