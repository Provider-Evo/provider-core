#!/bin/bash
# session-cleanup.sh — Post-session review and update hook for Provider-V2
#
# Triggered on the `Stop` event (agent finishes a task).
# Reads session context from stdin, determines what changed,
# and outputs a structured prompt for the agent to self-review
# and update: docs-src, tests, record.md, README.md, template,
# config.toml, requirements.txt.
#
# Exit codes: 0 = success (prompt injected), other = warning

set -euo pipefail

# Use Python for JSON parsing (more portable than jq)
python3 -c "
import json, sys, os, subprocess

try:
    input_data = json.loads(sys.stdin.read())
except Exception:
    print('session-cleanup: failed to parse stdin', file=sys.stderr)
    sys.exit(0)

session_id = input_data.get('session_id', 'unknown')
cwd = input_data.get('cwd', '.')

# Change to project root
try:
    os.chdir(cwd)
except Exception:
    print('session-cleanup: cannot chdir to ' + cwd, file=sys.stderr)
    sys.exit(0)

# Sanity check: is this a Provider-V2 project?
if not (os.path.isfile('config.toml') or os.path.isdir('src')):
    print('session-cleanup: not a Provider-V2 project, skipping', file=sys.stderr)
    sys.exit(0)

# Collect changed files from git
changed_files = ''
try:
    # Staged changes
    result = subprocess.run(['git', 'diff', '--cached', '--name-only'],
                          capture_output=True, text=True, timeout=10)
    changed_files += result.stdout

    # Unstaged changes
    result = subprocess.run(['git', 'diff', '--name-only'],
                          capture_output=True, text=True, timeout=10)
    changed_files += result.stdout

    # Untracked files
    result = subprocess.run(['git', 'ls-files', '--others', '--exclude-standard'],
                          capture_output=True, text=True, timeout=10)
    changed_files += result.stdout

    # Deduplicate
    lines = [l.strip() for l in changed_files.split('\n') if l.strip()]
    changed_files = '\n'.join(sorted(set(lines)))
except Exception:
    changed_files = ''

if not changed_files:
    changed_files = '(No git repo or no tracked changes)'

# Build the review prompt
prompt = '''## Session End — Self-Review and Project Update

Session ID: {session_id}

You have just finished a task in this Provider-V2 project. Before the session ends, review what you did and update the following project artifacts if needed.

### 1. docs-src (documentation mirror)
- If you modified or added any source file under \`src/\`, \`src/platforms/\`, \`src/core/\`, \`src/webui/\`, or \`src/routes/\`, ensure the corresponding mirror documentation under \`docs-src/\` is updated to reflect the current structure and behavior.
- Add or update \`INDEX.md\` files for any new directories.
- Follow the rules in \`.agents/provider-guide/references/docs-tests-guide.md\` and \`.agents/provider-guide/references/rules/AGENTS_MD_GUIDE.md\`.
- Mirror AGENTS.md files must stay in sync if their sources changed.

### 2. tests (test mirror)
- If you added or changed platform adapters, core modules, or WebUI components, ensure corresponding tests exist under \`tests/\`.
- Each platform must have at least an MVP test that verifies: importability, Adapter availability, name/supported_models/default_capabilities accessibility.
- New test files must be reflected in \`docs-src/tests/\` mirror.
- Run \`pytest tests -q\` to verify tests pass, then update the result summary.

### 3. record.md (change log)
- Append a new section to \`record.md\` summarizing what was done in this session:
  - Date (use current date)
  - Concise bullet points of meaningful changes
  - Any external blockers or skipped tests with reasons
  - Test results summary (passed/skipped counts)
  - Packaging status if applicable

### 4. README.md
- If new platforms were added, update the platform list and badges.
- If new features were added (APIs, WebUI pages, config options), update the feature table and documentation.
- If the project structure changed materially, update the tree diagram.
- Keep the changelog/roadmap section current.

### 5. template/config.toml
- If \`config.toml\` gained new sections, keys, or defaults, mirror them into \`template/template_config.toml\` (with sensible placeholder values and comments).

### 6. config.toml
- If your changes introduced new configuration keys, ensure the active \`config.toml\` has them (or document that defaults apply).

### 7. requirements.txt
- If you imported any new third-party Python packages, add them to \`requirements.txt\` with an appropriate version constraint.

### 8. Verification
- If any code was changed, run \`py_compile\` on modified files and \`pytest tests -q\` for a full regression.
- If scripts were changed, run the relevant scripts and inspect outputs.
- Record all verification results in \`record.md\`.

### Changed files in this session:
{changed_files}

Now review your changes and update the above artifacts accordingly. If nothing in a category changed, skip it — do not make cosmetic-only edits.'''.format(session_id=session_id, changed_files=changed_files)

print(prompt)
sys.exit(0)
"
