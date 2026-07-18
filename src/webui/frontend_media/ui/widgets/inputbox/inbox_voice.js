// inbox_voice.js — 拆分自 inbox.js（4/5）：语音录制、静音检测
// 依赖 inbox_core.js 中定义的全局 InputBox。
// 原 _startVoice 约58行，超过单函数<=50行限制，拆分为
// _initRecordingState / _showRecordingIndicator / _requestMicrophone 三个 helper。

var IB_RECORDING_GIF = '<img src="data:image/gif;base64,R0lGODlhQABAAPcAAAAAAP7+/v///wAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACH/C05FVFNDQVBFMi4wAwEAAAAh+QQJAwAAACwAAAAAQABAAAAI/gABCBxIsKDBgwgTKlzIsKHDhxAjSpxIsaLFixgzatzIsaPHjyBDihxJsqRJAAIEnLSYMoDKlRNTpoQZUyZNiTJf3nyYcyfEnj4dAg3KcChRhUYNJoW5lGDTk08FRsU4E6nNhFNZXkU4NWvFrlsPeqUItirXsDx1njUrFm3BsW/dOpU7sKxahy7ZKqUrlS9Kv2vvxtU7WPBcwkX92rWKeOFirIoBt23cl/Jfy3AJ5jVcNzJmyXs/i+ZcmbRVx55NZ474ODDI1pNNax3NWLbFAAFQ0/YJm2ZvpqmDrt45/GZx36CJHgdu+Whp547zQnc8vbr169iza9/Ovbv379MDAQIA" alt="recording" style="width:19px;height:19px;display:block;pointer-events:none;">';

InputBox.prototype._toggleVoice = function() {
  if (this._isRecording) { this._stopVoice(); } else { this._startVoice(); }
};

InputBox.prototype._startVoice = function() {
  var voiceBtn = this._el('voiceBtn');
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    if (voiceBtn) voiceBtn.title = 'Voice not supported';
    return;
  }
  this._initRecordingState();
  this._showRecordingIndicator(voiceBtn);
  if (this._opts.onVoiceStart) this._opts.onVoiceStart();
  this._requestMicrophone(voiceBtn);
};

InputBox.prototype._initRecordingState = function() {
  this._isRecording = true;
  this._audioChunks = [];
  this._stopRequested = false;
  this._stream = null;
  this._audioContext = null;
  this._silenceTimer = null;
};

InputBox.prototype._showRecordingIndicator = function(voiceBtn) {
  if (!voiceBtn) return;
  // Save original button content, then replace with wave GIF
  this._originalVoiceBtnHtml = voiceBtn.innerHTML;
  voiceBtn.classList.add('ib-recording');
  voiceBtn.innerHTML = IB_RECORDING_GIF;
};

InputBox.prototype._requestMicrophone = function(voiceBtn) {
  var self = this;
  navigator.mediaDevices.getUserMedia(self._audioConstraints()).then(function(stream) {
    self._stream = stream;
    // Check if stop was requested before getUserMedia resolved
    if (self._stopRequested) {
      stream.getTracks().forEach(function(t) { t.stop(); });
      self._stream = null;
      self._stopRequested = false;
      return;
    }
    self._mediaRecorder = new MediaRecorder(stream);
    self._audioChunks = [];
    self._mediaRecorder.ondataavailable = function(e) { self._audioChunks.push(e.data); };
    self._mediaRecorder.onstop = function() {
      stream.getTracks().forEach(function(t) { t.stop(); });
      self._stream = null;
      self._stopSilenceDetection();
      var blob = new Blob(self._audioChunks, { type: 'audio/webm' });
      self._processVoiceAudio(blob);
    };
    self._mediaRecorder.start();
    self._startSilenceDetection(stream);
  }).catch(function(err) {
    self._isRecording = false;
    self._stopRequested = false;
    if (voiceBtn) {
      voiceBtn.classList.remove('ib-recording');
      voiceBtn.innerHTML = self._originalVoiceBtnHtml || '';
    }
    if (typeof toast === 'function') {
      var msg = (err && err.name === 'NotAllowedError')
        ? (typeof t === 'function' ? t('voice.micDenied') : 'Microphone permission denied')
        : (err && err.message ? err.message : String(err));
      toast(msg, 'error');
    }
  });
};

InputBox.prototype._stopVoice = function() {
  this._isRecording = false;
  this._stopRequested = true;
  var voiceBtn = this._el('voiceBtn');
  // Restore original button content
  if (voiceBtn) {
    voiceBtn.classList.remove('ib-recording');
    voiceBtn.innerHTML = this._originalVoiceBtnHtml || '';
  }
  this._stopSilenceDetection();
  // Stop MediaRecorder if it exists and is recording
  if (this._mediaRecorder && this._mediaRecorder.state !== 'inactive') {
    this._mediaRecorder.stop();
  } else {
    // MediaRecorder may not exist yet (getUserMedia still pending)
    // or already inactive. Stop stream tracks directly as fallback.
    if (this._stream) {
      this._stream.getTracks().forEach(function(t) { t.stop(); });
      this._stream = null;
    }
  }
  if (this._opts.onVoiceEnd) this._opts.onVoiceEnd();
};

/**
 * Start silence detection using AnalyserNode.
 * Monitors audio levels and auto-stops after 30s of silence.
 */
InputBox.prototype._startSilenceDetection = function(stream) {
  var self = this;
  var SILENCE_THRESHOLD = 0.01;  // Volume below this is considered silence
  var SILENCE_DURATION = 30000;  // 30 seconds of silence triggers auto-stop
  var CHECK_INTERVAL = 500;      // Check every 500ms

  try {
    var AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!AudioCtx) return;
    this._audioContext = new AudioCtx();
    var source = this._audioContext.createMediaStreamSource(stream);
    var analyser = this._audioContext.createAnalyser();
    analyser.fftSize = 256;
    source.connect(analyser);
    this._analyser = analyser;
    this._silenceStart = Date.now();
    this._silenceDetected = false;

    var dataArray = new Uint8Array(analyser.frequencyBinCount);
    this._silenceTimer = setInterval(function() {
      if (!self._isRecording) {
        self._stopSilenceDetection();
        return;
      }
      analyser.getByteFrequencyData(dataArray);
      // Calculate average volume (0-255 range, normalize to 0-1)
      var sum = 0;
      for (var i = 0; i < dataArray.length; i++) sum += dataArray[i];
      var avg = sum / dataArray.length / 255;

      if (avg < SILENCE_THRESHOLD) {
        if (!self._silenceDetected) {
          self._silenceDetected = true;
          self._silenceStart = Date.now();
        } else if (Date.now() - self._silenceStart >= SILENCE_DURATION) {
          // 30s of silence detected, auto-stop
          console.log('InputBox: Auto-stopping recording after 30s of silence');
          self._stopVoice();
        }
      } else {
        // Sound detected, reset silence timer
        self._silenceDetected = false;
        self._silenceStart = null;
      }
    }, CHECK_INTERVAL);
  } catch (e) {
    // AudioContext not available, skip silence detection
    console.log('InputBox: Silence detection unavailable:', e.message);
  }
};

/**
 * Stop silence detection and clean up audio resources.
 */
InputBox.prototype._stopSilenceDetection = function() {
  if (this._silenceTimer) {
    clearInterval(this._silenceTimer);
    this._silenceTimer = null;
  }
  if (this._audioContext) {
    try { this._audioContext.close(); } catch(e) {}
    this._audioContext = null;
  }
  this._analyser = null;
  this._silenceStart = null;
  this._silenceDetected = false;
};

InputBox.prototype._audioConstraints = function() {
  var deviceId = (this._opts.voice && this._opts.voice.recordingDeviceId) || '';
  if (!deviceId) return { audio: true };
  return { audio: { deviceId: { exact: deviceId } } };
};

InputBox.prototype.updateVoice = function(voice) {
  this._opts.voice = Object.assign({}, this._opts.voice, voice || {});
};
