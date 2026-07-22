# Provider-Evo

> 统一 AI 模型网关：通过插件适配各上游平台，对外提供 OpenAI / Anthropic 兼容 API

<div align="center">

![Version](https://img.shields.io/badge/version-2.2.316-blue)
![Python](https://img.shields.io/badge/python-3.8+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

[![GitHub](https://img.shields.io/github/stars/Provider-Evo/provider-core)](https://github.com/Provider-Evo/provider-core)

</div>

**provider-core** 是 Provider-Evo 的运行时网关（独立 git 仓库）。插件源码在 [provider-plugin](https://github.com/Provider-Evo) 工作区的各 `Provider-*` 目录；`plugins/` 为 overlay 部署副本，不在此改业务逻辑。

| 分支 | 说明 |
|------|------|
| **dev** | 活跃开发，日常提交与 PR 目标 |
| **main** | 稳定发布，经审核后从 dev 合并 |
| **classical** | 重构前冻结快照，只读参考 |

日常开发请基于 **dev**；禁止未经确认直推 **main**。

---

## 功能概览

| 能力 | 说明 |
|------|------|
| 插件化平台 | 29 个内置插件（adapter / util），WebUI 面板安装、启用、配置 |
| API 兼容 | OpenAI（`/v1/chat/completions` 等）与 Anthropic（`/v1/messages`） |
| 网关调度 | 并发竞速、TAS 候选项选择、模型映射 |
| 工具调用 | 多协议 fncall（xml / antml / nous / dsml 等），模板可配置 |
| 内置 WebUI | 聊天、终端、文件、统计、配置、插件市场 |
| 热重载 | 配置与插件代码变更后自动重载（`fast_restart`） |

---

## 快速开始

### 环境

- Python 3.8+（推荐 3.10+）
- Windows / Linux / macOS

### 安装与启动

```bash
git clone https://github.com/Provider-Evo/provider-core.git
cd provider-core
pip install -r requirements.txt

# 首次启动会由 template/template_config.toml 生成本地 config/main_config.toml（config/ 不提交）
python main.py
```

默认监听 `http://127.0.0.1:1337/`。健康检查：`GET /health`。

浏览器打开 `/` 进入 WebUI；侧栏「插件」面板可管理适配器。

### Docker

```bash
docker compose up -d --build
```

挂载 `config/`、`plugins/`、`persist/` 以保留配置与状态（见 `docker-compose.yml`）。

---

## 项目结构

```
provider-core/
├── config/              # 本地运行时配置（gitignore，不提交；由 template 生成 main_config.toml）
├── template/            # 配置模板 template_config.toml
├── plugins/             # 插件部署副本（overlay，非开发入口）
├── persist/             # 账号状态、WebUI、网关统计等持久化
├── src/
│   ├── bootstrap/       # 应用组合根
│   ├── core/            # 网关、配置、分发、鉴权、热重载
│   ├── foundation/      # 日志、路径等基础模块
│   ├── routes/          # OpenAI / Anthropic / 健康检查路由
│   └── webui/           # 内置 WebUI（前后端）
├── main.py              # Runner-Worker 入口
├── pyproject.toml       # 依赖与版本 SSOT
└── requirements.txt     # 与 pyproject 同步的锁定依赖
```

编排工作区其他目录：`provider-plugin/`（插件真源）、`plugin-repo/`（市场索引）、`provider-docs/`（用户文档站）。

---

## 配置

- **本地运行时**：`config/main_config.toml`（不存在时从 `template/template_config.toml` 生成；`config/` 整目录 **gitignore，不提交**）
- **可提交模板**：`template/template_config.toml`（版本号与 `pyproject.toml` 同步）
- 不使用 `.env` 作为主配置
- 修改 `[proxy]` 后需重启；其余段支持热重载

配置项说明与示例见 [官方文档 · 快速开始](https://provider-evo.github.io/docs/manual/quickstart/)。

---

## API 端点（常用）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/v1/models` | 模型列表 |
| POST | `/v1/chat/completions` | OpenAI 聊天 |
| POST | `/v1/messages` | Anthropic 消息 |

完整路由与能力矩阵见 WebUI「模型」面板或 [文档站](https://provider-evo.github.io/docs/)。

---

## 开发与测试

```bash
# 结构健康度门禁
python achecker.py

# 测试（工作区根目录 tests/）
pytest tests/provider-core/

# 注释套话合规
python scripts/provider-core/strip_comment_boilerplate.py --verify
```

- 编码规范：`AGENTS.md`
- 工作流与插件修改：`docs-src/provider-guide-references/agents-project-conventions.md`（编排仓内）
- 插件开发：[文档 · 插件](https://provider-evo.github.io/docs/plugins/)
- 贡献：Fork → 基于 **dev** 建分支 → PR 到 **dev**

---

## 相关仓库

| 仓库 | 说明 |
|------|------|
| [Provider-Evo/provider-core](https://github.com/Provider-Evo/provider-core) | 本仓库（运行时） |
| [Provider-Evo/docs](https://github.com/Provider-Evo/docs) | 用户文档站 |
| [Provider-Evo/plugin-repo](https://github.com/Provider-Evo/plugin-repo) | 插件市场索引 |

---

## 变更日志

见 [CHANGELOG.md](./CHANGELOG.md)。里程碑摘要见 [文档 · 发版](https://provider-evo.github.io/docs/release/)。

## 许可证

[MIT](./LICENSE)

---

## 联系

- 作者：nightpoem
- Issues：<https://github.com/Provider-Evo/provider-core/issues>
- 邮箱：nichengfuben@outlook.com
