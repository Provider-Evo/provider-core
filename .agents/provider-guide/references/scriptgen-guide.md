# Scriptgen 输出规则

## 输出目录

- 文本合并输出目录：`logs/scriptgen/`
- 文本切分输出目录：`logs/scriptgen/spilt/`
- 目录树输出目录：`logs/scriptgen/`
- 快照 zip 与 self zip 输出目录：项目根目录

## 命名规则

- 合并输出：`upload_<uuidv7>.txt`
- 目录树输出：`dir_<uuidv7>.txt`
- 切分输出：`upload1.txt`、`upload2.txt`、`upload3.txt`
- self zip：`provider-{version}-self.zip`
- snapshot zip：`provider-{version}.zip`

## 保留的旧逻辑

- `gen_spilt.py` 默认最大字符数继续保持 `119913`。
- `gen_spilt.py` 保留旧分段提示文本逻辑，但通过 `--stdout-mode legacy` 显式启用。
- `gen_spilt.py` 默认标准输出为生成文件路径，同时始终写入 `logs/scriptgen/spilt/upload{n}.txt`。
- `upload{n}.txt` 默认保留旧版 `PART n/total` 包装提示；仅在 `--raw-files` 模式下写入纯片段内容。
- 截断提示语不再混入最后一个 upload 分片，而是固定写入 `logs/scriptgen/spilt/instruction.txt`。
- `gen_merger.py` 保留旧版的编码回退、文本文件识别、统计输出思路。
- `gen_dir.py` 保留旧版的统计分析思路，并改为默认输出到 `logs/scriptgen/`。
- `gen_accounts.py` 保留旧版的 AST 双向转换逻辑。

## 过滤规则

- 是否包含隐藏文件由脚本参数决定，不能写死在注释中。
- 默认排除日志、缓存、压缩包自身、解释器缓存目录以及脚本自身。
- 文本合并只处理文本文件，非文本文件跳过并记录统计信息。

## 复用规则

- UUIDv7 统一调用 `src.core.ids.uuid7()`。
- 原子写统一调用 `src.core.io_utils.atomic_write_text()`。
- 文本切分优先复用 `src.core.scriptgen.split_text()`；当需要完全保留旧行为时，允许直接按字符数截断。
