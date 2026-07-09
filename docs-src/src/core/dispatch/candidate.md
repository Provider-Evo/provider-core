# src/core/dispatch/candidate.py

该模块定义候选项数据结构，用于表示 AI 平台的能力和状态。

## 概述

`Candidate` 类是一个数据类，包含平台候选项的所有能力布尔字段和元数据。每个候选项代表一个可处理请求的 AI 平台实例。

## 导出接口

- `Candidate`：候选项数据类
- `make_id`：生成候选项 ID 的辅助函数
- `ALL_CAPABILITIES`：所有支持的能力元组

## 核心组件

### Candidate 数据类

包含以下字段：

**核心能力**：
- `chat`：文本聊天
- `vision`：视觉理解
- `tools`：工具调用
- `native_tools`：原生工具
- `thinking`：思考模式
- `search`：搜索功能
- `continuation`：对话延续

**生成能力**：
- `image_gen`：图片生成
- `image_edit`：图片编辑
- `image_variation`：图片变体
- `video_gen`：视频生成
- `audio_gen`：音频生成

**音频输入**：
- `audio_in`：音频输入
- `audio_transcription`：音频转录
- `audio_translation`：音频翻译

**其他能力**：
- `embedding`：向量嵌入
- `rerank`：重排序
- `research`：研究功能
- `code_exec`：代码执行
- `artifacts`：工件生成
- `moderation`：内容审核
- `responses`：响应生成
- `upload`：文件上传
- `files`：文件管理
- `vector_stores`：向量存储
- `batch`：批处理
- `fine_tuning`：微调
- `assistants`：助手 API
- `threads`：线程管理
- `runs`：运行管理
- `realtime`：实时功能

**元数据**：
- `context_length`：上下文长度（可选）
- `models`：支持的模型列表
- `available`：是否可用
- `busy`：是否忙碌
- `cooldown`：冷却时间
- `meta`：额外元数据字典

### make_id 函数

生成候选项 ID，支持两种模式：
1. 确定性 ID：提供 `resource_id` 时，使用 SHA256 哈希生成
2. 随机 ID：未提供 `resource_id` 时，使用 UUID 生成

格式：`{platform}_{hash12}`

### ALL_CAPABILITIES 元组

包含所有支持的能力名称，用于遍历和验证。

## 依赖关系

- **标准库**：`hashlib`, `time`, `uuid`, `dataclasses`, `typing`
- **被依赖**：`src/core/dispatch/gateway.py`, `src/core/dispatch/selector.py`

## 使用场景

- 网关路由决策
- 候选项评分和选择
- 模型列表 API 响应
- 平台能力查询