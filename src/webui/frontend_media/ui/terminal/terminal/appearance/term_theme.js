// ========================= Terminal: Theme & Background =========================
// Split from terminal.js. Handles xterm theme colors and custom/original/theme
// background mode switching, including persistence.

function _attachThemeMethods(ctx) {
  _attachThemeStaticColorMethods(ctx);
  _attachThemeAdaptiveColorMethods(ctx);
  _attachThemeBgModeMethods(ctx);
  _attachThemeBgApplyMethods(ctx);
  _attachThemeBgMigrateMethods(ctx);
  _attachThemeBgSetMethods(ctx);
  _attachThemeBgUiMethods(ctx);
  _attachThemePersistMethods(ctx);
}

function _attachThemeStaticColorMethods(ctx) {
  // Classic VS Code dark terminal colors (bgMode === 'original')
  function _getOriginalTheme() {
    return {
      background: '#1e1e1e', foreground: '#cccccc', cursor: '#ffffff',
      selectionBackground: '#264f78',
      black: '#1e1e1e', red: '#f44747', green: '#6a9955', yellow: '#dcdcaa',
      blue: '#569cd6', magenta: '#c586c0', cyan: '#4ec9b0', white: '#cccccc',
      brightBlack: '#808080', brightRed: '#f44747', brightGreen: '#6a9955',
      brightYellow: '#dcdcaa', brightBlue: '#569cd6', brightMagenta: '#c586c0',
      brightCyan: '#4ec9b0', brightWhite: '#ffffff',
    };
  }
  // Custom image mode colors (bgMode === 'custom', transparent bg)
  function _getCustomTheme(isDark) {
    return {
      background: 'rgba(0,0,0,0)',
      foreground: isDark ? '#edf3ff' : '#162033',
      cursor: isDark ? '#edf3ff' : '#162033',
      selectionBackground: isDark ? 'rgba(42,58,92,0.8)' : 'rgba(219,227,255,0.8)',
      black: '#172131', red: isDark ? '#ff7b7b' : '#d94848',
      green: isDark ? '#37ca7e' : '#1f9d61', yellow: isDark ? '#ffb454' : '#d17b17',
      blue: isDark ? '#8aa4ff' : '#4263eb', magenta: isDark ? '#c084fc' : '#9333ea',
      cyan: isDark ? '#22d3ee' : '#0891b2', white: isDark ? '#edf3ff' : '#f3f6fb',
      brightBlack: isDark ? '#9eabc2' : '#5d6980', brightRed: isDark ? '#ff9b9b' : '#ef4444',
      brightGreen: isDark ? '#5ee6a0' : '#22c55e', brightYellow: isDark ? '#ffc97a' : '#f59e0b',
      brightBlue: isDark ? '#a8bbff' : '#6366f1', brightMagenta: isDark ? '#d4a5ff' : '#a855f7',
      brightCyan: isDark ? '#5ee9f5' : '#06b6d4', brightWhite: '#ffffff',
    };
  }
  ctx.getOriginalTheme = _getOriginalTheme;
  ctx.getCustomTheme = _getCustomTheme;
}

function _attachThemeAdaptiveColorMethods(ctx) {
  // Light/dark UI-following colors (bgMode === 'theme')
  function _getDarkTheme() {
    return {
      background: '#0d1420', foreground: '#edf3ff', cursor: '#edf3ff',
      selectionBackground: '#2a3a5c',
      black: '#172131', red: '#ff7b7b', green: '#37ca7e', yellow: '#ffb454',
      blue: '#8aa4ff', magenta: '#c084fc', cyan: '#22d3ee', white: '#edf3ff',
      brightBlack: '#9eabc2', brightRed: '#ff9b9b', brightGreen: '#5ee6a0',
      brightYellow: '#ffc97a', brightBlue: '#a8bbff', brightMagenta: '#d4a5ff',
      brightCyan: '#5ee9f5', brightWhite: '#ffffff',
    };
  }
  function _getLightTheme() {
    return {
      background: '#ffffff', foreground: '#162033', cursor: '#162033',
      selectionBackground: '#dbe3ff',
      black: '#172131', red: '#d94848', green: '#1f9d61', yellow: '#d17b17',
      blue: '#4263eb', magenta: '#9333ea', cyan: '#0891b2', white: '#f3f6fb',
      brightBlack: '#5d6980', brightRed: '#ef4444', brightGreen: '#22c55e',
      brightYellow: '#f59e0b', brightBlue: '#6366f1', brightMagenta: '#a855f7',
      brightCyan: '#06b6d4', brightWhite: '#ffffff',
    };
  }
  /**
   * Return xterm.js theme colors for the given background mode.
   * @param {string} bgMode - 'theme', 'original', or 'custom'
   */
  function _getTerminalTheme(bgMode) {
    bgMode = bgMode || ctx.terminalBgMode;
    if (bgMode === 'original') return ctx.getOriginalTheme();
    var isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (bgMode === 'custom') return ctx.getCustomTheme(isDark);
    return isDark ? _getDarkTheme() : _getLightTheme();
  }
  ctx.getTerminalTheme = _getTerminalTheme;
}

function _attachThemeBgModeMethods(ctx) {
  /**
   * Apply terminal background mode to all open tabs and persist the setting.
   * @param {string} mode - 'theme', 'original', or 'custom'
   */
  function _applyTerminalBgMode(mode) {
    ctx.terminalBgMode = mode;
    document.documentElement.setAttribute('data-terminal-bg', mode);
    if (ctx.body) {
      ctx.body.classList.remove('terminal-body--original', 'terminal-body--custom');
      if (mode === 'original') ctx.body.classList.add('terminal-body--original');
      else if (mode === 'custom') {
        ctx.body.classList.add('terminal-body--custom');
        ctx.applyCustomBgImage();
      }
    }
    var theme = ctx.getTerminalTheme(mode);
    for (var i = 0; i < ctx.tabs.length; i++) {
      if (ctx.tabs[i].xterm) ctx.tabs[i].xterm.options.theme = theme;
    }
    ctx.saveTerminalBgMode();
    ctx.updateBgModeButton();
    ctx.updateCustomBgControls();
  }
  function _toggleTerminalBgMode() {
    var modes = ['theme', 'original', 'custom'];
    var idx = modes.indexOf(ctx.terminalBgMode);
    _applyTerminalBgMode(modes[(idx + 1) % modes.length]);
  }
  ctx.applyTerminalBgMode = _applyTerminalBgMode;
  ctx.toggleTerminalBgMode = _toggleTerminalBgMode;
}

function _attachThemeBgApplyMethods(ctx) {
  function _applyCustomBgImage() {
    if (!ctx.body) return;
    if (ctx.customBgImage) {
      ctx.body.style.setProperty('--custom-bg-image', 'url(' + ctx.customBgImage + ')');
      ctx.body.style.setProperty('--custom-bg-opacity', ctx.customBgOpacity);
    } else {
      ctx.body.style.removeProperty('--custom-bg-image');
      ctx.body.style.removeProperty('--custom-bg-opacity');
    }
  }
  function _clearCustomBgImage() {
    ctx.customBgImage = '';
    ctx.customBgOpacity = 0.3;
    _applyCustomBgImage();
    ctx.saveTerminalBgMode();
  }
  function _setCustomBgOpacity(opacity) {
    ctx.customBgOpacity = Math.max(0, Math.min(1, opacity));
    if (ctx.body) ctx.body.style.setProperty('--custom-bg-opacity', ctx.customBgOpacity);
    ctx.saveTerminalBgMode();
  }
  function _cycleCustomBgOpacity() {
    var steps = [0.1, 0.3, 0.5, 0.7, 0.9];
    _setCustomBgOpacity(steps[(steps.indexOf(ctx.customBgOpacity) + 1) % steps.length]);
  }
  ctx.applyCustomBgImage = _applyCustomBgImage;
  ctx.clearCustomBgImage = _clearCustomBgImage;
  ctx.setCustomBgOpacity = _setCustomBgOpacity;
  ctx.cycleCustomBgOpacity = _cycleCustomBgOpacity;
}

function _attachThemeBgMigrateMethods(ctx) {
  /**
   * Migrate legacy base64 data URL to server-side file.
   * @param {string} dataUrl - Legacy base64 data URL
   */
  function _migrateBgImageToServer(dataUrl) {
    var parts = dataUrl.split(',');
    if (parts.length !== 2) return;
    var mime = parts[0].match(/:(.*?);/);
    if (!mime) return;
    var bstr = atob(parts[1]);
    var n = bstr.length;
    var u8arr = new Uint8Array(n);
    while (n--) { u8arr[n] = bstr.charCodeAt(n); }
    var blob = new Blob([u8arr], { type: mime[1] });
    var ext = (mime[1].split('/')[1] || 'png').split(';')[0];
    var formData = new FormData();
    formData.append('file', blob, 'terminal-bg-migrated.' + ext);
    fetch('/v1/webui/bg-image', { method: 'POST', body: formData })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (data && data.url) {
          ctx.customBgImage = data.url;
          ctx.applyCustomBgImage();
          ctx.saveTerminalBgMode();
        }
      })
      .catch(function() {});
  }
  ctx.migrateBgImageToServer = _migrateBgImageToServer;
}

function _attachThemeBgSetMethods(ctx) {
  /**
   * Upload a background image file to the server and store its URL.
   * @param {File} file - Image file
   */
  function _setCustomBgImage(file) {
    if (!file || !file.type.startsWith('image/')) return;
    var formData = new FormData();
    formData.append('file', file);
    fetch('/v1/webui/bg-image', { method: 'POST', body: formData })
      .then(function(resp) { return resp.json(); })
      .then(function(data) {
        if (data && data.url) {
          ctx.customBgImage = data.url;
          ctx.applyCustomBgImage();
          ctx.saveTerminalBgMode();
        }
      })
      .catch(function() {});
  }
  function _showImagePicker() {
    var input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.style.display = 'none';
    input.addEventListener('change', function(e) {
      if (e.target.files && e.target.files[0]) _setCustomBgImage(e.target.files[0]);
      document.body.removeChild(input);
    });
    document.body.appendChild(input);
    input.click();
  }
  ctx.setCustomBgImage = _setCustomBgImage;
  ctx.showImagePicker = _showImagePicker;
}

function _attachThemeBgUiMethods(ctx) {
  function _getBgModeLabel() {
    var labels = { 'original': t('terminal.bgClassic'), 'custom': t('terminal.bgCustom'), 'theme': t('terminal.bgProvider') };
    return labels[ctx.terminalBgMode] || t('terminal.bgProvider');
  }
  function _updateBgModeButton() {
    var iconEl = document.getElementById('terminalBgModeIcon');
    var labelEl = document.getElementById('terminalBgModeLabel');
    var icons = { 'original': '☾', 'custom': '▣', 'theme': '☀' };
    if (iconEl) iconEl.textContent = icons[ctx.terminalBgMode] || '☀';
    if (labelEl) labelEl.textContent = _getBgModeLabel();
  }
  function _updateCustomBgControls() {
    var controls = document.getElementById('terminalCustomBgControls');
    var opacityRange = document.getElementById('terminalBgOpacityRange');
    if (controls) controls.style.display = ctx.terminalBgMode === 'custom' ? 'flex' : 'none';
    if (opacityRange) opacityRange.value = Math.round(ctx.customBgOpacity * 100);
  }
  ctx.getBgModeLabel = _getBgModeLabel;
  ctx.updateBgModeButton = _updateBgModeButton;
  ctx.updateCustomBgControls = _updateCustomBgControls;
}

function _attachThemePersistMethods(ctx) {
  async function _saveTerminalBgMode() {
    try {
      var patch = {
        bgMode: ctx.terminalBgMode,
        termFontSize: ctx.termFontSize || 14,
      };
      if (ctx.customBgImage) {
        patch.bgImage = ctx.customBgImage;
        patch.bgOpacity = ctx.customBgOpacity;
      }
      if (typeof mergeTerminalsPersist === 'function') {
        await mergeTerminalsPersist(patch);
      } else if (typeof persistSave === 'function') {
        var existing = await persistLoad('terminals.json') || {};
        Object.assign(existing, patch);
        await persistSave('terminals.json', existing);
      }
    } catch (e) { /* ignore */ }
  }
  async function _loadTerminalBgMode() {
    try {
      if (typeof persistLoad !== 'function') return;
      var data = await persistLoad('terminals.json');
      if (data && data.bgMode) ctx.terminalBgMode = data.bgMode;
      if (data && typeof data.termFontSize === 'number') {
        ctx.termFontSize = data.termFontSize;
      } else {
        ctx.termFontSize = ctx.termFontSize || 14;
      }
      if (data && data.bgImage) {
        if (data.bgImage.indexOf('data:') === 0) ctx.migrateBgImageToServer(data.bgImage);
        else ctx.customBgImage = data.bgImage;
      }
      if (data && typeof data.bgOpacity === 'number') ctx.customBgOpacity = data.bgOpacity;
    } catch (e) { /* ignore */ }
    ctx.applyTerminalBgMode(ctx.terminalBgMode);
  }
  ctx.saveTerminalBgMode = _saveTerminalBgMode;
  ctx.loadTerminalBgMode = _loadTerminalBgMode;
}
