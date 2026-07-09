# ui 静态资源

WebUI 用户界面组件的前端资源。

## 目录结构

```
ui/
├── bootstrap.js     # Bootstrap 框架 JavaScript
├── dropdown.js      # 下拉菜单组件
├── input-box.css    # 输入框样式
├── input-box.js     # 输入框组件
├── sortable-list/   # 可排序列表组件
└── styles.css       # 全局样式
```

## 核心功能

### bootstrap.js

Bootstrap 框架的 JavaScript 实现。页面加载时调用 `refreshAll()` 拉取 `/v1/webui/summary` 填充模型清单与下拉框；聊天/语音模型下拉通过 `populateModelDropdowns()` 更新，**不**调用需 API Key 的 `/v1/models`。

语音模型筛选规则（`actions.js`）：
- **STT**：`audio_transcription` / `audio_in`，或 `chat+vision` 多模态，或模型名含 whisper/transcribe
- **TTS**：`edgetts` / `gtts` / `openaifm` 平台，或仅 `audio_gen` 无 `chat` 的专用语音模型

### dropdown.js

下拉菜单组件的实现，包括：
- 菜单显示和隐藏
- 选项选择处理
- 键盘导航支持

### input-box.js

聊天输入框组件，包括：
- 文本输入、文件附件、超长文本转文件
- **语音录音**：`getUserMedia`（可选 `recordingDeviceId`）→ `MediaRecorder` → `POST /v1/audio/transcriptions`（`sttModel`）
- `updateVoice()`：配置变更时热更新语音参数

语音参数来自 `webui_config.toml`（经 `loadVoiceSettings()` 缓存到 localStorage）。

### sortable-list/

可排序列表组件，支持拖拽排序功能。

## 依赖关系

- 被其他静态资源模块依赖
- 提供 WebUI 的 UI 组件

## 注意事项

- 此目录为 WebUI UI 组件库
- 修改时需要考虑组件的可复用性
- 遵循项目的前端编码规范