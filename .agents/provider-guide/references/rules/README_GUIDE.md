```markdown
# CLAUDE - README.md 编写规范

This file provides guidance to Claude Code (claude.ai/code) when writing comprehensive README.md files.

### 第一部分：核心编写原则 (Guiding Principles)
这是编写 README.md 的顶层思想，指导所有具体的内容创作行为。

#### 基础设计原则
- **用户中心原则 (User-Centric)：** README 是写给读者的，必须站在读者角度思考他们需要什么信息，以最短时间让读者理解项目价值和使用方法。
- **完整性优先 (Completeness First)：** 信息必须详尽无遗漏，涵盖项目的方方面面，让读者无需查阅其他文档即可上手。
- **结构清晰 (Clear Structure)：** 采用层次分明的标题结构，使用目录导航，确保读者能快速定位所需信息。
- **实用性导向 (Practicality-Oriented)：** 提供可直接复制执行的命令和代码示例，减少读者的认知负担。

#### 专业性原则
- **技术准确性 (Technical Accuracy)：** 所有技术描述、命令和代码必须经过验证，确保可正确执行。
- **版本一致性 (Version Consistency)：** 明确标注所有依赖的版本要求，避免版本不兼容问题。
- **跨平台考虑 (Cross-Platform Consideration)：** 针对不同操作系统提供相应的安装和运行指导。

#### 可维护性原则
- **模块化内容 (Modular Content)：** 将 README 拆分为逻辑清晰的独立章节，便于后续更新维护。
- **时效性标记 (Timeliness Marking)：** 对于可能变化的内容（如版本号、API 端点等）进行明确标记。
- **变更日志关联 (Changelog Association)：** 与 CHANGELOG.md 保持联动，确保版本信息同步。

### 第二部分：具体执行指令 (Actionable Instructions)
这是 Claude 在编写 README.md 时需要严格遵守的具体操作指南。

#### 沟通与语言规范
- **默认语言：** 请默认使用简体中文进行 README 的编写，除非项目明确要求使用英文。
- **代码与术语：** 所有代码实体（变量名、函数名、命令等）及技术术语必须保持英文原文。
- **标点规范：** 中文内容使用中文标点，代码块和技术术语周围使用英文标点。
- **语气规范：** 使用专业、友好、明确的语气，避免模糊和歧义表达。

#### 批判性审查原则
- **信息完整性检查：** 审视是否遗漏了读者可能需要的关键信息。
- **可操作性验证：** 确保所有步骤和命令都是可执行的，不存在断层。
- **逻辑连贯性：** 检查各章节之间的逻辑关系是否顺畅。

#### 内容深度要求
- **概述不空洞：** 项目介绍必须包含具体功能描述，而非泛泛而谈。
- **示例要丰富：** 每个主要功能都应配有代码示例和预期输出。
- **问题预判：** 预判用户可能遇到的问题，在 FAQ 或疑难解答中提前解答。

## README.md 标准结构

### 完整章节架构
```markdown
# 项目名称

> 一句话简介（简洁有力地描述项目核心价值）

![项目徽章区域]

## 📋 目录
[自动生成的目录导航]

## 🎯 项目简介
[详细的项目描述]

## ✨ 功能特性
[核心功能列表]

## 🖼️ 效果展示
[截图/GIF/演示视频]

## 🚀 快速开始
[最简安装和运行步骤]

## 📦 安装指南
[详细安装步骤]

## 💻 使用说明
[详细使用方法]

## 🏗️ 项目结构
[目录结构说明]

## ⚙️ 配置说明
[配置文件详解]

## 🔌 API 文档
[接口说明（如适用）]

## 🧪 测试指南
[测试方法]

## 📝 开发指南
[贡献代码指南]

## 🗺️ 路线图
[未来计划]

## ❓ 常见问题
[FAQ]

## 📄 更新日志
[版本历史]

## 🤝 贡献指南
[如何贡献]

## 📜 许可证
[许可证信息]

## 👥 作者与致谢
[贡献者信息]

## 📮 联系方式
[联系渠道]
```

## 各章节详细编写指南

### 1. 项目名称与徽章区域
```markdown
# 项目名称

> 用一句话概括项目的核心功能和价值主张

[![Build Status](https://img.shields.io/badge/build-passing-brightgreen)](链接)
[![Version](https://img.shields.io/badge/version-1.0.0-blue)](链接)
[![License](https://img.shields.io/badge/license-MIT-green)](链接)
[![Coverage](https://img.shields.io/badge/coverage-90%25-yellowgreen)](链接)
[![Stars](https://img.shields.io/github/stars/用户名/仓库名)](链接)
```

**徽章选择原则：**
- 必选徽章：构建状态、版本号、许可证
- 推荐徽章：测试覆盖率、下载量、最后更新时间
- 可选徽章：代码质量评分、依赖状态、贡献者数量

### 2. 项目简介章节
```markdown
## 🎯 项目简介

### 项目背景
[解释为什么创建这个项目，解决什么问题]

### 核心功能
[列出3-5个核心功能点]

### 技术栈
| 类别 | 技术 |
|------|------|
| 前端 | React 18, TypeScript 5.0, Vite 4 |
| 后端 | Node.js 20, Express 4.18 |
| 数据库 | PostgreSQL 15, Redis 7 |
| 部署 | Docker, Kubernetes |

### 为什么选择本项目
[与同类项目的对比优势，可用表格形式]
```

### 3. 功能特性章节
```markdown
## ✨ 功能特性

### 核心功能
- ✅ **功能一名称** - 功能详细描述
- ✅ **功能二名称** - 功能详细描述
- ✅ **功能三名称** - 功能详细描述

### 高级功能
- 🔧 **功能名称** - 功能描述
- 🔧 **功能名称** - 功能描述

### 即将推出
- 🚧 **功能名称** - 预计发布版本
- 🚧 **功能名称** - 预计发布版本
```

### 4. 效果展示章节
```markdown
## 🖼️ 效果展示

### 主界面
![主界面截图](./docs/images/main-screenshot.png)

### 功能演示
![功能演示GIF](./docs/images/demo.gif)

### 在线演示
🔗 [点击体验在线 Demo](https://demo.example.com)

### 视频教程
📺 [YouTube 教程](链接) | [Bilibili 教程](链接)
```

### 5. 快速开始章节
```markdown
## 🚀 快速开始

### 环境要求
- Node.js >= 18.0.0
- npm >= 9.0.0 或 yarn >= 1.22.0
- Git >= 2.40.0

### 30 秒快速体验
```bash
# 克隆项目
git clone https://github.com/用户名/项目名.git

# 进入目录
cd 项目名

# 安装依赖
npm install

# 启动项目
npm run dev
```

### 验证安装
访问 http://localhost:3000，看到欢迎页面即表示安装成功。
```

### 6. 安装指南章节
```markdown
## 📦 安装指南

### 方式一：npm 安装
```bash
npm install 包名
```

### 方式二：源码安装
```bash
# 1. 克隆仓库
git clone https://github.com/用户名/项目名.git
cd 项目名

# 2. 安装依赖
npm install

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入必要配置

# 4. 初始化数据库（如需要）
npm run db:migrate

# 5. 启动服务
npm run start
```

### 方式三：Docker 安装
```bash
# 使用 docker-compose
docker-compose up -d

# 或使用单独的 docker 命令
docker pull 镜像名:标签
docker run -d -p 3000:3000 镜像名:标签
```

### 系统特定说明

#### Windows
```powershell
# Windows 特定命令
```

#### macOS
```bash
# macOS 特定命令（如需要 Homebrew）
brew install 依赖名
```

#### Linux
```bash
# Linux 特定命令
sudo apt-get install 依赖名
```
```

### 7. 使用说明章节
```markdown
## 💻 使用说明

### 基础用法
```python
from 包名 import 模块

# 初始化
client = 模块.Client(api_key="your-key")

# 基本操作
result = client.操作方法(参数)
print(result)
```

### 高级用法

#### 场景一：批量处理
```python
# 详细的代码示例
# 包含完整的输入输出
```

#### 场景二：异步操作
```python
# 异步代码示例
```

### 配置选项
| 参数名 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `param1` | string | `""` | 参数说明 |
| `param2` | number | `100` | 参数说明 |
| `param3` | boolean | `false` | 参数说明 |

### 完整示例项目
📁 查看 [examples/](./examples/) 目录获取更多示例
```

### 8. 项目结构章节
```markdown
## 🏗️ 项目结构

```
项目名/
├── 📁 src/                    # 源代码目录
│   ├── 📁 components/         # 组件
│   │   ├── 📁 common/        # 通用组件
│   │   └── 📁 business/      # 业务组件
│   ├── 📁 pages/             # 页面
│   ├── 📁 services/          # 服务层
│   ├── 📁 utils/             # 工具函数
│   ├── 📁 hooks/             # 自定义 Hooks
│   ├── 📁 types/             # 类型定义
│   └── 📄 main.ts            # 入口文件
├── 📁 tests/                  # 测试文件
│   ├── 📁 unit/              # 单元测试
│   └── 📁 e2e/               # 端到端测试
├── 📁 docs/                   # 文档
├── 📁 scripts/                # 脚本
├── 📄 package.json           # 项目配置
├── 📄 tsconfig.json          # TypeScript 配置
├── 📄 .env.example           # 环境变量模板
└── 📄 README.md              # 项目说明
```

### 核心目录说明
| 目录 | 说明 |
|------|------|
| `src/components/` | 可复用的 UI 组件 |
| `src/services/` | API 调用和业务逻辑 |
| `src/utils/` | 工具函数和辅助方法 |
```

### 9. 配置说明章节
```markdown
## ⚙️ 配置说明

### 环境变量
在项目根目录创建 `.env` 文件：

```bash
# 服务器配置
PORT=3000
HOST=localhost

# 数据库配置
DB_HOST=localhost
DB_PORT=5432
DB_NAME=database_name
DB_USER=username
DB_PASSWORD=password

# API 密钥
API_KEY=your_api_key_here
SECRET_KEY=your_secret_key_here

# 功能开关
ENABLE_FEATURE_X=true
DEBUG_MODE=false
```

### 配置文件
```yaml
# config/default.yaml
server:
  port: 3000
  host: localhost
  
database:
  host: localhost
  port: 5432
  
logging:
  level: info
  format: json
```

### 配置优先级
1. 命令行参数（最高优先级）
2. 环境变量
3. `.env` 文件
4. 配置文件
5. 默认值（最低优先级）
```

### 10. API 文档章节
```markdown
## 🔌 API 文档

### 接口概览
| 方法 | 端点 | 说明 |
|------|------|------|
| GET | `/api/v1/users` | 获取用户列表 |
| POST | `/api/v1/users` | 创建用户 |
| GET | `/api/v1/users/:id` | 获取用户详情 |
| PUT | `/api/v1/users/:id` | 更新用户 |
| DELETE | `/api/v1/users/:id` | 删除用户 |

### 接口详情

#### 获取用户列表
```http
GET /api/v1/users?page=1&limit=10
Authorization: Bearer <token>
```

**请求参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| page | number | 否 | 页码，默认 1 |
| limit | number | 否 | 每页数量，默认 10 |

**响应示例：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [...],
    "total": 100,
    "page": 1,
    "limit": 10
  }
}
```

**错误码：**
| 错误码 | 说明 |
|--------|------|
| 400 | 请求参数错误 |
| 401 | 未授权 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

### 完整 API 文档
📚 [Swagger 文档](链接) | [Postman 集合](链接)
```

### 11. 测试指南章节
```markdown
## 🧪 测试指南

### 运行测试
```bash
# 运行所有测试
npm test

# 运行单元测试
npm run test:unit

# 运行端到端测试
npm run test:e2e

# 生成覆盖率报告
npm run test:coverage
```

### 测试覆盖率要求
| 类型 | 最低覆盖率 |
|------|-----------|
| 语句覆盖 | 80% |
| 分支覆盖 | 75% |
| 函数覆盖 | 85% |
| 行覆盖 | 80% |

### 编写测试
```javascript
describe('模块名', () => {
  beforeEach(() => {
    // 测试前准备
  });

  it('应该正确执行某功能', () => {
    // 测试代码
    expect(result).toBe(expected);
  });
});
```
```

### 12. 开发指南章节
```markdown
## 📝 开发指南

### 开发环境搭建
```bash
# 1. Fork 并克隆项目
git clone https://github.com/你的用户名/项目名.git

# 2. 添加上游仓库
git remote add upstream https://github.com/原作者/项目名.git

# 3. 安装开发依赖
npm install

# 4. 创建功能分支
git checkout -b feature/你的功能名
```

### 代码规范
- 使用 ESLint + Prettier 进行代码格式化
- 遵循项目既定的命名约定
- 提交前运行 `npm run lint` 检查

### 提交规范
采用 [Conventional Commits](https://conventionalcommits.org/) 规范：

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Type 类型：**
- `feat`: 新功能
- `fix`: Bug 修复
- `docs`: 文档更新
- `style`: 代码格式调整
- `refactor`: 重构
- `test`: 测试相关
- `chore`: 构建/工具相关

### 分支命名
- `feature/xxx`: 新功能
- `fix/xxx`: Bug 修复
- `docs/xxx`: 文档更新
- `refactor/xxx`: 重构
```

### 13. 路线图章节
```markdown
## 🗺️ 路线图

### 当前版本：v1.0.0
✅ 已完成的功能列表

### v1.1.0（计划中）
- [ ] 功能 A
- [ ] 功能 B
- [ ] 性能优化

### v2.0.0（规划中）
- [ ] 重大功能 C
- [ ] 架构升级

### 长期目标
- 目标 1
- 目标 2

📢 欢迎在 [Issues](链接) 中提出功能建议！
```

### 14. 常见问题章节
```markdown
## ❓ 常见问题

<details>
<summary><b>Q1: 安装时遇到权限错误怎么办？</b></summary>

**问题描述：** 运行 `npm install` 时报 EACCES 错误

**解决方案：**
```bash
# 方案一：使用 nvm 管理 Node.js
nvm install 18
nvm use 18

# 方案二：修改 npm 目录权限
mkdir ~/.npm-global
npm config set prefix '~/.npm-global'
```
</details>

<details>
<summary><b>Q2: 如何配置代理？</b></summary>

**解决方案：**
在 `.env` 文件中添加：
```bash
HTTP_PROXY=http://proxy.example.com:8080
HTTPS_PROXY=http://proxy.example.com:8080
```
</details>

<details>
<summary><b>Q3: 数据库连接失败？</b></summary>

**可能原因：**
1. 数据库服务未启动
2. 连接参数错误
3. 防火墙阻止

**排查步骤：**
```bash
# 检查数据库服务状态
systemctl status postgresql

# 测试连接
psql -h localhost -U username -d database
```
</details>

### 更多问题
- 📖 查看 [Wiki](链接) 获取更多帮助
- 💬 加入 [Discord 社区](链接) 讨论
- 🐛 在 [Issues](链接) 中报告问题
```

### 15. 更新日志章节
```markdown
## 📄 更新日志

### [1.2.0] - 2024-01-15
#### 新增
- 新功能 A
- 新功能 B

#### 变更
- 优化了 X 的性能
- 调整了 Y 的默认行为

#### 修复
- 修复了 Z 的崩溃问题

#### 废弃
- 废弃了旧的 API 方法

---

### [1.1.0] - 2024-01-01
...

📋 完整更新日志请查看 [CHANGELOG.md](./CHANGELOG.md)
```

### 16. 贡献指南章节
```markdown
## 🤝 贡献指南

我们欢迎所有形式的贡献！

### 如何贡献
1. **报告 Bug**：通过 [Issues](链接) 提交 Bug 报告
2. **功能建议**：在 [Discussions](链接) 中提出新想法
3. **代码贡献**：提交 Pull Request
4. **文档改进**：帮助完善文档
5. **社区支持**：回答其他用户的问题

### Pull Request 流程
1. Fork 本仓库
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

### 行为准则
请阅读我们的 [行为准则](./CODE_OF_CONDUCT.md)

### 贡献者名单
感谢所有贡献者！

<a href="https://github.com/用户名/仓库名/graphs/contributors">
  <img src="https://contrib.rocks/image?repo=用户名/仓库名" />
</a>
```

### 17. 许可证章节
```markdown
## 📜 许可证

本项目采用 [MIT 许可证](./LICENSE)。

```
MIT License

Copyright (c) 2024 作者名

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software...
```
```

### 18. 联系方式章节
```markdown
## 📮 联系方式

- **作者**：作者名
- **邮箱**：email@example.com
- **主页**：https://example.com
- **Twitter**：[@username](https://twitter.com/username)

### 技术支持
- 💬 [Discord 社区](链接)
- 📧 技术支持邮箱：support@example.com
- 🐛 [问题反馈](链接)

---

<p align="center">
  如果这个项目对你有帮助，请给一个 ⭐️ Star！
</p>
```

## 编写强制要求 ⚠️

1. **目录完整性**：必须包含可点击跳转的目录导航
2. **徽章区域**：必须包含项目状态徽章（构建状态、版本、许可证等）
3. **快速开始**：必须有能在 1 分钟内完成的快速体验步骤
4. **代码示例**：所有示例代码必须可直接复制运行
5. **跨平台支持**：安装说明必须覆盖 Windows、macOS、Linux 三大平台
6. **版本标注**：所有依赖项必须标明版本要求
7. **错误处理**：必须包含常见问题解答章节
8. **贡献指南**：必须说明如何贡献代码
9. **许可证声明**：必须明确项目的许可证类型
10. **联系方式**：必须提供有效的联系渠道

## 格式规范

### Markdown 语法要求
- 使用标准 Markdown 语法，确保在 GitHub/GitLab 上正确渲染
- 代码块必须指定语言类型
- 表格需要对齐
- 链接需要有效且使用相对路径（项目内资源）
- 图片需要提供 alt 文本

### Emoji 使用规范
| 用途 | 推荐 Emoji |
|------|-----------|
| 项目简介 | 🎯 |
| 功能特性 | ✨ |
| 快速开始 | 🚀 |
| 安装指南 | 📦 |
| 使用说明 | 💻 |
| 项目结构 | 🏗️ |
| 配置说明 | ⚙️ |
| API 文档 | 🔌 |
| 测试指南 | 🧪 |
| 开发指南 | 📝 |
| 路线图 | 🗺️ |
| 常见问题 | ❓ |
| 更新日志 | 📄 |
| 贡献指南 | 🤝 |
| 许可证 | 📜 |
| 联系方式 | 📮 |
| 警告/注意 | ⚠️ |
| 提示 | 💡 |

## 质量检查清单

### 发布前检查
- [ ] 所有链接都可正常访问
- [ ] 所有代码示例都已验证可运行
- [ ] 版本号和日期都是最新的
- [ ] 截图/GIF 都能正常显示
- [ ] 目录跳转链接正确
- [ ] 拼写和语法无误
- [ ] 排版整齐美观
- [ ] 在不同设备上阅读体验良好

## 注意事项

- README 是项目的门面，第一印象至关重要
- 定期更新 README，保持信息时效性
- 收集用户反馈，持续改进文档质量
- 考虑国际化需求，必要时提供多语言版本
- 利用 GitHub 的特殊文件支持（如 `.github/README.md`）
- 测试 README 在暗色模式下的显示效果
- 图片资源建议存放在专门的 `docs/images/` 目录
- 对于大型项目，考虑使用专门的文档网站

---

遵循本规范编写的 README.md 将具备完整性、专业性和易用性，能够有效帮助用户快速了解和使用项目。
```