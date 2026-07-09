# docs-src 编写规范

## 一、定位

`docs-src` 是项目文档镜像树，不是随意堆放说明文件的目录。

它的核心作用是：
- 镜像源码、测试、skill、模板和保留脚本结构
- 保存原项目中的 AGENTS/agents 文档镜像
- 为维护者提供按路径定位的文档入口
- 记录目录职责、边界、维护方式和已知误区

## 二、结构要求

### 必须尽量镜像的目录
- `src/`
- `tests/`
- `.agents/provider-guide/`
- `.scripts/`
- `template/`

### 每个重要目录至少具备
- 一个 `INDEX.md`
- 必要时的专题说明文档
- 如果原目录有 AGENTS/agents 文件且要求保留，则在 docs-src 中提供镜像副本

## 三、内容要求

1. 全部使用无 emoji Markdown。
2. 不允许只给出文件列表而不写用途。
3. 对复杂目录，要说明：
   - 目录职责
   - 关键入口文件
   - 常见误区
   - 维护建议
4. 对镜像 AGENTS 文档，要明确说明它们是镜像副本，而不是重新定义的新规则。

## 四、索引要求

### 根索引
`docs-src/INDEX.md` 必须至少导航到：
- docs-src 自身规范
- tests 规范
- src 核心目录
- 平台规范与平台合规矩阵
- WebUI 文档
- skill 索引
- rules 索引
- template 索引

### 子目录索引
每个子目录的 `INDEX.md` 至少说明：
- 该目录在真实项目中的来源路径
- 该目录主要职责
- 关键文件或子目录

## 五、镜像 AGENTS 规则

当前项目中，以下文档应作为镜像保留：
- `docs-src/AGENTS.md`
- `docs-src/src/AGENTS.md`
- `docs-src/src/platforms/AGENTS.md`
- `docs-src/.scripts/AGENTS.md`

这些文件的含义来自历史原文件，而不是 docs-src 自己重新发明的规则。

## 六、禁止事项

- 不要把 docs-src 写成会议纪要堆场。
- 不要用 README 风格宣传文本替代目录说明。
- 不要为了省事删掉历史规则镜像。
- 不要把 AGENTS 镜像文件误写成 docs-src 专属规则。
