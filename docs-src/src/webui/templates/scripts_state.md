# src/webui/templates/scripts_state.py

该模块放前端状态、设置和基础工具脚本。

v2.2.153 起 switchTab 集成懒加载，新增 _initTab 分发函数，按标签页触发对应资源的延迟加载。

## UI 组件

### showInputDialog

通用输入对话框组件，用于替代原生 `prompt()` 对话框。返回 Promise，用户输入内容后 resolve 输入值，取消时 resolve null。

**参数：**
- `message` - 对话框提示信息
- `options.title` - 对话框标题，默认 "输入"
- `options.defaultValue` - 输入框默认值
- `options.confirmText` - 确认按钮文本，默认 "确定"
- `options.cancelText` - 取消按钮文本，默认 "取消"
- `options.placeholder` - 输入框占位符文本

**使用示例：**
```javascript
showInputDialog('请输入名称:', {
  title: '重命名',
  defaultValue: '当前名称',
  placeholder: '请输入新名称'
}).then(function(value) {
  if (value) {
    // 处理输入值
  }
});
```
