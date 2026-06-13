# tests 编写规范

## 一、定位

`tests/` 是与源码结构尽量镜像的测试树，负责最小契约验证、核心逻辑回归和运行行为校验。

## 二、结构要求

### 顶层要求
- `tests/INDEX.md`
- `tests/conftest.py`
- `tests/helpers/`
- `tests/src/`

### 镜像要求
- `tests/src/core/`：核心复用逻辑测试
- `tests/src/platforms/`：平台 MVP 与平台专项测试
- 重要新增源码目录若有可测试逻辑，应在 tests 中镜像补齐

## 三、平台 MVP 规则

每个平台至少有一个 MVP test，至少验证：
1. 模块可导入
2. `Adapter` 可解析
3. `name`、`supported_models`、`default_capabilities` 可访问
4. 必要时使用 `pytest.skip()`，但必须给出原因

## 四、专项测试建议

优先补强以下类型：
- 持久化模块读写测试
- WebUI 页面生成测试
- 启动流程与端口释放测试
- 路由与摘要接口测试
- 脚本工具测试

## 五、跳过规则

允许跳过的情况：
- 外部 API 不可用
- 有效凭证不可得
- 远端服务阻断
- 环境缺少特定依赖

但必须：
- 用 `pytest.skip()` 明确说明原因
- 不得伪造通过
- 长期性问题写入 `RECORD.md`

## 六、索引要求

`tests/INDEX.md` 至少应说明：
- 测试运行命令
- 目录布局
- 跳过规则
- 主要测试分类

## 七、当前项目要求

- 平台目录不可缺少 MVP test。
- 新增 `src/webui/`、`src/core/runtime_view.py`、持久化模块等都应具备对应测试。
- 每次重大结构重构后应重新运行全量 `pytest tests -q`。
