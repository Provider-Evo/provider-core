# template 索引

模板目录存放配置模板，版本更新时应与 `config.toml` 字段保持一致。

## 文件

- `template_config.toml` — `config/main_config.toml` 模板，与 `config_panel_schema` 及 `sections.py` 对齐
- `template_webui_config.toml` — `config/webui_config.toml` 模板，与 `WEBUI_CONFIG_PANEL_SCHEMA` 对齐

版本号 `[server].version` 与 `pyproject.toml` 一致，供打包脚本 `gen_selfzip` / `gen_snapshot` 读取。
