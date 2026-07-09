# 平台逐项合规矩阵

下表记录按当前平台规范扫描得到的结果。

| 平台 | util future 导入次数 | Adapter 通用门面 | core 命名偏差 |
|---|---:|---|---|
| aitianhu2 | 1 | 是 | core/constants.py、core/persistence.py |
| apiairforce | 1 | 是 | 无 |
| caiyuesbk | 1 | 是 | 无 |
| cerebras | 1 | 否 | 无 |
| chatmoe | 1 | 是 | 无 |
| chutes | 1 | 是 | 无 |
| codebuddy | 1 | 是 | 无 |
| cursor | 1 | 是 | core/constants.py、core/conversation.py |
| deepseek | 1 | 是 | core/constants.py |
| edgetts | 1 | 是 | core/constants.py |
| gtts | 1 | 是 | core/constants.py |
| n1n | 1 | 是 | 无 |
| nvidia | 1 | 是 | 无 |
| ollama | 1 | 是 | core/constants.py |
| openaifm | 1 | 是 | 无 |
| openrouter | 1 | 是 | core/constants.py |
| perplexity | 1 | 是 | core/constants.py |
| qwen | 1 | 是 | core/constants.py、core/endpoints.py、core/persistence.py |

## 结论

- 顶层目录结构全部满足统一形态。
- 本次已修复会导致导入失败的 future import 重复问题与 Adapter 门面问题。
- 仍保留的主要合规债务集中在部分 core 文件名长度超出建议值，例如 constants.py、endpoints.py、persistence.py、conversation.py。
- 这些命名问题目前不会直接阻断运行，但在后续平台深度整理时应继续收敛。
