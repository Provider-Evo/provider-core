function copyText(text, successMessage) {
  var copyPromise;
  if (navigator.clipboard && navigator.clipboard.writeText) {
    copyPromise = navigator.clipboard.writeText(text);
  } else {
    // Fallback for insecure contexts (HTTP)
    var textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed';
    textarea.style.left = '-9999px';
    textarea.style.top = '-9999px';
    document.body.appendChild(textarea);
    textarea.focus();
    textarea.select();
    var success = false;
    try {
      success = document.execCommand('copy');
    } catch (e) {
      console.error('Copy failed:', e);
    }
    document.body.removeChild(textarea);
    copyPromise = success ? Promise.resolve() : Promise.reject(new Error('Copy failed'));
  }
  copyPromise.then(function() {
    toast(successMessage, 'ok');
  }).catch(function(error) {
    toast(t('actions.copyFailed', { error: String(error) }), 'error');
  });
}

function exportSummary() {
  const payload = JSON.stringify(state.summary || {}, null, 2);
  const blob = new Blob([payload], { type: 'application/json' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = 'provider-summary.json';
  link.click();
  URL.revokeObjectURL(url);
  toast(t('actions.exportSummaryOk'), 'ok');
}

function onConfigFieldChange(e) {
  // Config field changes are now handled by _onConfigChange in render.js
}
