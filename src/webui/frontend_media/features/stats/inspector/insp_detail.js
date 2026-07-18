/**
 * RequestInspector detail modal rendering.
 *
 * Attaches _select / _showDetailModal / renderDetail onto the shared
 * instance created in inspector_core.js. See that file's header comment
 * for the overall split rationale.
 */
function _idBuildModalMetaHtml(req) {
  var html = '<div class="req-modal-meta">';
  html += '<span class="req-status ' + (req.status >= 400 ? 'req-error' : 'req-ok') + '">';
  html += req.status === 'pending' ? 'In Progress' : 'Status ' + req.status;
  html += '</span>';
  html += '<span>Model: <strong>' + escapeHtml(req.model || 'unknown') + '</strong></span>';
  html += '<span>Platform: <strong>' + escapeHtml(req.platform || 'unknown') + '</strong></span>';
  html += '<span>Messages: ' + req.messages_count + '</span>';
  html += '<span>Tools: ' + (req.has_tools ? 'yes' : 'no') + '</span>';
  html += '<span>Stream: ' + (req.stream ? 'yes' : 'no') + '</span>';
  if (req.latency_ms !== null) html += '<span>Latency: <strong>' + req.latency_ms + 'ms</strong></span>';
  var time = new Date(req.ts * 1000);
  html += '<span>Time: ' + time.toLocaleString() + '</span>';
  html += '</div>';
  return html;
}

function _idBuildResponseSectionHtml(instance, req) {
  var content = instance._requestContent(req);
  if (content) {
    return '<div class="req-modal-section">'
      + '<div class="req-modal-section-header">'
      + '<div class="req-modal-label">Response (' + content.length + ' chars)</div>'
      + '<button type="button" class="req-copy-btn" data-copy-target="response" title="' + t('common.copy') + '">' + t('common.copy') + '</button>'
      + '</div>'
      + '<pre class="req-modal-content" id="req-response-content">' + escapeHtml(content) + '</pre>'
      + '</div>';
  } else if (req.status === 'pending') {
    return '<div class="req-modal-section"><div class="text-muted" style="padding:12px;text-align:center;">Waiting for response...</div></div>';
  }
  return '<div class="req-modal-section"><div class="text-muted" style="padding:12px;text-align:center;">No response content captured</div></div>';
}

function _idBuildMessagesSectionHtml(req) {
  if (!req.messages || req.messages.length === 0) return '';
  var messagesJson = JSON.stringify(req.messages, null, 2);
  return '<div class="req-modal-section">'
    + '<div class="req-modal-section-header">'
    + '<div class="req-modal-label">Request Messages (' + req.messages.length + ')</div>'
    + '<button type="button" class="req-copy-btn" data-copy-target="messages" title="' + t('common.copy') + '">' + t('common.copy') + '</button>'
    + '</div>'
    + '<pre class="req-modal-content" id="req-messages-content">' + escapeHtml(messagesJson) + '</pre>'
    + '</div>';
}

function _idCopyModalButton(instance, btn, elId) {
  var el = document.getElementById(elId);
  if (!el) return;
  var text = el.textContent || '';
  instance.copyToClipboard(text).then(function () {
    btn.textContent = t('toast.copied');
    setTimeout(function () { btn.textContent = t('common.copy'); }, 1500);
  }, function () {
    btn.textContent = t('common.failed');
    setTimeout(function () { btn.textContent = t('common.copy'); }, 1500);
  });
}

function _idBindModalCopyButtons(instance, overlay) {
  overlay.querySelectorAll('.req-copy-btn').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var target = btn.dataset.copyTarget;
      var elId = target === 'response' ? 'req-response-content' : 'req-messages-content';
      _idCopyModalButton(instance, btn, elId);
    });
  });
}

function _idBuildModalHtml(instance, req) {
  var html = '<div class="req-modal">';
  html += '<div class="req-modal-header">';
  html += '<div class="req-modal-title">Request ' + escapeHtml(req.id) + '</div>';
  html += '<button type="button" class="req-modal-close" aria-label="Close">&times;</button>';
  html += '</div>';
  html += _idBuildModalMetaHtml(req);
  html += _idBuildResponseSectionHtml(instance, req);
  html += _idBuildMessagesSectionHtml(req);
  html += '</div>';
  return html;
}

function _idBindModalCloseHandlers(overlay) {
  function closeModal() {
    overlay.classList.remove('is-visible');
    document.removeEventListener('keydown', escHandler);
    setTimeout(function () { overlay.remove(); }, 180);
  }

  function escHandler(e) {
    if (e.key === 'Escape') closeModal();
  }

  overlay.querySelector('.req-modal-close').addEventListener('click', closeModal);
  overlay.addEventListener('click', function (e) {
    if (e.target === overlay) closeModal();
  });
  document.addEventListener('keydown', escHandler);
}

function _idShowDetailModal(instance, id) {
  var req = instance._requests[id];
  if (!req) return;

  // Remove any existing modal
  var existing = document.getElementById('requestDetailModal');
  if (existing) existing.remove();

  var overlay = document.createElement('div');
  overlay.id = 'requestDetailModal';
  overlay.className = 'confirm-overlay';
  overlay.innerHTML = _idBuildModalHtml(instance, req);
  document.body.appendChild(overlay);

  requestAnimationFrame(function () { overlay.classList.add('is-visible'); });

  _idBindModalCloseHandlers(overlay);
  _idBindModalCopyButtons(instance, overlay);
}

function _idRebindResponseCopyButton(instance, firstSection) {
  var newBtn = firstSection.querySelector('.req-copy-btn');
  if (newBtn) {
    newBtn.addEventListener('click', function () {
      _idCopyModalButton(instance, newBtn, 'req-response-content');
    });
  }
}

function _idUpdateResponseSection(instance, req, modal) {
  var sections = modal.querySelectorAll('.req-modal-section');
  var content = instance._requestContent(req);
  if (sections.length === 0) return;
  var firstSection = sections[0];
  if (content) {
    firstSection.innerHTML = '<div class="req-modal-section-header">'
      + '<div class="req-modal-label">Response (' + content.length + ' chars)</div>'
      + '<button type="button" class="req-copy-btn" data-copy-target="response" title="' + t('common.copy') + '">' + t('common.copy') + '</button>'
      + '</div>'
      + '<pre class="req-modal-content" id="req-response-content">' + escapeHtml(content) + '</pre>';
    _idRebindResponseCopyButton(instance, firstSection);
  } else if (req.status === 'pending') {
    firstSection.innerHTML = '<div class="text-muted" style="padding:12px;text-align:center;">Waiting for response...</div>';
  } else {
    firstSection.innerHTML = '<div class="text-muted" style="padding:12px;text-align:center;">No response content captured</div>';
  }
}

function _idUpdateStatusBadge(req, modal) {
  var meta = modal.querySelector('.req-modal-meta');
  if (!meta) return;
  var statusSpan = meta.querySelector('.req-status');
  if (statusSpan) {
    statusSpan.className = 'req-status ' + (req.status >= 400 ? 'req-error' : 'req-ok');
    statusSpan.textContent = req.status === 'pending' ? 'In Progress' : 'Status ' + req.status;
  }
}

function _idRenderDetail(instance) {
  // Live-update the modal if it is currently open for the selected request
  var modal = document.getElementById('requestDetailModal');
  if (!modal || !instance._selectedId) return;
  var req = instance._requests[instance._selectedId];
  if (!req) return;

  _idUpdateResponseSection(instance, req, modal);
  _idUpdateStatusBadge(req, modal);
}

function _attachDetailMethods(instance) {

  instance._select = function (id) {
    instance._selectedId = id;
    instance.renderList();
    instance._showDetailModal(id);
  };

  instance._showDetailModal = function (id) { _idShowDetailModal(instance, id); };

  instance.renderDetail = function () { _idRenderDetail(instance); };
}
