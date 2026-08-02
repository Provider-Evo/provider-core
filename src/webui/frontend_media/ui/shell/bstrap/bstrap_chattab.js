// Lazy chat tab init — shared by bstrap_boot.js and bstrap_helpers.js

function _bindChatBatchToggleBtn(chatBatchToggleBtn) {
  if (!chatBatchToggleBtn) return;
  chatBatchToggleBtn.addEventListener('click', function() {
    var section = document.getElementById('batchTestSection');
    if (section) {
      section.classList.toggle('hidden');
      chatBatchToggleBtn.textContent = section.classList.contains('hidden') ? t('chat.batchTest') : t('chat.collapseBatchTest');
    }
  });
}

function _mountChatInputBox() {
  var initInputBox = function() {
    if (typeof InputBox === 'undefined' || !document.getElementById('chatInputBox')) return;
    if (window._chatInputBox) return;
    var voiceSettings = typeof loadVoiceSettings === 'function' ? loadVoiceSettings() : {};
    window._chatInputBox = InputBox.create('#chatInputBox', {
      placeholder: t('chat.inputPlaceholder'),
      buttons: { file: true, voice: true, send: true },
      voice: voiceSettings,
      onSend: function(text, files) { sendChatMessage(text, files); },
      onVoiceStart: function() { toast(t('chat.recording'), 'info'); },
      onVoiceEnd: function() {},
    });
  };
  if (typeof loadWebUISettings === 'function') {
    loadWebUISettings().then(initInputBox).catch(function() { initInputBox(); });
  } else {
    initInputBox();
  }
}

function _bindChatClearAndTests(chatClearBtn, chatRunTestsBtn) {
  if (chatClearBtn) {
    chatClearBtn.addEventListener('click', function() {
      clearChatMessages();
      toast(t('chat.cleared'), 'ok');
    });
  }
  if (chatRunTestsBtn && typeof runChatTests === 'function') {
    chatRunTestsBtn.addEventListener('click', runChatTests);
  }
}

function _loadChatTabLazy() {
  (async function() {
    if (typeof loadChatState === 'function') await loadChatState();
    if (typeof loadModelsList === 'function') await loadModelsList();
  })();
  if (typeof ChatAttachments !== 'undefined' && ChatAttachments.install) ChatAttachments.install();
  if (typeof _loadTools === 'function') _loadTools();
}

function _initChatTab() {
  _bindChatBatchToggleBtn(document.getElementById('chatBatchToggleBtn'));
  _mountChatInputBox();
  _bindChatClearAndTests(
    document.getElementById('chatClearBtn'),
    document.getElementById('chatRunTestsBtn')
  );
  _loadChatTabLazy();
}
