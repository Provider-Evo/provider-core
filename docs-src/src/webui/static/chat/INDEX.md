# chat 静态资源

WebUI 聊天功能的前端资源。实现位于 `src/webui/static/ui/chat/`。

## 目录结构

```
ui/chat/
├── chat.js              # 聊天主逻辑
├── chat-attachments.js  # 附件与预览
└── chat-media-persist.js
```

## 语音能力

| 能力 | 配置来源 | API |
|------|----------|-----|
| STT 录音输入 | `webui_config.toml` → `sttModel`、`recordingDeviceId` | `POST /v1/audio/transcriptions` |
| TTS 播放助手回复 | `webui_config.toml` → `ttsModel`、`ttsPrompt` | `POST /v1/audio/speech` |

助手消息操作栏含 **播放** 按钮（`speak`）：按 `ttsPrompt` 与正文合成语音并播放；再次点击可停止。

语音配置在配置面板保存后，经 `_applyWebuiRuntime` → `saveVoiceSettings` 同步到 `InputBox`。

## 依赖关系

- `InputBox`（`ui/widgets/input-box.js`）
- `loadVoiceSettings` / `normalizeVoiceSettings`（`base/core/state.js`）
