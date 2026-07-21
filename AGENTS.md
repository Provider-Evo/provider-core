# 代码规范

## 运行环境

- **Python**：3.8–3.14 均需可运行；使用 `from __future__ import annotations` 与 `typing_extensions` 处理版本差异；避免仅在高版本可用的语法而不加守卫。
- **操作系统**：Windows / Linux / macOS 均需支持；平台相关逻辑须显式分支，禁止假设单一环境。
- **不使用 f-string**，使用 `str.format()` 或 `%` 保持 Python 3.8 兼容。


## 禁止的注释套话（一律不得写入源码）

以下均为 agent 历史污染，**禁止新增**；清理用 `python scripts/provider-core/strip_comment_boilerplate.py`，门禁用同脚本的 `--verify`。

- 「标准模块」「项目标准模块」「作为 Provider-Evo 项目标准模块」
- 文件末尾「本模块对外契约」「相关模块」分隔注释块
- 「中文说明：」「公开方法/公开类 xxx。」等机械 docstring
- 「修改指引参见…」「保持单文件 200-400 行」等自描述套话
- 在 `.py` 里复述 `docs-src/`、`PROJECT_DECISIONS.md`、覆盖率门禁等文档内容

详细设计只写 `docs-src/`；源码注释只解释当前实现里不易一眼看出的点。


## 注释与文档分工

注释服务于**读代码的人**，不是凑合规字数。好注释回答 **「为何这样写」** 和 **「否则会怎样」**，不重复函数名已表达的信息。

### 好注释（推荐模式）

以下模式摘自成熟网关项目的实践（如本地 `MaiBot-dev` 只读参考），写入时保持简短，通常 1–3 行：

| 场景 | 写什么 |
|------|--------|
| **锁 / 并发** | 为何用 `threading.Lock` 而非 `asyncio.Lock`；是否存在多 event loop、跨线程调用；选错锁的后果 |
| **取消 / 超时** | 父协程 `CancelledError` 时须显式取消子任务，否则后台请求泄漏连接或使超时失效 |
| **魔法常量** | 阈值、窗口、burst 判定的业务后果；误触发或统计口径边界（如「不区分发言者」） |
| **兼容 / 降级** | 旧数据、可选 API、插件旧字段——退化行为是什么、为何不能更精确 |
| **跨层契约** | HTTP 状态码、错误码映射的前后端约定（如避免 401 被前端当成 WebUI 登录失效） |
| **信任边界** | 哪些字段可信、哪些用户可控；为何不用昵称/自由文本做安全判断 |
| **操作顺序** | 回滚、切换、清理时的步骤顺序，避免新旧状态混合 |

**示例（风格参考，非模板）：**

```python
# SQLite WAL 仅单写；网关存在多 event loop / 跨线程直调，须用进程级 threading.Lock，
# asyncio.Lock 无法跨 loop 互斥。

# 调用方因 wait_for 取消时，必须 cancel 子任务并 await 清理，否则 httpx 请求仍在后台占用连接。

# 使用 502 而非上游 401/403：前端 fetchWithAuth 会把 401 当作 WebUI 会话失效。
```

公开 API 的 docstring：**一句话职责即可**；参数/返回值能从类型注解读出时不逐条复述。复杂逻辑用行内 `#` 注释放在分支或常量旁，不要堆在文件头。

### 坏注释

- 重复函数名/参数名；上文「禁止套话」清单中的机械 docstring
- 为通过 `achecker` 堆砌的空洞 docstring 或文件末尾契约块
- 在 `.py` 里复述 `docs-src/`、门禁规则、架构长文

### 重构与补充

1. 原注释若仍描述当前行为应**保留或改准确**；删代码才删注释。
2. 无注释处仅在逻辑复杂、易误读、或属于上表场景时补充；**不**追求「每个公开符号必有 docstring」。
3. 架构、流程、API 说明写在 `docs-src/`；源码只留读代码时的盲区。

门禁：`python scripts/provider-core/strip_comment_boilerplate.py --verify`


## 质量门禁（achecker）

`achecker.py` 与 `check_python_standards.py` 是**结构健康度**检查（目录宽度、文件/函数体量、嵌套深度等），不是评论文比赛。

1. **目的**：发现难维护的巨型文件/函数，推动合理拆分——拆分应改善结构，而非机械拆函数骗过行数。
2. **禁止**：为过关追加无信息注释、复制粘贴 docstring 模板、把说明性长文塞进 `.py` 而非 `docs-src`。
3. **正确做法**：先判断违规是否反映真实设计问题；该拆则拆，该豁免/重构则带着理由处理；注释只补阅读盲区。
4. **任务完成**：相关路径改动后运行 `python achecker.py`；既有违规若与本次无关可记录，**不得**用垃圾注释/空函数伪造合规。


## import 规范

在从外部库进行导入时候，请遵循以下顺序：

1. 对于标准库和第三方库的导入，请按照如下顺序：
   - 需要使用 `from ... import ...` 语法的导入放在前面。
   - 直接使用 `import ...` 语法的导入放在后面。
   - 对于使用 `from ... import ...` 导入的多个项，请**在保证不会引起 import 错误的前提下**，按照**字母顺序**排列。
   - 对于使用 `import ...` 导入的多个项，请**在保证不会引起 import 错误的前提下**，按照**字母顺序**排列。

2. 对于本地模块的导入，请按照如下顺序：
   - 对于同一个文件夹下的模块导入，使用相对导入，排列顺序按照**不发生 import 错误的前提下**，随便排列。
   - 对于不同文件夹下的模块导入，使用绝对导入。这些导入应该以 `from src` 开头，并且按照**不发生 import 错误的前提下**，尽量使得第二层的文件夹名称相同的导入放在一起；第二层文件夹名称排列随机。

3. 标准库和第三方库的导入应该放在本地模块导入的前面。

4. 各个导入块之间应该使用一个空行进行分隔。

5. 对于现有的代码，如果导入顺序不符合上述规范，在重构代码时应该调整导入顺序以符合规范。


## 类型注解规范

1. 重构代码时，如果原来的代码中有类型注解，则相同功能的代码应该保留类型注解（可以对类型注解进行修改以保持准确性，但不应该删除类型注解）。

2. 重构代码时，如果原来的代码中没有类型注解，则重构的时候，如果某个函数的功能较为复杂或者参数较多，则应该添加类型注解来提高代码的可读性和可维护性。（对于简单的变量，可以不添加类型注解）

3. 对于参数化泛型，应该使用 `typing` 模块中的类型注解来指定参数化泛型的类型。
   - 例如，使用 `List[int]` 来表示一个包含整数的列表，使用 `Dict[str, Any]` 来表示一个键为字符串，值为任意类型的字典。


## 变量规范

1. 当确定某个变量/实例是某种类型的时候（优先按照类型注解确定，除非你分析出类型注解是错误的），可以不必使用 `or` 进行 fallback。


## 类属性使用规范

1. 应该尽量减少使用 getattr 和 setattr 方法，除非是在对一个动态类进行处理或者使用 Monkeypatch 完成 Pytest。

2. 在重构代码时，如果遇到 getattr 和 setattr，应该尝试检查这个类实例是否有这个属性，如果有，则直接替换为类属性访问写法。


## debug 规范

1. 不要总是想找兜底，一定要精准的找到问题的核心，然后提出建议，兜底是不合适，难以维护的。

2. 不要总是考虑 fallback，如果哪里有错误，一定要让他及时完整的暴露，而不是用 fallback 兜底掩盖过去。


## 运行/调试/构建/测试/依赖

优先使用 uv。

依赖项以 pyproject.toml 为准，要同步更新 requirements.txt。

不要总是考虑 fallback，如果哪里有错误，一定要让他及时完整的暴露，而不是用 fallback 兜底掩盖过去。


## 语言规范

项目的首选语言为简体中文，无论是注释语言，日志展示语言，还是 WebUI 展示语言都首要以简体中文为首要实现目标。


## WebUI 规范

如果遇到 UI 高度/布局问题：
- 对比展开前后 DOM，找新增元素和新增属性。
- 查 data-dashboard-style 主题样式，尤其是 !important。
- 查 computed style 的实际 height/min-height，而不是只看 Tailwind class。

如果遇到 UI 底纹、阴影、半透明、模糊或颜色叠加问题，先按 DOM 层级拆分父容器、触发器、内部装饰元素和伪元素，逐层查 computed style 的 background/background-color/background-image/backdrop-filter/box-shadow/opacity，不要只盯着截图中最显眼的子元素或只看 class。

涉及 Tabs/TabsList/TabsTrigger、Radix 或 motion 动画指示器时，要先确认视觉效果来自 TabsList 容器、TabsTrigger 本体、内部 motion/span，还是父级 header/card/dialog 的 backdrop-filter 或主题覆盖，再做最小范围修改。

Radix 组件不随便移出上下文，像 TabsTrigger 必须留在 TabsList 里。

修改完 WebUI，如果是小改动小修复，不用急着 npm run build。当完成一个较大功能新增或者较广重构时，才需要运行 npm run build。

WebUI 开发服务固定起到 7999 端口。


## Git 分支与推送

- 日常开发与交付在 **`dev`** 分支；`git push` 目标为 **`origin dev`**。
- **禁止** `git push origin dev:main` 或未经用户当次明确要求推送到 `main`。
- 扩展说明见工作区 `docs-src/provider-guide-references/agents-project-conventions.md` 中「Git 分支与推送规范」。


## Changelog 编写

`CHANGELOG.md` 只记录**本仓库会提交**的变更；其他子仓库、编排仓根目录脚本、以及 `config/` 本地配置等未纳入本仓 git 的内容**不得**写入。

建议分为两部分：用户感知功能侧、开发侧（含修复和插件 SDK、API 改动）。最好一个功能一行，按模块分。

一般不写入 Changelog 的内容：

- 版本号提升或更新项目依赖（无独立行为说明时）
- 未纳入本仓库提交的变更（`config/` 本地配置、`provider-docs/`、编排根路径等）——**改记入 `RECORD.md`**，见 `agents-project-conventions.md`「RECORD.md 编写」

## RECORD.md 编写

`RECORD.md` 为本地工作日志（gitignore，永不提交）。**不按 git 可提交范围过滤**；编排根、各子仓库、`config/`、插件独立仓、测试统计等本会话实质变更均可写入。与 `CHANGELOG.md`（仅本仓可提交变更）分工。格式细则见 `docs-src/provider-guide-references/agents-project-conventions.md`。