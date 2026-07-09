# stats 静态资源

WebUI 统计功能的前端资源。

## 目录结构

```
stats/
├── request-inspector.js  # 请求检查器 JavaScript 实现
└── stats.js              # 统计功能 JavaScript 实现
```

## 核心功能

### request-inspector.js

请求检查器的前端实现，包括：
- HTTP 请求监控（WebSocket `/v1/webui/ws/requests`）
- 请求详情展示（优先使用 `request_end.response` 作为最终响应文本）
- 流式过程中通过 `request_chunk` 增量更新详情弹窗

### stats.js

统计功能的前端实现，包括：
- 统计数据收集
- 统计图表展示
- 统计信息汇总

## 依赖关系

- 依赖 `src/webui/static/core/` 中的核心模块
- 依赖 `src/webui/static/ui/` 中的 UI 组件

## 注意事项

- 此文件为 WebUI 前端资源
- 修改时需要考虑浏览器兼容性
- 遵循项目的前端编码规范