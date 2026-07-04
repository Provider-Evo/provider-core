# 项目开发规范与 AGENTS.md 自动生成指令

本文件同时作为项目开发规范和执行指令。收到本指令后，你必须立即开始分析当前项目，并按照本文件的全部要求生成分层的
AGENTS.md 文件。不得询问"需要我做什么"，不得等待进一步指示。

---

## 第零部分：执行指令（立即生效）

收到本指令后，你必须按照以下工作流程立即执行，无需额外确认：

1. **发现与分析阶段：** 并发执行项目结构扫描、代码分析、现有文档读取。
2. **评分与决策阶段：** 对所有目录进行混淆密度评分，决定哪些目录需要创建 AGENTS.md。
3. **生成阶段：** 先生成根目录 AGENTS.md，再并发生成子目录 AGENTS.md。
4. **审查阶段：** 去重、裁剪、验证每条记录是否符合"防止具体错误"的核心标准。

详细的工作流程规范见本文件第十一部分。

---

## 第一部分：核心编程原则

### 1.1 基础设计原则

- **可读性优先 (Readability First)：** 遵循 "The Zen of Python"，代码应当简洁明了，简洁胜过复杂，明确胜过隐晦。
- **DRY (Don't Repeat Yourself)：** 通过函数、类、模块和装饰器消除重复代码，充分利用语言的抽象能力。
- **高内聚，低耦合 (High Cohesion, Low Coupling)：** 利用模块系统和包结构实现清晰的代码组织，每个模块专注于单一职责。
- **KISS (Keep It Simple, Stupid)：** 优先选择简单直接的实现方案，避免过度设计。
- **YAGNI (You Aren't Gonna Need It)：** 不编写当前不需要的功能，避免预测性编程。

### 1.2 DDD + TDD 融合开发方法论

- **领域驱动设计 (Domain-Driven Design)：** 采用 Domain Model 并结合类型系统，以业务领域为核心组织代码结构。
- **测试驱动开发 (Test-Driven Development)：** 每完成一个功能模块就立即编写相应的测试。
- **渐进式开发策略：** 每写一个单元就进行验证。
- **领域边界清晰：** 通过包和模块系统明确领域关系对应。
- **AI 辅助质量保障：** 结合 AI 工具和静态分析工具提升代码质量。

---

## 第二部分：沟通与语言规范

### 2.1 默认语言

请默认使用简体中文进行所有交流、解释和思考过程的陈述。

### 2.2 代码与术语

所有代码实体（变量名、函数名、类名、模块名等）及技术术语必须保持英文原文，不得翻译。

### 2.3 注释规范

代码注释应使用中文编写。Python 项目遵循 PEP 257 文档字符串规范；其他语言项目遵循对应语言的文档注释规范（如 JSDoc、GoDoc
 等）。行内注释用中文简明扼要地说明意图。

### 2.4 类型注解强制要求

Python 项目中所有函数和方法必须添加完整的类型注解，包括参数类型和返回类型。TypeScript
项目必须使用严格模式。其他语言项目必须充分利用其类型系统。

---

## 第三部分：批判性反馈与破框思维

### 3.1 审慎分析

必须以审视和批判的眼光分析所有输入代码和设计方案，主动识别潜在的问题和违背编程最佳实践的模式。

### 3.2 坦率直言

指出不符合语言惯用风格的代码模式时，必须同时推荐更优雅的解决方案，给出具体的改进代码示例。

### 3.3 严厉质询

对于违背语言社区规范或最佳实践的代码，必须明确指出违规之处，解释为何违规，并提供符合规范的改进建议。不得因礼貌而回避问
题。

---

## 第四部分：开发与调试策略

### 4.1 问题解决策略

- **坚韧不拔的解决问题：** 充分利用调试工具和日志系统进行问题定位，不轻易放弃。
- **逐个击破：** 将复杂问题分解为可验证的小单元，逐步验证每个组件的功能。
- **探索有效替代方案：** 优先考虑标准库和成熟的第三方库解决方案，避免重复造轮子。
- **禁止伪造实现：** 严禁使用占位符代码（如 Python 的 `pass`、JavaScript 的空函数体、Go
的空实现）作为功能实现。所有代码必须具备真实的业务逻辑。

### 4.2 测试驱动开发规范

#### 4.2.1 测试框架选择

根据项目技术栈选择对应的测试框架：Python 使用 pytest，JavaScript/TypeScript 使用 Jest 或 Vitest，Go 使用标准 testing
包。

#### 4.2.2 Red-Green-Refactor 循环

严格遵循三步循环：

1. **Red（红）：** 先编写一个会失败的测试用例，确认测试确实失败。
2. **Green（绿）：** 编写最少量的代码使测试通过，不多写一行。
3. **Refactor（重构）：** 在测试通过的保护下优化代码结构，确保测试仍然全部通过。

#### 4.2.3 测试覆盖率

核心业务逻辑的测试覆盖率必须达到 90% 以上。

---

## 第五部分：Python 特定规范

本部分仅适用于 Python 项目。非 Python 项目可跳过本部分，但必须遵循对应语言的等效规范。

### 5.1 虚拟环境强制规范

所有 Python 项目必须使用虚拟环境，推荐使用 `venv` 或 `conda`。严禁在全局 Python 环境中安装项目依赖。

```bash
# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
source venv/bin/activate  # Linux/macOS
.\venv\Scripts\activate   # Windows
```

### 5.2 依赖管理

使用 `requirements.txt` 或 `pyproject.toml`
管理项目依赖。所有依赖必须明确指定版本号或版本范围，禁止使用不受约束的版本。

```bash
pip install -r requirements.txt
pip freeze > requirements.txt

# 或使用 poetry
poetry init
poetry add package_name
poetry install
```

### 5.3 PEP 规范遵循

严格遵守 PEP 8（代码风格）和 PEP 257（文档字符串）规范。使用 black 进行代码格式化，使用 isort 进行导入排序。

### 5.4 文档字符串

遵循 PEP 257，为所有公共函数、方法和类编写详细的中文文档字符串，包括功能描述、参数说明（Args）、返回值说明（Returns）和
异常说明（Raises）。

### 5.5 导入排序

使用 isort 工具进行导入语句的排序和分组，遵循以下顺序：标准库导入、第三方库导入、本地应用或库导入。每组之间用空行分隔。

### 5.6 异步编程规范

异步函数必须使用 `async/await` 语法，禁止使用回调模式。所有 I/O 操作应优先使用异步版本。注意 Python 的 GIL 限制，CPU
密集型任务应考虑使用 `multiprocessing` 或 `concurrent.futures.ProcessPoolExecutor`。

### 5.7 错误处理与日志

- 使用 `logging` 标准库，禁止使用 `print` 语句进行调试输出。
- 日志消息使用 `%s` 格式化而非 f-string，以避免不必要的字符串插值开销。
- 为每个模块创建独立的 logger：`logger = logging.getLogger(__name__)`。
- 设计清晰的自定义异常层次结构，区分业务异常和系统异常。

### 5.8 质量检查命令

```bash
pytest                              # 运行测试
pytest --cov=src --cov-report=html  # 覆盖率报告
mypy src/                           # 类型检查
black src/                          # 代码格式化
isort src/                          # 导入排序
pylint src/                         # 代码检查
flake8 src/                         # 代码检查
```

### 5.9 推荐项目结构

```
project/
├── src/
│   ├── domain/              # 领域模型层
│   │   ├── __init__.py
│   │   ├── entities/        # 实体类
│   │   ├── value_objects/   # 值对象
│   │   └── services/        # 领域服务
│   ├── application/         # 应用层
│   │   ├── __init__.py
│   │   ├── use_cases/       # 用例
│   │   └── dtos/            # 数据传输对象
│   ├── infrastructure/      # 基础设施层
│   │   ├── __init__.py
│   │   ├── repositories/    # 仓储实现
│   │   └── adapters/        # 适配器
│   └── interfaces/          # 接口层
│       ├── __init__.py
│       └── web/             # Web 接口
├── tests/
│   ├── conftest.py          # 共享 fixture
│   ├── unit/                # 单元测试
│   ├── integration/         # 集成测试
│   └── e2e/                 # 端到端测试
├── docs/                    # 文档
├── AGENTS.md                # 项目陷阱与易错点活文档
├── requirements.txt         # 依赖管理
├── pyproject.toml           # 项目配置
└── README.md                # 项目说明
```

### 5.10 技术栈推荐

| 类别 | 推荐工具 |
|------|----------|
| Web 框架 | FastAPI（异步）/ Flask（同步）/ Django（全栈） |
| ORM | SQLAlchemy / Django ORM / Tortoise ORM |
| 测试框架 | pytest + pytest-asyncio |
| 类型检查 | mypy |
| 代码格式化 | black + isort |
| 代码检查 | pylint + flake8 |
| 文档生成 | Sphinx / MkDocs |
| 异步编程 | asyncio + aiohttp |

---

## 第六部分：全栈项目通用规范

### 6.1 前端项目规范（适用于 JavaScript / TypeScript 项目）

- 使用 TypeScript 严格模式，所有函数必须有完整的类型标注。
- 使用 ESLint + Prettier 进行代码检查和格式化。
- 组件文件使用 PascalCase 命名，工具函数文件使用 camelCase 命名。
- 测试使用 Jest 或 Vitest，遵循 TDD 循环。
- 依赖管理使用 package.json，锁文件（package-lock.json 或 pnpm-lock.yaml）必须提交到版本控制。

### 6.2 后端项目规范（适用于 Go / Rust / Java 等项目）

- 遵循各语言社区的官方代码风格指南。
- 充分利用语言的类型系统和编译期检查。
- 测试使用语言标准测试框架。
- 错误处理遵循语言惯用模式（Go 的多返回值、Rust 的 Result 类型等）。

### 6.3 数据库与基础设施

- 数据库迁移脚本必须版本化管理。
- Docker 配置必须完整且可复现。
- CI/CD 配置文件中的非显而易见步骤必须添加注释。
- 环境变量管理使用 `.env` 文件，敏感信息不得提交到版本控制。

### 6.4 资源管理规范

必须正确管理和关闭所有系统资源，包括但不限于文件句柄、数据库连接、网络连接和线程池。优先使用上下文管理器或语言提供的资
源释放机制确保资源的确定性释放，避免出现资源泄漏。

---

## 第七部分：领域驱动设计实施指南

### 7.1 实体设计示例（Python）

```python
from dataclasses import dataclass
from typing import Optional
from uuid import UUID, uuid4


@dataclass
class User:
    """用户实体。

    表示系统中的注册用户，包含用户的基本信息和行为。

    Attributes:
        id: 用户唯一标识符，自动生成。
        name: 用户姓名。
        email: 用户邮箱地址。
    """

    name: str
    email: str
    id: UUID = None

    def __post_init__(self) -> None:
        """初始化后处理，自动生成 UUID。"""
        if self.id is None:
            self.id = uuid4()

    def change_email(self, new_email: str) -> None:
        """更改用户邮箱。

        Args:
            new_email: 新的邮箱地址。

        Raises:
            ValueError: 当邮箱格式无效时抛出。
        """
        if not self._is_valid_email(new_email):
            raise ValueError("Invalid email format")
        self.email = new_email

    def _is_valid_email(self, email: str) -> bool:
        """验证邮箱格式。

        Args:
            email: 待验证的邮箱地址。

        Returns:
            邮箱格式是否有效。
        """
        return "@" in email and "." in email.split("@")[-1]
```

### 7.2 值对象设计示例（Python）

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    """货币值对象。

    不可变对象，表示一个带币种的金额。

    Attributes:
        amount: 金额数值，不可为负。
        currency: 币种代码，默认为 USD。
    """

    amount: float
    currency: str = "USD"

    def __post_init__(self) -> None:
        """初始化后验证，确保金额非负。"""
        if self.amount < 0:
            raise ValueError("Amount cannot be negative")

    def add(self, other: "Money") -> "Money":
        """与另一个货币值相加。

        Args:
            other: 另一个货币值对象。

        Returns:
            相加后的新货币值对象。

        Raises:
            ValueError: 当两个货币币种不同时抛出。
        """
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)
```

### 7.3 仓储模式示例（Python）

```python
from abc import ABC, abstractmethod
from typing import List, Optional
from uuid import UUID


class UserRepository(ABC):
    """用户仓储抽象基类。

    定义用户数据持久化的接口契约，
    具体实现由基础设施层提供。
    """

    @abstractmethod
    async def save(self, user: User) -> None:
        """保存用户实体。

        Args:
            user: 待保存的用户实体。
        """
        pass

    @abstractmethod
    async def find_by_id(self, user_id: UUID) -> Optional[User]:
        """根据 ID 查找用户。

        Args:
            user_id: 用户唯一标识符。

        Returns:
            找到的用户实体，未找到时返回 None。
        """
        pass

    @abstractmethod
    async def find_by_email(self, email: str) -> Optional[User]:
        """根据邮箱查找用户。

        Args:
            email: 用户邮箱地址。

        Returns:
            找到的用户实体，未找到时返回 None。
        """
        pass
```

---

## 第八部分：测试最佳实践

### 8.1 单元测试示例（Python / pytest）

```python
import pytest
from src.domain.entities.user import User
from src.domain.value_objects.money import Money


class TestUser:
    """用户实体单元测试。"""

    def test_user_creation(self) -> None:
        """测试用户创建时自动生成 ID。"""
        user = User(name="张三", email="zhangsan@example.com")
        assert user.name == "张三"
        assert user.email == "zhangsan@example.com"
        assert user.id is not None

    def test_change_email_success(self) -> None:
        """测试成功更改邮箱。"""
        user = User(name="张三", email="zhangsan@example.com")
        user.change_email("new@example.com")
        assert user.email == "new@example.com"

    def test_change_email_invalid_format(self) -> None:
        """测试更改邮箱时传入无效格式应抛出异常。"""
        user = User(name="张三", email="zhangsan@example.com")
        with pytest.raises(ValueError, match="Invalid email format"):
            user.change_email("invalid-email")


class TestMoney:
    """货币值对象单元测试。"""

    def test_money_creation(self) -> None:
        """测试货币值对象的正常创建。"""
        money = Money(100.0, "USD")
        assert money.amount == 100.0
        assert money.currency == "USD"

    def test_money_negative_amount_raises_error(self) -> None:
        """测试负金额应抛出异常。"""
        with pytest.raises(ValueError, match="Amount cannot be negative"):
            Money(-10.0, "USD")

    def test_money_add_same_currency(self) -> None:
        """测试同币种货币相加。"""
        money1 = Money(100.0, "USD")
        money2 = Money(50.0, "USD")
        result = money1.add(money2)
        assert result.amount == 150.0
        assert result.currency == "USD"

    def test_money_add_different_currency_raises_error(self) -> None:
        """测试不同币种货币相加应抛出异常。"""
        money1 = Money(100.0, "USD")
        money2 = Money(50.0, "EUR")
        with pytest.raises(ValueError, match="Cannot add different currencies"):
            money1.add(money2)
```

---

## 第九部分：开发强制要求

以下要求具有强制性，所有项目开发中必须严格执行，不得以任何理由豁免：

1. **环境隔离强制要求：** Python 项目必须使用虚拟环境；Node.js 项目必须使用 node_modules
隔离；严禁在全局环境中安装项目依赖。
2. **类型系统强制要求：** Python 必须添加完整类型注解；TypeScript 必须使用严格模式；其他语言必须充分利用类型系统。
3. **测试覆盖率要求：** 核心业务逻辑的测试覆盖率不低于 90%。
4. **代码风格要求：** 必须通过项目配置的代码检查工具（linter、formatter）。
5. **文档要求：** 所有公共 API 必须有详细的文档注释。
6. **规范遵循：** 严格遵守各语言社区的官方代码风格规范。
7. **资源管理规范：** 必须正确管理和关闭所有系统资源，避免出现资源泄漏。
8. **禁止伪造实现：** 严禁使用占位符代码作为功能实现，所有代码必须具备真实的业务逻辑。
9. **禁止使用 emoji：** 代码、注释和文档中禁止使用任何 emoji 字符。
10. **AGENTS.md 维护要求：** 在所有工作会话中持续更新 AGENTS.md 活文档，记录遇到的错误、意外和易混淆之处。
11. **功能完整性要求：** 所有功能禁止遗漏和省略，每个功能模块必须完整实现，所有要素达到理论极限的质量标准。

---

## 第十部分：注意事项

- 充分利用语言的惯用特性和内置功能，编写符合社区风格的代码。
- 优先使用标准库解决问题，谨慎选择第三方依赖，引入前评估其维护状态和安全性。
- 确保所有系统资源的正确关闭，使用语言提供的资源释放机制避免资源泄漏。
- 始终重视代码的可读性和简洁性，可读性优先于性能优化（除非有明确的性能需求）。
- 定期更新依赖包，关注安全漏洞通告。
- 所有代码保持最佳实践标准，力求达到理论极限的代码质量。
- 在开发过程中遇到的任何意外情况、易错点和混淆之处，必须实时更新到 AGENTS.md 活文档中。

---

## 第十一部分：AGENTS.md 生成工作流程

本部分定义了 AGENTS.md 文件的自动生成工作流程。收到本指令后，必须立即按照以下四个阶段顺序执行。

### 11.1 AGENTS.md 核心理念

AGENTS.md 不是项目文档，不是 README，不是架构概述。AGENTS.md 的唯一目的是：**记录 AI
代理在本项目中工作时会遇到的常见错误、易混淆之处、意外行为和陷阱。**

AGENTS.md 中的每一条记录都必须回答这个问题：**"未来在此项目工作的 AI 代理会因为什么而犯错或困惑，应该如何正确处理？"**

如果一条信息不能预防某个具体的错误或消除某个具体的困惑，那么它就不属于 AGENTS.md。

### 11.2 阶段一：发现与分析（并发执行）

使用任务管理工具记录所有阶段的进度，标记每个阶段的开始和完成状态。

#### 11.2.1 立即启动后台探索代理

不要等待，这些代理在主会话工作时异步运行。按照以下全部探索方向并发启动后台代理：

**探索代理 1 -- 项目结构偏差：**
预测检测到的语言/框架的标准项目结构模式，仅报告偏差和意外之处。什么会让一个期望标准布局的代理感到困惑？

**探索代理 2 -- 入口点混淆：**
找到主文件和入口点，报告非标准的、具有误导性的或令人困惑的组织方式。什么样的入口点假设是错误的？

**探索代理 3 -- 隐藏约定：** 找到配置文件（如 .eslintrc、pyproject.toml、.editorconfig、tsconfig.json、Cargo.toml
等），报告与社区默认值或通用标准相矛盾的项目特定规则。代理按默认假设行事会犯什么错？

**探索代理 4 -- 显式反模式与警告：** 找到代码中包含 `DO
NOT`、`NEVER`、`ALWAYS`、`DEPRECATED`、`HACK`、`WORKAROUND`、`XXX`、`FIXME`、`WARNING`、`TODO`
等标记的注释，列出被禁止的模式和已知陷阱，附带完整上下文。

**探索代理 5 -- 构建与 CI 意外：** 找到 `.github/workflows`、`Makefile`、`Dockerfile`、`docker-compose.yml`
等配置，报告非标准模式、意外的构建步骤、隐藏的前置条件、会导致代理犯错的环境假设。

**探索代理 6 -- 测试模式陷阱：**
找到测试配置和测试结构，报告与框架默认值不同的独特约定。代理会在什么测试命令或模式上犯错？

**探索代理 7 -- 命名与导入混淆：** 找到名称相似的文件或模块、重导出、桶文件（barrel
files）、循环依赖、路径别名配置，报告什么会导致代理编辑错误的文件或从错误的位置导入。

**探索代理 8 -- 版本与兼容性陷阱：** 检查运行时版本、依赖版本、已弃用 API
的使用、兼容性垫片（shims），报告什么版本假设会导致代理犯错。

#### 11.2.2 动态代理生成

在完成 bash 结构分析后，根据项目规模动态生成额外的探索代理：

| 因素 | 阈值 | 额外代理数 |
|------|------|-----------|
| 总文件数 | 超过 100 | 每 100 个文件加 1 个 |
| 总代码行数 | 超过 10000 | 每 10000 行加 1 个 |
| 目录深度 | 大于等于 4 | 加 2 个用于深层探索 |
| 大文件（超过 500 行） | 超过 10 个 | 加 1 个用于复杂度热点 |
| 单体仓库 | 检测到 | 每个包或工作区加 1 个 |
| 多语言项目 | 超过 1 种 | 每种语言加 1 个 |

额外的动态代理应聚焦于容易混淆的区域：深层嵌套、包含隐藏逻辑的大文件、跨包依赖等。

动态代理的探索方向示例：

- **大文件分析：** 找到超过 500
行的文件，报告隐藏的副作用、非显而易见的初始化顺序、会让线性阅读代码的代理感到意外的状态变更。
- **深层模块混淆：** 找到深度大于等于 4 的模块中与顶层约定不同的隐藏模式和内部约定。
- **跨切关注点：** 找到共享工具函数、全局状态、单例、事件总线，报告修改这些内容时会让代理感到意外的副作用。

#### 11.2.3 主会话并发分析

在后台代理运行的同时，主会话执行以下分析：

**bash 结构分析：**

```bash
# 目录深度与文件数统计
find . -type d -not -path '*/\.*' -not -path '*/node_modules/*' -not -path '*/venv/*' -not -path '*/dist/*' -not -path
'*/build/*' -not -path '*/__pycache__/*' -not -path '*/.venv/*' | awk -F/ '{print NF-1}' | sort -n | uniq -c

# 每个目录的文件数（前 30 个）
find . -type f -not -path '*/\.*' -not -path '*/node_modules/*' -not -path '*/venv/*' -not -path '*/__pycache__/*' |
sed 's|/[^/]*$||' | sort | uniq -c | sort -rn | head -30

# 按文件扩展名统计代码集中度
find . -type f \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.jsx" -o -name "*.go" -o
-name "*.rs" -o -name "*.java" \) -not -path '*/node_modules/*' -not -path '*/venv/*' | sed 's|/[^/]*$||' | sort | uniq
 -c | sort -rn | head -20

# 查找已有的 AGENTS.md 或 CLAUDE.md
find . -type f \( -name "AGENTS.md" -o -name "CLAUDE.md" \) -not -path '*/node_modules/*' -not -path '*/venv/*'
2>/dev/null

# 查找可能造成混淆的模式：符号链接、隐藏配置、非常规文件扩展名
find . -type l -not -path '*/node_modules/*' -not -path '*/.git/*' 2>/dev/null
find . -name "*.local" -o -name "*.override" -o -name "*.patch" 2>/dev/null | head -20

# 测量项目规模
total_files=$(find . -type f -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/venv/*' -not -path
'*/__pycache__/*' | wc -l)
total_lines=$(find . -type f \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.go" -o -name
"*.rs" \) -not -path '*/node_modules/*' -not -path '*/venv/*' -exec wc -l {} + 2>/dev/null | tail -1 | awk '{print
$1}')
large_files=$(find . -type f \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" -o -name "*.js" -o -name "*.go" -o -name
"*.rs" \) -not -path '*/node_modules/*' -not -path '*/venv/*' -exec wc -l {} + 2>/dev/null | awk '$1 > 500 {count++}
END {print count+0}')
max_depth=$(find . -type d -not -path '*/node_modules/*' -not -path '*/.git/*' -not -path '*/venv/*' | awk -F/ '{print
NF}' | sort -rn | head -1)
```

**读取已有的 AGENTS.md 文件：**

对于发现的每个已有文件，读取其内容，提取已记录的意外、混淆点、反模式和已知陷阱，存储到现有内容映射中，并标记可能已过时
的条目。

**LSP 代码映射（如可用）：**

检查 LSP 服务器可用性，获取入口点的文档符号，查询关键符号（类、接口、函数），分析高引用符号的中心性（高引用符号是代理犯
错的高风险区域）。如果 LSP 不可用，依赖探索代理和代码分析的结果。

#### 11.2.4 收集后台代理结果

在主会话分析完成后，收集所有后台代理的输出结果。

**合并所有来源的发现：** bash 结构分析 + LSP 代码映射 + 已有 AGENTS.md 内容 + 所有探索代理结果。

**将所有发现按优先级分类：**

1. **代理一定会犯的错误**（最高优先级）
2. **混淆点**（高优先级）
3. **意外之处**（中等优先级）
4. **非显而易见的约定**（仅在违反会导致错误时才收录）

### 11.3 阶段二：评分与位置决策

#### 11.3.1 混淆密度评分矩阵

| 因素 | 权重 | 高阈值 | 数据来源 | 重要性原因 |
|------|------|--------|----------|-----------|
| 偏离标准布局 | 4 倍 | 超过 3 处偏差 | 探索代理 | 偏差越多，代理犯错越多 |
| 反模式注释 | 3 倍 | 超过 5 个警告 | 探索代理 | 人类开发者明确标记的陷阱 |
| 文件数量 | 2 倍 | 超过 20 个 | bash 分析 | 文件越多，编辑错误文件的可能越大 |
| 命名歧义 | 3 倍 | 检测到 | 探索代理 | 相似名称导致目标选错 |
| 隐藏副作用 | 3 倍 | 检测到 | 探索代理 | 不可见的后果 |
| 非显而易见的配置 | 2 倍 | 有覆盖项 | 探索代理 | 默认假设失效 |
| 子目录数量 | 1 倍 | 超过 5 个 | bash 分析 | 导航混淆 |
| 模块边界 | 2 倍 | 有 index 或 __init__ | bash 分析 | 导入混淆 |
| 跨切引用 | 2 倍 | 超过 20 个引用 | LSP 分析 | 变更的连锁影响 |

#### 11.3.2 决策规则

| 得分 | 行动 |
|------|------|
| 根目录 (.) | 始终创建 |
| 超过 15 | 创建 AGENTS.md -- 高混淆密度 |
| 8 到 15 | 仅当该目录有独特的混淆域（陷阱与父目录不同）时创建 |
| 低于 8 | 跳过 -- 父目录的 AGENTS.md 已足够覆盖 |

#### 11.3.3 输出格式

确定需要创建 AGENTS.md 的位置列表，记录每个位置的路径、评分和创建原因。

### 11.4 阶段三：生成 AGENTS.md 文件

#### 11.4.1 文件写入规则

如果目标路径已存在 AGENTS.md 文件，使用编辑工具修改。如果不存在，使用写入工具创建。绝不使用写入工具覆盖已有文件。操作前
必须通过读取或发现阶段的结果确认文件是否已存在。

#### 11.4.2 根目录 AGENTS.md 文件模板

```
# AGENTS.md -- 错误、意外与易混淆点

> **用途**：本文件记录 AI 代理在本项目中工作时常见的错误和易混淆之处。
> 如果你遇到了意外情况，请立即告知开发者并追加到本文件中，
> 以防未来的代理重蹈覆辙。
>
> **活文档**：在工作过程中实时更新本文件。

**最后更新：** {ISO 时间戳}
**更新者：** {代理标识或任务描述，如果不知道或不确定就不用写这一栏信息}

---

## 项目身份
{仅用一到两句话描述：这是什么项目，核心技术栈是什么。
仅提供足以校准预期的最少上下文。}

## 必须避免的严重错误
{最高优先级。AI 代理在没有警告的情况下一定会犯的错误。}

### [CRITICAL] {错误标题}
**你会假设：** {自然的或默认的假设}
**实际情况：** {令人意外的现实}
**犯错后果：** {错误假设导致的具体后果}
**正确做法：** {应该怎么做}

## 易混淆之处
{存在歧义、误导性或非显而易见的事项。}

### [WARNING] {混淆标题}
**混淆之处：** {描述}
**澄清：** {真相}
**示例：** {如有必要，提供具体示例}

## 结构性意外
{项目布局偏离预期的地方。}

| 预期 | 实际 | 影响 |
|------|------|------|

## 命名陷阱
{文件、函数、变量中具有误导性名称的条目。}

| 名称 | 你以为的含义 | 实际含义或行为 |
|------|-------------|----------------|

## 依赖与导入陷阱
{非显而易见的导入规则、重导出、路径别名、循环依赖风险。}

## 构建、测试与运行意外
{不按预期工作的命令、隐藏的前置条件、环境要求。}

## 反模式（明确禁止）
{看似合理但在本项目中被禁止的做法。}

| 禁止做法 | 应采取的做法 | 原因 |
|----------|-------------|------|

## 配置陷阱
{以非显而易见方式覆盖默认值的设置。}

## 最近发现的意外日志
{在此追加新发现，按时间倒序排列。最近的条目在最上方。}

<!-- 当你遇到意外时，在此追加：
### {ISO 日期} -- {标题}
**上下文：** {你正在执行的任务}
**意外：** {发生了什么}
**解决方案：** {正确的行为或做法}
-->
```

**质量门槛：**

- 行数控制在 50 到 200 行之间。
- 零通用建议（不包含适用于所有项目的内容）。
- 零显而易见的信息（不包含代理在没有帮助的情况下也能正确处理的内容）。
- 每条记录都描述一个具体的错误、混淆或意外。
- 每条记录都有可操作的解决方案。

#### 11.4.3 子目录 AGENTS.md 文件

对评分结果中每个需要创建 AGENTS.md 的子目录，按以下规则生成：

- 行数控制在 20 到 80 行之间。
- 绝不重复父级 AGENTS.md 中已记录的混淆点，需要时引用父文件。
- 仅包含该目录特有的错误、意外和易混淆之处。
- 每条记录都必须回答："AI 代理在这里会犯什么错？"

子目录 AGENTS.md 文件的章节（仅使用有实际内容的章节）：

- 必须避免的错误（[CRITICAL] 条目）
- 易混淆之处（[WARNING] 条目）
- 本地约定（仅在与父级或项目级别约定不同时才包含）
- 命名陷阱（如有）
- 最近发现的意外日志（空模板，便于后续追加）

必须包含活文档头部，提醒未来的代理进行更新。

### 11.5 阶段四：审查与去重

对每个生成的文件，逐条验证是否符合核心理念：

**验证清单：**

- 每条记录都描述一个具体的错误、混淆或意外。不符合的条目删除。
- 每条记录都是可操作的，包含"正确做法"或"澄清"部分。不可操作的条目删除。
- 没有通用建议。发现后删除。
- 没有显而易见的信息。发现后删除。
- 子文件不重复父文件的内容。发现重复后删除子文件中的重复项，改为引用父文件。
- 语言简洁扼要，电报式风格。冗长的段落必须精简。
- "最近发现的意外日志"章节存在。缺失则补充。
- 活文档头部存在。缺失则补充。

**必须删除的内容类型：**

- 不能预防错误的项目概述。
- 没有混淆上下文的文件清单。
- 标准框架约定（除非项目违反了这些约定）。
- 不具有误导性名称的代码符号映射。
- 架构图（除非架构本身令人意外）。

### 11.6 最终报告

生成完成后，输出以下格式的最终报告：

```
=== AGENTS.md 生成完成 ===

模式: {更新已有文件 | 全新创建}

生成的文件:
  [OK] ./AGENTS.md (根目录, {N} 行, {N} 条混淆记录)
  [OK] ./src/hooks/AGENTS.md ({N} 行, {N} 条混淆记录)
  ...

文档化的混淆点总数: {总计}
  [CRITICAL] 严重错误: {N}
  [WARNING] 混淆点: {N}
  结构性意外: {N}
  命名陷阱: {N}

分析的目录数: {N}
创建的 AGENTS.md: {N}
更新的 AGENTS.md: {N}

文件层级:
  ./AGENTS.md
  ├── src/hooks/AGENTS.md
  └── src/api/AGENTS.md

持续更新协议: 已激活
后续工作中发现的意外将被实时追加。
```

---

## 第十二部分：AGENTS.md 持续更新协议

本协议在 AGENTS.md 文件生成完成后永久生效，适用于所有后续工作会话。

### 12.1 监控意外

在每个任务执行过程中，持续监控以下情况的发生：

- 某个行为与预期不同。
- 某个文件不在预期的位置。
- 某个函数的行为与其名称暗示的不一致。
- 某个测试需要非显而易见的准备工作。
- 某个构建步骤有隐藏的依赖。
- 某个 API 有未文档化的约束。
- 某个配置静默地覆盖了某些设置。
- 某个导入路径或模块解析方式与预期不同。
- 某个环境变量或运行时条件影响了代码行为。

### 12.2 检测到意外时的处理流程

1. 立即告知开发者："我遇到了一个意外情况：{描述}。我正在将其添加到 AGENTS.md。"
2. 确定正确的 AGENTS.md 文件（选择最具体的目录层级）。
3. 追加到"最近发现的意外日志"章节，使用以下格式：

```
### {ISO 日期} -- {简要标题}
**上下文：** {你正在执行的任务}
**意外：** {你预期什么 vs 实际发生了什么}
**解决方案：** {正确的做法，经开发者确认或调查验证}
```

4. 如果该意外是严重的（会导致数据丢失、破坏构建或浪费大量时间），同时在"必须避免的严重错误"章节添加一条 [CRITICAL]
记录。

### 12.3 因项目特性犯错时的处理流程

1. 告知开发者所犯的错误及其原因。
2. 在"必须避免的严重错误"章节添加一条 [CRITICAL]
记录，包含：你的假设是什么、实际情况是什么、错误导致了什么后果、正确做法是什么。
3. 在"最近发现的意外日志"中记录此事件。

### 12.4 发现现有条目过时或错误时的处理流程

1. 告知开发者："AGENTS.md 条目 '{标题}' 似乎已过时，因为 {原因}。正在更新。"
2. 编辑或删除该条目。
3. 在"最近发现的意外日志"中记录此变更。

此协议不是可选的。持续维护 AGENTS.md 是与完成指定任务同等重要的核心职责。

---

## 第十三部分：AGENTS.md 内容反模式

以下内容类型不得出现在 AGENTS.md 中：

| 反模式类型 | 说明 |
|-----------|------|
| 项目文档 | AGENTS.md 不是 README，不应包含"入门指南"或架构概述（除非架构本身令人意外） |
| 显而易见的惯例 | 不要记录"测试放在 /tests 目录"这类信息，除非测试实际上不在那里 |
| 通用最佳实践 | 不要包含适用于所有同类项目的通用建议 |
| 无混淆上下文的代码映射 | 不要列出代码符号清单，除非其名称具有误导性 |
| 冗长的解释 | 保持简洁，电报式风格，每个词都必须有存在的价值 |
| 静态快照 | AGENTS.md 必须持续更新，不仅仅在初始生成时维护 |
| 层级间冗余 | 子文件绝不重复父文件的内容，需要时引用父文件 |

以下是工作流程层面的反模式：

| 反模式类型 | 说明 |
|-----------|------|
| 静态代理数量 | 必须根据项目规模和深度动态调整代理数量 |
| 顺序执行 | 必须并发执行（探索代理与 LSP 分析同时进行） |
| 忽略已有内容 | 始终先读取已有文件，保留仍然有效的混淆点 |
| 过度生成 | 并非每个目录都需要 AGENTS.md，仅混淆密度高的目录才需要 |
| 跳过验证 | 每条记录都必须通过"这是否能预防一个具体的错误"测试 |

---如果是  根目录下的 AGENTS.md，那么一定要在开头加**文件指示**一栏，除非文件不存在

如：
```
# AGENTS.md -- 错误、意外与易混淆点

> **用途**：本文件记录 AI 代理在本项目中工作时常见的错误和易混淆之处。
> 如果你遇到了意外情况，请立即告知开发者并追加到本文件中，
> 以防未来的代理重蹈覆辙。
>
> **活文档**：在工作过程中实时更新本文件。

**文件指示**：
- 务必遵循的Python代码开发规范 ：.agents/PYTHON_GUIDE.md
- 务必遵循的AGENTS.md编写规范：.agents/AGENTS_MD_GUIDE.md
- 务必遵循的分模块开发规范：.agents/MODULE_GUIDE.md
```

本规范融合了 Python 的优雅简洁原则、全栈项目的通用开发标准、DDD 和 TDD 的核心方法论、以及 AGENTS.md
活文档的持续知识管理机制，为项目开发和项目知识文档化提供全面、严谨、可直接执行的指导框架。收到本指令后立即按照第十一部
分的工作流程开始执行。
