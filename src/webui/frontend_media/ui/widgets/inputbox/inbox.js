/**
 * InputBox — Portable chat input component.
 * Usage: InputBox.create(container, options)
 *
 * NOTE: 此文件已拆分为 5 个文件（单文件<=400行，单函数<=50行）：
 *   inputbox_core.js   (1/5) 内部状态 + 构造函数 + 基础渲染
 *   inputbox_events.js (2/5) 事件绑定
 *   inputbox_send.js   (3/5) 高度同步、字数限制、发送、文件附件
 *   inputbox_voice.js  (4/5) 语音录制、静音检测
 *   inputbox_api.js    (5/5) 公开 API、工厂方法、window.InputBox 挂载
 * 五个文件不用 IIFE 包裹，共享同一个全局 InputBox 函数引用，必须按顺序加载。
 * 加载顺序见 base/core/lazy/lazy_assets.js 的 chat 资源列表。
 * 本文件保留为空占位，不再包含任何实现，避免与拆分文件重复声明。
 */
