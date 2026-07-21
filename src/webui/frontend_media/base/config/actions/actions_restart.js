// ========================= Restart Overlay =========================

var _restartState = 'idle'; // idle | requesting | restarting | checking | success | failed
var _restartProgress = 0;
var _restartElapsed = 0;
var _restartTimer = null;
var _restartProgressTimer = null;
var _restartCheckTimer = null;
var _restartCheckAttempts = 0;
var _restartPreStart = null; // start_time before restart request

var _RESTART_CONFIG = {
  INITIAL_DELAY: 3000,
  CHECK_INTERVAL: 2000,
  CHECK_TIMEOUT: 3000,
  MAX_ATTEMPTS: 60,
  PROGRESS_INTERVAL: 200,
  SUCCESS_REDIRECT_DELAY: 1500,
};

var _RESTART_KEY_MAP = {
  requesting: { title: 'restart.preparing', desc: 'restart.preparingDesc' },
  restarting: { title: 'restart.restarting', desc: 'restart.restartingDesc' },
  checking: { title: 'restart.checking', desc: 'restart.checkingDesc' },
  success: { title: 'restart.success', desc: 'restart.successDesc' },
  failed: { title: 'restart.failed', desc: 'restart.failedDesc' },
};

function _restartText(status, field) {
  var keys = _RESTART_KEY_MAP[status] || _RESTART_KEY_MAP.requesting;
  var key = keys[field];
  if (status === 'checking' && field === 'desc') {
    return t(key, {
      current: _restartCheckAttempts,
      max: _RESTART_CONFIG.MAX_ATTEMPTS,
    });
  }
  return t(key);
}

function _restartSetIcons(status) {
  var spinner = document.getElementById('restartSpinner');
  var check = document.getElementById('restartCheck');
  var fail = document.getElementById('restartFail');
  var pulse = document.getElementById('restartPulse');
  var showSpinner = (status === 'requesting' || status === 'restarting' || status === 'checking');
  var showCheck = (status === 'success');
  var showFail = (status === 'failed');
  if (spinner) spinner.style.display = showSpinner ? '' : 'none';
  if (check) check.style.display = showCheck ? '' : 'none';
  if (fail) fail.style.display = showFail ? '' : 'none';
  if (pulse) pulse.classList.toggle('hidden', !showSpinner);
}

function _restartSetText(status) {
  var title = document.getElementById('restartTitle');
  var desc = document.getElementById('restartDesc');
  if (title) {
    title.textContent = _restartText(status, 'title');
    title.setAttribute('data-i18n', _RESTART_KEY_MAP[status] ? _RESTART_KEY_MAP[status].title : 'restart.preparing');
  }
  if (desc) {
    desc.textContent = _restartText(status, 'desc');
    if (_RESTART_KEY_MAP[status]) desc.setAttribute('data-i18n', _RESTART_KEY_MAP[status].desc);
  }
}

function _restartSetState(status) {
  _restartState = status;
  var overlay = document.getElementById('restartOverlay');
  var actions = document.getElementById('restartActions');
  if (!overlay) return;

  overlay.classList.remove('is-success', 'is-failed');
  if (status === 'success') overlay.classList.add('is-success');
  if (status === 'failed') overlay.classList.add('is-failed');

  _restartSetIcons(status);
  _restartSetText(status);

  if (actions) {
    actions.style.display = (status === 'success' || status === 'failed') ? '' : 'none';
  }
}

function _restartUpdateProgress(percent) {
  _restartProgress = Math.min(percent, 100);
  var bar = document.getElementById('restartProgressBar');
  var pct = document.getElementById('restartPercent');
  if (bar) bar.style.width = _restartProgress + '%';
  if (pct) pct.textContent = Math.round(_restartProgress) + '%';
}

function _restartUpdateElapsed() {
  _restartElapsed++;
  var el = document.getElementById('restartElapsed');
  if (el) el.textContent = t('restart.elapsed', { seconds: _restartElapsed });
}

function _restartStartProgressTimer() {
  _restartProgress = 0;
  _restartElapsed = 0;
  _restartUpdateProgress(0);
  _restartUpdateElapsed();
  _restartProgressTimer = setInterval(function() {
    if (_restartProgress < 90) {
      _restartUpdateProgress(_restartProgress + 1);
    }
  }, _RESTART_CONFIG.PROGRESS_INTERVAL);
  _restartTimer = setInterval(function() {
    _restartUpdateElapsed();
  }, 1000);
}

function _restartStopTimers() {
  if (_restartProgressTimer) { clearInterval(_restartProgressTimer); _restartProgressTimer = null; }
  if (_restartTimer) { clearInterval(_restartTimer); _restartTimer = null; }
  if (_restartCheckTimer) { clearTimeout(_restartCheckTimer); _restartCheckTimer = null; }
}

function _restartDoCheck() {
  _restartCheckAttempts++;
  var controller = new AbortController();
  var timeout = setTimeout(function() { controller.abort(); }, _RESTART_CONFIG.CHECK_TIMEOUT);

  fetch('/v1/webui/system/status', {
    signal: controller.signal,
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
  })
    .then(function(resp) {
      clearTimeout(timeout);
      if (resp.ok) {
        return resp.json();
      }
      throw new Error('not ok');
    })
    .then(function(data) {
      if (data && data.running) {
        // Verify the process actually restarted by comparing start_time
        if (_restartPreStart !== null && data.start_time === _restartPreStart) {
          _restartScheduleNext();
          return;
        }
        _restartOnSuccess();
        return;
      }
      _restartScheduleNext();
    })
    .catch(function() {
      clearTimeout(timeout);
      _restartScheduleNext();
    });
}

function _restartScheduleNext() {
  if (_restartCheckAttempts >= _RESTART_CONFIG.MAX_ATTEMPTS) {
    _restartOnFailed();
    return;
  }
  _restartCheckTimer = setTimeout(_restartDoCheck, _RESTART_CONFIG.CHECK_INTERVAL);
}

function _restartStartHealthCheck() {
  _restartCheckAttempts = 0;
  _restartSetState('checking');
  _restartDoCheck();
}

function _restartOnSuccess() {
  _restartStopTimers();
  _restartUpdateProgress(100);
  _restartSetState('success');
  setTimeout(function() { location.reload(); }, _RESTART_CONFIG.SUCCESS_REDIRECT_DELAY);
}

function _restartOnFailed() {
  _restartStopTimers();
  _restartSetState('failed');
}

function _restartShowOverlay() {
  var overlay = document.getElementById('restartOverlay');
  if (overlay) {
    overlay.style.display = 'flex';
    requestAnimationFrame(function() {
      requestAnimationFrame(function() {
        overlay.classList.add('is-visible');
      });
    });
  }
}

function _restartCaptureStartTime(nextStep) {
  _restartPreStart = null;
  var statusCtrl = new AbortController();
  var statusTimeout = setTimeout(function() { statusCtrl.abort(); }, 3000);
  return fetch('/v1/webui/system/status', { credentials: 'include', signal: statusCtrl.signal })
    .then(function(resp) { clearTimeout(statusTimeout); return resp.ok ? resp.json() : null; })
    .then(function(data) {
      if (data && typeof data.start_time === 'string') _restartPreStart = data.start_time;
    })
    .catch(function() { clearTimeout(statusTimeout); })
    .then(nextStep);
}

function _restartSendReloadRequest() {
  var controller = new AbortController();
  var timeout = setTimeout(function() { controller.abort(); }, 5000);

  return fetch('/v1/admin/reload', { method: 'POST', signal: controller.signal })
    .then(function(resp) {
      clearTimeout(timeout);
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      return resp.json();
    })
    .then(function(result) {
      if (result.status === 'ok') {
        _restartSetState('restarting');
        setTimeout(_restartStartHealthCheck, _RESTART_CONFIG.INITIAL_DELAY);
      } else {
        _restartStopTimers();
        _restartSetState('failed');
      }
    })
    .catch(function() {
      // Timeout or network error = server is dying, which is expected
      clearTimeout(timeout);
      _restartSetState('restarting');
      setTimeout(_restartStartHealthCheck, _RESTART_CONFIG.INITIAL_DELAY);
    });
}

function triggerRestart(options) {
  options = options || {};
  var skipApiCall = Boolean(options.skipApiCall);

  if (_restartState !== 'idle' && _restartState !== 'failed') {
    return;
  }

  _restartShowOverlay();
  _restartSetState(skipApiCall ? 'restarting' : 'requesting');
  _restartStartProgressTimer();

  if (skipApiCall) {
    // Still capture pre-restart start_time for health check comparison
    _restartCaptureStartTime(function() {
      setTimeout(_restartStartHealthCheck, _RESTART_CONFIG.INITIAL_DELAY);
    });
    return;
  }

  // Fetch current start_time before restart request, then send restart
  _restartCaptureStartTime(_restartSendReloadRequest);
}

function _restartTrigger() {
  triggerRestart();
}

function reloadServer() {
  showConfirmDialog(t('restart.confirmMessage'), {
    title: t('restart.confirmTitle'),
    confirmText: t('restart.confirmButton'),
    cancelText: t('common.cancel'),
  }).then(function(confirmed) {
    if (confirmed) {
      _restartTrigger();
    }
  });
}

function retryHealthCheck() {
  _restartStopTimers();
  _restartCheckAttempts = 0;
  _restartElapsed = 0;
  _restartUpdateElapsed();
  _restartUpdateProgress(0);
  _restartStartProgressTimer();
  _restartSetState('checking');
  _restartStartHealthCheck();
}
