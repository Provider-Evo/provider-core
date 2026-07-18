// Shared tab color picker: preset swatches + custom hue/alpha/RGB/hex panel.
// Used by both terminal (term_color.js) and file manager (m3/color.js).
// Call _showTabColorPicker(tabId, x, y, opts) where opts = {currentColor,
// headerLabel, onApply(color), onReset()}.

var _tabColorPickerEl = null;

// ========================= Color Utilities =========================

function _tabColorHexToRgb(hex) {
  var m = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex || '');
  if (!m) return { r: 255, g: 255, b: 255 };
  return { r: parseInt(m[1], 16), g: parseInt(m[2], 16), b: parseInt(m[3], 16) };
}

function _tabColorRgbToHex(r, g, b) {
  function h(v) {
    v = Math.max(0, Math.min(255, Math.round(v)));
    var s = v.toString(16);
    return s.length === 1 ? '0' + s : s;
  }
  return '#' + h(r) + h(g) + h(b);
}

function _tabColorHslToRgb(hh, s, l) {
  hh = (hh % 360) / 360;
  s = s / 100;
  l = l / 100;
  if (s === 0) {
    var v = Math.round(l * 255);
    return { r: v, g: v, b: v };
  }
  function hue2rgb(p, q, tt) {
    if (tt < 0) tt += 1;
    if (tt > 1) tt -= 1;
    if (tt < 1 / 6) return p + (q - p) * 6 * tt;
    if (tt < 1 / 2) return q;
    if (tt < 2 / 3) return p + (q - p) * (2 / 3 - tt) * 6;
    return p;
  }
  var q = l < 0.5 ? l * (1 + s) : l + s - l * s;
  var p = 2 * l - q;
  return {
    r: Math.round(hue2rgb(p, q, hh + 1 / 3) * 255),
    g: Math.round(hue2rgb(p, q, hh) * 255),
    b: Math.round(hue2rgb(p, q, hh - 1 / 3) * 255),
  };
}

// ========================= Preset Data =========================

var _TAB_COLOR_PRESETS = [
  '#dc3545', '#ff4444', '#ff6b9d', '#e91e63',
  '#fd7e14', '#ff8800', '#ffc107', '#ffcd38',
  '#28a745', '#44cc44', '#20c997', '#17a2b8',
  '#007bff', '#4488ff', '#6f42c1', '#aa44ff',
];

// ========================= HTML Builder =========================

function _buildTabColorPickerHtml(currentColor, headerLabel) {
  var header = headerLabel || t('terminal.tabColor');
  var html = '<div class="color-picker-header">' + header + '</div>';
  html += '<div class="color-presets"><div class="color-grid">';
  for (var i = 0; i < _TAB_COLOR_PRESETS.length; i++) {
    var c = _TAB_COLOR_PRESETS[i];
    var sel = (currentColor && currentColor.toLowerCase() === c.toLowerCase()) ? ' selected' : '';
    html += '<div class="color-cell' + sel + '" data-color="' + c + '" style="background:' + c + '"></div>';
  }
  html += '</div></div>';
  html += '<div class="color-actions">';
  html += '<button type="button" class="color-reset">' + t('terminal.reset') + '</button>';
  html += '<button type="button" class="color-custom">' + t('terminal.custom') + ' &gt;</button>';
  html += '</div>';
  html += '<div class="color-custom-panel" style="display:none">';
  html += '<div class="color-preview-box"><div class="color-preview"></div></div>';
  html += '<div class="color-hue-slider"><input type="range" min="0" max="360" value="0"></div>';
  html += '<div class="color-alpha-slider"><input type="range" min="0" max="100" value="100"></div>';
  html += '<div class="color-more"><button type="button">' + t('terminal.more') + ' &gt;</button></div>';
  html += '<div class="color-rgb-panel" style="display:none">';
  html += '<div class="rgb-inputs">';
  html += '<div class="rgb-row"><input type="text" class="rgb-hex" value="#FFFFFF"></div>';
  html += '<div class="rgb-row"><label>R</label><input type="number" class="rgb-r" min="0" max="255" value="255"></div>';
  html += '<div class="rgb-row"><label>G</label><input type="number" class="rgb-g" min="0" max="255" value="255"></div>';
  html += '<div class="rgb-row"><label>B</label><input type="number" class="rgb-b" min="0" max="255" value="255"></div>';
  html += '</div>';
  html += '<button type="button" class="color-confirm">' + t('terminal.confirm') + '</button>';
  html += '</div></div>';
  return html;
}

// ========================= Picker Lifecycle =========================

function _hideTabColorPicker() {
  if (_tabColorPickerEl) {
    _tabColorPickerEl.remove();
    _tabColorPickerEl = null;
  }
}

function _tabColorUpdatePreview(picker) {
  var hue = parseInt(picker.querySelector('.color-hue-slider input').value, 10) || 0;
  var alpha = parseInt(picker.querySelector('.color-alpha-slider input').value, 10);
  if (isNaN(alpha)) alpha = 100;
  var rgb = _tabColorHslToRgb(hue, 100, 50);
  var hex = _tabColorRgbToHex(rgb.r, rgb.g, rgb.b);
  var preview = picker.querySelector('.color-preview');
  if (preview) preview.style.background = 'rgba(' + rgb.r + ',' + rgb.g + ',' + rgb.b + ',' + (alpha / 100) + ')';
  var hexInput = picker.querySelector('.rgb-hex');
  if (hexInput) hexInput.value = hex.toUpperCase();
  if (picker.querySelector('.rgb-r')) picker.querySelector('.rgb-r').value = rgb.r;
  if (picker.querySelector('.rgb-g')) picker.querySelector('.rgb-g').value = rgb.g;
  if (picker.querySelector('.rgb-b')) picker.querySelector('.rgb-b').value = rgb.b;
  return hex;
}

// ========================= Picker Event Binding =========================

function _bindPickerPresetCells(picker, onApply) {
  var cells = picker.querySelectorAll('.color-cell');
  for (var i = 0; i < cells.length; i++) {
    (function (cell) {
      cell.addEventListener('click', function () {
        onApply(cell.getAttribute('data-color'));
        _hideTabColorPicker();
      });
    })(cells[i]);
  }
}

function _bindPickerPanelToggles(picker) {
  // Toggle custom panel visibility and refresh preview
  picker.querySelector('.color-custom').addEventListener('click', function () {
    var panel = picker.querySelector('.color-custom-panel');
    panel.style.display = panel.style.display === 'none' ? 'block' : 'none';
    _tabColorUpdatePreview(picker);
  });
  // Hue / alpha sliders update preview
  picker.querySelector('.color-hue-slider input').addEventListener('input', function () {
    _tabColorUpdatePreview(picker);
  });
  picker.querySelector('.color-alpha-slider input').addEventListener('input', function () {
    _tabColorUpdatePreview(picker);
  });
  // More / less toggle for RGB input panel
  var moreBtn = picker.querySelector('.color-more button');
  moreBtn.addEventListener('click', function () {
    var rgbPanel = picker.querySelector('.color-rgb-panel');
    if (rgbPanel.style.display === 'none') {
      rgbPanel.style.display = 'block';
      moreBtn.textContent = t('terminal.less') + ' <';
    } else {
      rgbPanel.style.display = 'none';
      moreBtn.textContent = t('terminal.more') + ' >';
    }
  });
}

function _bindPickerRgbInputs(picker, onApply) {
  var hexInput = picker.querySelector('.rgb-hex');
  var rInput = picker.querySelector('.rgb-r');
  var gInput = picker.querySelector('.rgb-g');
  var bInput = picker.querySelector('.rgb-b');
  // Hex input drives RGB fields
  hexInput.addEventListener('change', function () {
    var rgb = _tabColorHexToRgb(hexInput.value);
    rInput.value = rgb.r;
    gInput.value = rgb.g;
    bInput.value = rgb.b;
    var preview = picker.querySelector('.color-preview');
    if (preview) preview.style.background = hexInput.value;
  });
  // RGB inputs drive hex field
  function syncRgbToHex() {
    var hex = _tabColorRgbToHex(
      parseInt(rInput.value, 10) || 0,
      parseInt(gInput.value, 10) || 0,
      parseInt(bInput.value, 10) || 0
    );
    hexInput.value = hex.toUpperCase();
    var preview = picker.querySelector('.color-preview');
    if (preview) preview.style.background = hex;
  }
  rInput.addEventListener('input', syncRgbToHex);
  gInput.addEventListener('input', syncRgbToHex);
  bInput.addEventListener('input', syncRgbToHex);
  // Confirm applies current hex value
  picker.querySelector('.color-confirm').addEventListener('click', function () {
    onApply(hexInput.value);
    _hideTabColorPicker();
  });
}

// ========================= Picker Show =========================

/**
 * Show the tab color picker at screen position (x, y).
 * opts.onApply(color) is called when user confirms a color.
 * opts.onReset() is called when user resets.
 */
function _showTabColorPicker(tabId, x, y, opts) {
  _hideTabColorPicker();
  opts = opts || {};
  var onApply = opts.onApply || function () {};
  var onReset = opts.onReset || function () {};

  var picker = document.createElement('div');
  picker.className = 'terminal-color-picker';
  picker.innerHTML = _buildTabColorPickerHtml(opts.currentColor || '', opts.headerLabel || null);
  picker.style.left = x + 'px';
  picker.style.top = y + 'px';
  document.body.appendChild(picker);
  _tabColorPickerEl = picker;

  _bindPickerPresetCells(picker, onApply);
  picker.querySelector('.color-reset').addEventListener('click', function () {
    onReset();
    _hideTabColorPicker();
  });
  _bindPickerPanelToggles(picker);
  _bindPickerRgbInputs(picker, onApply);

  // Adjust position to stay within viewport
  var rect = picker.getBoundingClientRect();
  if (rect.right > window.innerWidth) {
    picker.style.left = (window.innerWidth - rect.width - 8) + 'px';
  }
  if (rect.bottom > window.innerHeight) {
    picker.style.top = (window.innerHeight - rect.height - 8) + 'px';
  }
}
