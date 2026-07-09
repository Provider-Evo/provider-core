# dashboard 静态资源

WebUI 仪表盘功能的前端资源。

## 目录结构

```
dashboard/
└── render.js        # 仪表盘渲染 JavaScript 实现
```

## 核心功能

### render.js

仪表盘渲染的前端实现，包括：
- 仪表盘界面渲染
- 数据可视化展示
- 状态信息显示

## 依赖关系

- 依赖 `src/webui/static/core/` 中的核心模块
- 依赖 `src/webui/static/ui/` 中的 UI 组件

## 注意事项

- 此文件为 WebUI 前端资源
- 修改时需要考虑浏览器兼容性
- 遵循项目的前端编码规范