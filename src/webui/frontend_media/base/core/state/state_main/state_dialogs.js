// ========================= Dialogs & Toast =========================
// 拆分自 state.js。依赖 state_core.js（toastWrap）已加载。

function toast(message, type) {
  const node = document.createElement('div');
  node.className = 'min-w-[220px] max-w-[340px] rounded-xl border border-border bg-panel shadow-panel px-3 py-2.5 text-[13px] leading-relaxed toast-enter';
  node.textContent = '[' + (type || 'info') + '] ' + message;
  toastWrap.appendChild(node);
  // Animate toast entrance if MotionKit is available
  if (typeof animateToastIn === 'function') {
    animateToastIn(node);
  }
  setTimeout(function() {
    // Animate toast exit
    if (typeof MotionKit !== 'undefined') {
      MotionKit.opacityTo(node, 0, 5);
      setTimeout(function() { node.remove(); }, 200);
    } else {
      node.remove();
    }
  }, 3200);
}

function showConfirmDialog(message, options) {
  if (document.querySelector('.confirm-overlay')) {
    return Promise.resolve(false);
  }
  options = options || {};
  var title = options.title || t('dialog.titleDefault');
  var confirmText = options.confirmText || t('dialog.ok');
  var cancelText = options.cancelText || t('dialog.cancel');

  return new Promise(function(resolve) {
    var overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    overlay.innerHTML =
      '<div class="confirm-dialog">' +
      '<div class="confirm-dialog-title">' + title + '</div>' +
      '<div class="confirm-dialog-message">' + message + '</div>' +
      '<div class="confirm-dialog-actions">' +
      '<button class="confirm-dialog-btn confirm-dialog-cancel" type="button">' + cancelText + '</button>' +
      '<button class="confirm-dialog-btn confirm-dialog-ok" type="button">' + confirmText + '</button>' +
      '</div></div>';

    document.body.appendChild(overlay);
    requestAnimationFrame(function() { overlay.classList.add('is-visible'); });

    function close(result) {
      overlay.classList.remove('is-visible');
      setTimeout(function() { overlay.remove(); resolve(result); }, 180);
    }

    overlay.querySelector('.confirm-dialog-ok').addEventListener('click', function() { close(true); });
    overlay.querySelector('.confirm-dialog-cancel').addEventListener('click', function() { close(false); });
    overlay.addEventListener('click', function(e) { if (e.target === overlay) close(false); });
  });
}

function showInfoDialog(message, options) {
  if (document.querySelector('.confirm-overlay')) {
    return Promise.resolve();
  }
  options = options || {};
  var title = options.title || t('dialog.titleDefault');
  var confirmText = options.confirmText || t('dialog.ok');

  return new Promise(function(resolve) {
    var overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    overlay.innerHTML =
      '<div class="confirm-dialog">' +
      '<div class="confirm-dialog-title">' + title + '</div>' +
      '<div class="confirm-dialog-message">' + message + '</div>' +
      '<div class="confirm-dialog-actions">' +
      '<button class="confirm-dialog-btn confirm-dialog-ok" type="button">' + confirmText + '</button>' +
      '</div></div>';

    document.body.appendChild(overlay);
    requestAnimationFrame(function() { overlay.classList.add('is-visible'); });

    function close() {
      overlay.classList.remove('is-visible');
      setTimeout(function() { overlay.remove(); resolve(); }, 180);
    }

    overlay.querySelector('.confirm-dialog-ok').addEventListener('click', close);
    overlay.addEventListener('click', function(e) { if (e.target === overlay) close(); });
  });
}

function showInputDialog(message, options) {
  options = options || {};
  var title = options.title || t('dialog.inputTitle');
  var defaultValue = options.defaultValue || '';
  var confirmText = options.confirmText || t('dialog.ok');
  var cancelText = options.cancelText || t('dialog.cancel');
  var placeholder = options.placeholder || '';

  return new Promise(function(resolve) {
    var overlay = document.createElement('div');
    overlay.className = 'confirm-overlay';
    overlay.innerHTML =
      '<div class="confirm-dialog">' +
      '<div class="confirm-dialog-title">' + title + '</div>' +
      '<div class="confirm-dialog-message">' + message + '</div>' +
      '<input type="text" class="input-dialog-input" value="' + _escapeAttr(defaultValue) + '" placeholder="' + _escapeAttr(placeholder) + '">' +
      '<div class="confirm-dialog-actions">' +
      '<button class="confirm-dialog-btn confirm-dialog-cancel" type="button">' + cancelText + '</button>' +
      '<button class="confirm-dialog-btn confirm-dialog-ok" type="button">' + confirmText + '</button>' +
      '</div></div>';

    document.body.appendChild(overlay);
    requestAnimationFrame(function() { overlay.classList.add('is-visible'); });

    var input = overlay.querySelector('.input-dialog-input');
    input.focus();
    input.select();

    function close(result) {
      overlay.classList.remove('is-visible');
      setTimeout(function() { overlay.remove(); resolve(result); }, 180);
    }

    function confirm() {
      var value = input.value.trim();
      close(value || null);
    }

    overlay.querySelector('.confirm-dialog-ok').addEventListener('click', confirm);
    overlay.querySelector('.confirm-dialog-cancel').addEventListener('click', function() { close(null); });
    overlay.addEventListener('click', function(e) { if (e.target === overlay) close(null); });
    input.addEventListener('keydown', function(e) {
      if (e.key === 'Enter') { e.preventDefault(); confirm(); }
      if (e.key === 'Escape') close(null);
    });
  });
}

function showModal(options) {
  options = options || {};
  var title = options.title || '';
  var content = options.content || '';
  var className = options.className || 'confirm-overlay';
  var dialogClass = options.dialogClass || 'confirm-dialog';
  var showClose = options.showClose !== false;
  var closeOnOverlay = options.closeOnOverlay !== false;
  var onClose = options.onClose || null;

  var overlay = document.createElement('div');
  overlay.className = className;

  var html = '<div class="' + dialogClass + '">';
  if (title) {
    html += '<div class="confirm-dialog-title">' + title + '</div>';
  }
  html += '<div class="confirm-dialog-message">' + content + '</div>';
  if (showClose) {
    html += '<div class="confirm-dialog-actions">';
    html += '<button class="confirm-dialog-btn confirm-dialog-ok" type="button">' + t('dialog.ok') + '</button>';
    html += '</div>';
  }
  html += '</div>';
  overlay.innerHTML = html;

  document.body.appendChild(overlay);
  requestAnimationFrame(function() { overlay.classList.add('is-visible'); });

  function close() {
    overlay.classList.remove('is-visible');
    setTimeout(function() {
      overlay.remove();
      if (onClose) onClose();
    }, 180);
  }

  overlay.querySelector('.confirm-dialog-ok').addEventListener('click', close);
  if (closeOnOverlay) {
    overlay.addEventListener('click', function(e) { if (e.target === overlay) close(); });
  }

  return {
    close: close,
    getElement: function() { return overlay; },
    getContentElement: function() { return overlay.querySelector('.' + dialogClass); }
  };
}

function _escapeAttr(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
}
