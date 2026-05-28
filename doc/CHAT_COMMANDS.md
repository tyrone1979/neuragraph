# Chat Command Spec and Test Guide

## Scope

This document describes the unified command behavior for:

- Floating UI assistant (`/chat/api/message`)
- Terminal chat (`chat.py`)

Both now use the same shared command core:

- `service/chat/commands.py`

## Command Contract

### Context and Preview

- `/pin show|clear|graph <id>|exp <id>|dataset <file>`
- `/dryrun <slash_command>`

### CRUD and Execution

- `/list workflows|agents|tools|datasets|llms|experiments`
- `/show workflow|agent|tool|dataset|llm|experiment <id>`
- `/create testset <runner_id> <filename> [source_file] [count]`
- `/create experiment [runner_id] [dataset] [runner_type]`
- `/run workflow|agent <id> {json_inputs}`
- `/run experiment <exp_id>`
- `/copy workflow <source_id> <target_id>`
- `/optimize <exp_id> [max_updates]`
- `/orchestrate <goal>`
- `/delete workflow|agent|tool|llm|experiment <id>`

### Output Style

- Command outputs are markdown cards or concise markdown text from shared layer.
- Terminal and UI assistant should show equivalent content for the same command.

## Architecture

### Shared Layer

- `service/chat/commands.py`
  - Parses and executes slash commands
  - Keeps session pins
  - Returns normalized markdown responses
  - Runs end-to-end orchestration (`/orchestrate`) for generate -> run -> report -> compare

### UI Entry

- `ui/chat_api.py`
  - Session management (`session_id`)
  - Delegates slash and intent actions to shared command functions

### Terminal Entry

- `chat.py`
  - Delegates non-interactive command set to shared command functions
  - Keeps local interactive workflow/agent run path for manual input mode

## Regression Test Suites

### Python suites

- `tests/test_chat_feature_suite.py`
  - Pin and dry-run
  - List/show/delete/copy/create/optimize/orchestrate command flows
- `tests/test_report_regression_suite.py`
  - Report prompt anti-hardcode constraints
  - Inline chart layout contract

### One-click batch runner

- `test_chat_suite.bat`

## How to Run

From workspace root:

- `test_chat_suite.bat`

Or manual:

- `set PYTHONPATH=%CD%`
- `py -3 tests/test_chat_feature_suite.py`
- `py -3 tests/test_report_regression_suite.py`

## Acceptance Checklist

- Same slash command gives same semantic output in terminal and UI assistant.
- `/create experiment` works with pinned defaults.
- `/dryrun` never mutates state.
- Report page renders charts inline with related sections (no overflow).
- Report prompt rules explicitly disallow hardcoded keyword/sample special handling.
