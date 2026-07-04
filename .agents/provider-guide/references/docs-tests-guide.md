# docs-src 与 tests 详细规范

## 一、docs-src 的定位

`docs-src` 不是随便写说明文档的地方，而是项目知识的镜像文档树。

它必须尽量按真实项目结构建立同名目录，目的是：
- 让维护者可以按路径定位文档
- 让规范、索引、历史知识和镜像 AGENTS 共存
- 让 docs-src 成为源码、tests、skill、模板与保留脚本的文档镜像层

## 二、docs-src 目录要求

### 必须镜像的根级目录
- `src/`
- `tests/`
- `.agents/provider-guide/`
- `.scripts/`
- `template/`

### 每个重要目录至少包含
- 一个 `INDEX.md`，说明该目录职责
- 必要时增加专题 Markdown 文件
- 若原项目存在 AGENTS/agents 文档且要求镜像保留，则应在 docs-src 中保留镜像副本

## 三、AGENTS 镜像规则

1. docs-src 中的 `AGENTS.md` 不应被误写成“仅 docs-src 专属规则”。
2. 若原项目有根级或子目录级 AGENTS/agents 文档，应以镜像方式保留在 docs-src 中。
3. 这些镜像文档应在文件中明确写出“镜像说明”，避免误读成新语义。
4. 当前应保留的镜像文档包括：
   - `docs-src/AGENTS.md`
   - `docs-src/src/AGENTS.md`
   - `docs-src/src/platforms/AGENTS.md`
   - `docs-src/.scripts/AGENTS.md`

## 四、docs-src 内容规则

- 全部使用无 emoji Markdown。
- 不能只列文件名，必须写职责或边界说明。
- 对复杂目录，应说明入口文件、关键流程、常见误区。
- 如果某目录只是镜像占位，也应明确写出其镜像来源。

## 五、tests 的定位

`tests/` 也应按源码结构尽量镜像，承担最小契约验证与核心逻辑回归验证职责。

## 六、tests 目录要求

### 顶层要求
- `tests/INDEX.md`
- `tests/conftest.py`
- `tests/helpers/` 可放共享辅助逻辑

### 镜像要求
- 至少镜像 `src/core/`
- 至少镜像 `src/platforms/`
- 每个平台目录至少有一个 MVP test

## 七、平台 MVP test 规则

每个平台 MVP test 至少验证：
1. 平台模块可以导入
2. `Adapter` 可以找到
3. `name`、`supported_models`、`default_capabilities` 可访问
4. 无法安全实例化时，用 `pytest.skip()` 明确说明原因

## 八、跳过规则

允许跳过的场景：
- 真实第三方 API 不可用
- 凭证缺失或失效
- 环境缺少特定二进制依赖
- 远程服务策略阻塞

但跳过必须：
- 写清楚原因
- 不得伪装成通过
- 若属于项目级长期限制，**追加**到 `RECORD.md` 末尾（已 gitignore，不提交），禁止覆盖文件

## 九、当前项目特别要求

- docs-src 中同时要收录 `docs-src-guide.md` 和 `tests-guide.md`。
- tests 中的平台最小测试不能缺失。
- docs-src 索引必须能导航到平台规范、平台合规矩阵、WebUI 说明、skill 规则索引。
