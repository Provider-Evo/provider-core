---
name: provider-guide
description: This skill should be used when the user works on Provider-V2 and needs the full local project rule set, platform adapter conventions, docs-src or tests mirror guidance, script generation and packaging workflows, WebUI maintenance rules, persistent state changes, startup behavior checks, or a compliance review against the migrated legacy standards.
version: 2.2.247
---

# Provider Guide

This skill is the single authoritative project skill for Provider-V2.

It replaces the old `.agents/rules/` and most of `.scripts/`, but it must not lose their content. Historical rules have been migrated into `references/rules/` and should be treated as first-class reference material, not optional leftovers.

## When this skill must be used

Use this skill whenever work touches any of the following:

- `src/core/`, `src/routes/`, `src/platforms/`, `src/webui/`
- `docs-src/` mirrored documentation
- `tests/` mirrored test structure
- project packaging and snapshot generation
- script generation under `logs/scriptgen/`
- platform contract checks and compliance reviews
- persistence logic, startup logic, port handling, proxy switching
- the built-in WebUI served at the root path `/`

## Hard requirements

1. Do not drop legacy rules just because a new skill structure exists.
2. Update `RECORD.md` locally for every meaningful change and every external blocker. **必须以追加方式更新**（在文件末尾添加新的时间戳+描述块），**禁止覆盖或重写整个文件**。`RECORD.md` 是 gitignored，永远不要提交它。
3. Keep `PLAN.txt` updated when task understanding materially changes.
4. Prefer reuse from `src/core/` over duplicating logic in scripts or platforms.
5. Preserve old script behavior where it is meaningful, then layer new path/output rules on top.
6. Treat `docs-src` as a mirrored documentation tree, not as an unrelated docs playground.
7. Treat mirrored `AGENTS.md` files in `docs-src` as preserved project knowledge, not docs-src-only rules.

## Version management

When any meaningful change is made, the agent **must** handle version numbers correctly:

1. **Single source of truth**: `config.toml` → `server.version` is the authoritative version.
2. **Increment by 0.0.1 only**: Each commit with substantive changes bumps the patch by exactly `0.0.1` (e.g. `2.1.2` → `2.1.3`). Never jump multiple minor versions unless the user explicitly says so.
3. **Sync all version references** after bumping `config.toml`:
   - `template/template_config.toml` — update `server.version`
   - `README.md` — update both badges (status + version) and the roadmap "当前版本" heading
   - `.agents/provider-guide/SKILL.md` — update the `version` field in frontmatter
   - **Hardcoded version strings in code** (e.g. route responses) — do **not** update the number; instead refactor them to read from `get_config().server.version`
4. **Check before changing**: before touching any version, `grep` the codebase for the current version string to find all places that need updating.
5. **Never hardcode versions** in new code — always read from config.

## Required reading order

### For any Python or architecture change
1. `references/code-guide.md`
2. `references/rules/CODE_GUIDE.txt`
3. `references/platform-guide.md` if any platform is involved

### For docs-src or tests work
1. `references/docs-tests-guide.md`
2. `references/rules/AGENTS_MD_GUIDE.md`
3. `references/rules/README_GUIDE.md` when touching README-like structure

### For WebUI changes
1. `references/webui-guide.md`
2. `references/rules/Frontend/CLAUDE.md`
3. `references/rules/Frontend/STYLE-DETAIL.txt`

### For script changes
1. `references/scriptgen-guide.md`
2. `references/script-agents.md`
3. relevant historical script under `scripts/` or migrated rule in `references/rules/`

## Directory map

### Main references
- `references/code-guide.md` - current project coding, runtime, and reuse rules
- `references/platform-guide.md` - platform structure rules plus current compliance matrix
- `references/docs-tests-guide.md` - mirrored docs-src and tests rules
- `references/scriptgen-guide.md` - script output, naming, cleanup, and preserved legacy behavior
- `references/webui-guide.md` - production-facing expectations for the built-in WebUI
- `references/script-agents.md` - migrated intent from old `.scripts/AGENTS.md`

### Migrated complete legacy rule set
- `references/rules/INDEX.md`
- `references/rules/CODE_GUIDE.txt`
- `references/rules/AGENTS_MD_GUIDE.md`
- `references/rules/README_GUIDE.md`
- `references/rules/REVERSE_GUIDE.md`
- `references/rules/SYSTEMINFO.md`
- `references/rules/Frontend/CLAUDE.md`
- `references/rules/Frontend/STYLE-DETAIL.txt`
- plus all other legacy language/domain rule files under `references/rules/`

### Deterministic maintenance scripts
- `scripts/gen_dir.py`
- `scripts/gen_merger.py`
- `scripts/gen_spilt.py`
- `scripts/gen_accounts.py`
- `scripts/gen_platforms.py`
- `scripts/gen_snapshot.py`
- `scripts/gen_selfzip.py`
- `scripts/gen_wenshushu.py`
- `scripts/_legacy_gen_wenshushu.py`
- `scripts/_zip_common.py`
- `scripts/common.py`

## Script output rules

### Output locations
- merged text -> `logs/scriptgen/`
- directory trees -> `logs/scriptgen/`
- split parts -> `logs/scriptgen/spilt/`
- instruction prompt for split continuation -> `logs/scriptgen/spilt/instruction.txt`
- snapshot zip -> project root
- self zip -> project root
- `warp.py` remains in `.scripts/`

### Naming rules
- merged text: `upload_<uuidv7>.txt`
- directory tree: `dir_<uuidv7>.txt`
- split parts: `upload1.txt`, `upload2.txt`, `upload3.txt`
- split instruction file: `instruction.txt`
- snapshot: `provider-{version}.zip`
- self zip: `provider-{version}-self.zip`

### Preserved legacy split behavior
- default `max_chars` remains `119913`
- part wrappers remain `--- PART x/y START ---` and matching END markers
- the three continuation prompt lines are now stored only in `instruction.txt`
- before generating new split output, old `upload{n}.txt` files under `logs/scriptgen/spilt/` must be deleted, while `instruction.txt` is preserved and overwritten separately

## Verification checklist

### Code verification
- import all changed modules
- run `py_compile` on changed Python files
- run relevant pytest subsets
- run full `pytest tests -q` after significant structural changes

### Runtime verification
- if startup logic changed, simulate port occupation and verify auto-release behavior
- if WebUI changed, actually start the service and request `/`
- if summary endpoints changed, request `/v1/webui/summary`

### Script verification
When any script changes, run the script itself and inspect its outputs:
- `gen_dir.py`
- `gen_merger.py`
- `gen_spilt.py`
- `gen_snapshot.py`
- `gen_selfzip.py`
- `gen_accounts.py` in validate mode unless explicit conversion is intended

## Script usage rules

1. **Always use gen_merger.py for merging**: When the user asks to merge files (whether a directory or explicit file list), always use `gen_merger.py`. Do NOT write manual one-off merges.
2. **When user provides explicit file list**: Pass the exact file paths to `gen_merger.py` using `--files` argument. Example: `python gen_merger.py --files file1.ts file2.ts file3.ts --verbose`
3. **When user provides a directory**: Run `gen_merger.py` on that directory to merge all files within it.
4. **Never override default output naming unless user explicitly asks**: The default output is `logs/scriptgen/upload_<uuidv7>.txt`. Do NOT use `-o` to override this unless the user explicitly requests a specific filename. Using `-o upload.txt` by default is a mistake.
5. **Dry run first**: For any script that produces output, run with `--dry-run` or equivalent first to confirm what will be processed.
6. **Confirm output location**: Only if the user says "输出到 upload.txt" or similar, then use `-o` to specify the filename.

## Failure-driven skill auto-update principle

When the agent makes a mistake that violates user expectations or project conventions:

1. **Identify the root cause**: What rule, assumption, or missing instruction led to the error?
2. **Update the skill immediately**: Add or modify rules in `SKILL.md` (or relevant reference files) to prevent the same mistake. Treat the skill as a living document that evolves from real errors.
3. **Be specific, not vague**: Write actionable rules with concrete examples. E.g., "Always use gen_merger.py for merging — when user lists files, pass them as arguments to gen_merger.py, do not write manual one-off merges."
4. **Preserve existing rules**: Never delete historical rules to add new ones. Append or refine.
5. **Record locally in RECORD.md**: Log the error, its cause, and the skill update in `RECORD.md` (gitignored, never commit) for traceability.
6. **Version bump**: If the skill update is substantive, increment the version in frontmatter by 0.0.1 per the version management rules.

## Failure handling

- If a third-party API, remote auth, quota, or network environment blocks a platform test, record the exact reason in `RECORD.md` (gitignored) and continue.
- If a verification command mutates production-like files unexpectedly, restore immediately and record the incident in `RECORD.md` (gitignored).
- If a rule appears to conflict with current repo structure, preserve the historical rule in references and add a project-specific clarification rather than deleting it.
