#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# session-cleanup.py — Post-session review and update hook for Provider-V2
#
# Triggered on the `Stop` event (agent finishes a task).
# Reads session context from stdin, compares local tree against dev branch,
# and when actual (non-trivial) changes are detected, outputs a structured
# prompt for the agent to: review/update docs-src, tests, record.md, README.md,
# template, config.toml (auto +0.0.1 version), requirements.txt,
# .agents/provider-guide/, then stage, commit and push.
#
# If no real changes are detected, the hook exits silently with no prompt.
#
# Exit codes: 0 = success (prompt injected or no-op), other = warning

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def main() -> None:
    try:
        raw = sys.stdin.read()
        input_data = json.loads(raw)
    except Exception:
        print("session-cleanup: failed to parse stdin", file=sys.stderr)
        sys.exit(0)

    session_id: str = input_data.get("session_id", "unknown")
    cwd: str = input_data.get("cwd", ".")

    try:
        os.chdir(cwd)
    except Exception:
        print("session-cleanup: cannot chdir to " + cwd, file=sys.stderr)
        sys.exit(0)

    if not (Path("config.toml").is_file() or Path("src").is_dir()):
        print("session-cleanup: not a Provider-V2 project, skipping", file=sys.stderr)
        sys.exit(0)

    # Check if there are actual changes compared to dev branch
    diff_summary = _compare_to_dev()
    if not diff_summary:
        # No real changes — exit silently
        sys.exit(0)

    changed_files = _collect_changed_files()
    prompt = _build_prompt(session_id, diff_summary, changed_files)
    print(prompt)
    sys.exit(0)


def _run_git(args: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git"] + args, capture_output=True, text=True, timeout=15
        )
        return result.stdout
    except Exception:
        return ""


def _compare_to_dev() -> str | None:
    """Compare working tree against dev branch. Returns a diff summary if
    there are actual code-level changes, or None if only trivial differences
    (e.g. whitespace, comments, version-only bumps in config.toml)."""

    # Ensure we have a dev branch reference
    _run_git(["fetch", "origin", "dev"])

    # Get the local dev branch commit, or fallback to origin/dev
    dev_ref = _run_git(["rev-parse", "--verify", "dev"]).strip()
    if not dev_ref:
        dev_ref = _run_git(["rev-parse", "--verify", "origin/dev"]).strip()
    if not dev_ref:
        return None

    # Compare working tree (HEAD + unstaged) against dev
    # Use --stat to get a quick overview of changed files
    stat = _run_git(["diff", "--stat", dev_ref])
    if not stat.strip():
        # Also check untracked files
        untracked = _run_git(
            ["ls-files", "--others", "--exclude-standard"]
        ).strip()
        if not untracked:
            return None

    # Get the actual diff (code-level, ignoring whitespace-only changes)
    diff = _run_git(["diff", "-w", "--no-ext-diff", dev_ref])

    # Also include staged changes
    staged = _run_git(["diff", "--cached", "-w", "--no-ext-diff"])

    # Collect names of files with substantive changes
    diff_files = _run_git(["diff", "--name-only", "-w", dev_ref]).strip()
    staged_files = _run_git(
        ["diff", "--cached", "--name-only", "-w"]
    ).strip()
    untracked_files = _run_git(
        ["ls-files", "--others", "--exclude-standard"]
    ).strip()

    all_files = set()
    for blob in (diff_files, staged_files, untracked_files):
        for line in blob.splitlines():
            line = line.strip()
            if line:
                all_files.add(line)

    if not all_files:
        return None

    # Build a concise summary for the agent
    summary_lines = ["## Changes detected vs dev branch:"]
    for f in sorted(all_files):
        summary_lines.append("- " + f)
    summary_lines.append("")

    # Include a short diff context for the agent to understand the changes
    shortstat = _run_git(["diff", "--shortstat", dev_ref]).strip()
    if shortstat:
        summary_lines.append("Diff stats: " + shortstat)

    return "\n".join(summary_lines)


def _collect_changed_files() -> str:
    """Collect all changed/staged/untracked file paths."""
    lines: list[str] = []

    lines.extend(_run_git(["diff", "--cached", "--name-only"]).splitlines())
    lines.extend(_run_git(["diff", "--name-only"]).splitlines())
    lines.extend(
        _run_git(["ls-files", "--others", "--exclude-standard"]).splitlines()
    )

    cleaned = sorted({l.strip() for l in lines if l.strip()})
    return "\n".join(cleaned)


def _build_prompt(
    session_id: str, diff_summary: str, changed_files: str
) -> str:
    """Build the self-review prompt injected back into the conversation."""
    return f"""\
## Session End — Self-Review, Artifact Update, and Commit

Session ID: {session_id}

You have just finished a task in this Provider-V2 project. **Actual code changes have been detected compared to the dev branch.** Before the session ends, complete the following steps.

---

### Step 1: Compare and Understand Changes

{diff_summary}

Review the actual code changes above. Understand what was modified at the code level — do not focus on version number changes. Determine the real semantic changes (new features, bug fixes, refactoring, new platforms, config changes, etc.).

---

### Step 2: Update Project Artifacts (only where changed)

### 2.1 docs-src (documentation mirror)
- If you modified or added any source file under `src/`, `src/platforms/`, `src/core/`, `src/webui/`, or `src/routes/`, ensure the corresponding mirror documentation under `docs-src/` is updated.
- Add or update `INDEX.md` files for new directories.
- Follow `.agents/provider-guide/references/docs-tests-guide.md` and `.agents/provider-guide/references/rules/AGENTS_MD_GUIDE.md`.

### 2.2 tests (test mirror)
- If you added or changed platform adapters, core modules, or WebUI components, ensure corresponding tests exist under `tests/`.
- Each platform must have at least an MVP test.
- Run `pytest tests -q` and record results.

### 2.3 record.md (change log)
- **Append** a new section to `record.md` with:
  - Date (use current date)
  - Concise bullet points of meaningful changes
  - External blockers or skipped tests with reasons
  - Test results summary (passed/skipped counts)

### 2.4 README.md
- If new platforms, APIs, or features were added, update relevant sections.
- If project structure changed materially, update the tree diagram.

### 2.5 template/template_config.toml
- If `config.toml` gained new sections or keys, mirror them into the template.

### 2.6 config.toml — Auto version increment
- **Increment the `server.version` by 0.0.1** (e.g., `2.2.0` → `2.2.1`).
- Only do this because actual code changes were detected.

### 2.7 requirements.txt
- If new third-party Python packages were imported, add them with version constraints.

### 2.8 .agents/provider-guide/ (project skill)
- If platform interfaces, architecture, coding standards, or scripts changed, update the relevant reference docs under `.agents/provider-guide/references/`.
- Update `SKILL.md` sections if they are no longer accurate.

### 2.9 Verification
- Run `py_compile` on all modified Python files.
- Run `pytest tests -q` for a full regression.
- If scripts were changed, run the relevant scripts under `.agents/provider-guide/scripts/` and inspect outputs.
- Record all verification results (pass/fail/skip counts) in `record.md`.

---

### Step 3: Git Commit

After updating all artifacts:

1. Stage all changed files: `git add <files>`
2. Write a **meaningful commit message** based on the actual code changes — not the version bump. The version increment is incidental; the commit should describe the real work done.
   - Use Conventional Commits format: `type(scope): description`
   - Include a body with bullet points of what changed
3. Create the commit: `git commit -m "..." `

---

### Changed files in this session:
{changed_files}

**Important:** If after your review you determine that no substantive code changes were made (e.g., only whitespace, comments, or documentation tweaks), skip all steps above and do not create a commit.
"""


if __name__ == "__main__":
    main()
