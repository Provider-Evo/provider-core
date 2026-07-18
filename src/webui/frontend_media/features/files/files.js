/**
 * File Manager Tab -- directory browsing with tab management.
 *
 * This file is now a thin entry point. All implementation has moved into
 * features/files/modules/ (loaded beforehand via LazyLoader's
 * TAB_RESOURCES.files array in base/core/lazy/lazy_assets.js). Those sibling files
 * declare shared state and functions as top-level globals (matching the
 * pattern used by base/core/tabbar/), so this file only needs to expose
 * the public FileManager API and perform auto-init, exactly as before.
 *
 * Features:
 * - Horizontal tab bar (create/switch/close)
 * - Directory listing with sortable columns
 * - Breadcrumb navigation and back/forward history
 * - Editable address bar
 * - Right-click context menu (open, download, rename, delete, new folder)
 * - File preview modal (text with line numbers, images inline)
 * - Download files
 * - Session persistence via persist API
 */
var FileManager = {
  init: init,
  createTab: createTab,
  closeTab: closeTab,
  download: _downloadFile,
  openPath: openPath,
};

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', function () { FileManager.init(); });
} else {
  FileManager.init();
}
