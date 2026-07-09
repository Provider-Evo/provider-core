# files 静态资源

WebUI 文件管理功能的前端资源。

## 目录结构

```
files/
├── files.css        # 文件管理样式
└── files.js         # 文件管理 JavaScript 实现
```

## 核心功能

### files.js

文件管理功能的前端实现，包括：
- 文件列表展示
- 文件上传和下载
- 文件删除和管理
- 文件预览功能

### files.css

文件管理界面的样式定义，包括：
- 文件列表布局
- 文件图标样式
- 上传进度显示

## 依赖关系

- 依赖 `src/webui/static/core/` 中的核心模块
- 依赖 `src/webui/static/ui/` 中的 UI 组件

## 注意事项

- 此文件为 WebUI 前端资源
- 修改时需要考虑浏览器兼容性
- 遵循项目的前端编码规范