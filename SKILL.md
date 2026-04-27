---
name: delete-codex-local-session
description: List, inspect, or delete one or many local Codex sessions/threads. Use when Codex needs to enumerate local session IDs and titles, show a local conversation/session list, find local files for session IDs, preview local deletion, batch-delete provided local session IDs, or clean a local thread from transcript files, session indexes, SQLite state, logs, and generated-images folders under `CODEX_HOME` or `~/.codex`. This skill is for local-only Codex cleanup, not cloud/account chat deletion.
---

# Delete Codex Local Session

Use the bundled scripts to list local sessions or delete sessions by ID.

## Workflow

1. Confirm the user wants to work with local Codex session storage, not a cloud/account chat.
2. When the user needs to find session IDs first, list them by folder:

```powershell
python scripts/list_codex_sessions_by_folder.py
```

3. If the user says "conversation list", "session list", "conversation ID list", or similar, default to returning the listing script's output as-is. Do not collapse it to bare IDs or reformat it into an ID-only list unless the user explicitly asks for IDs only.
4. Add `--show-paths` when the user also wants rollout file paths.
5. Add `--include-missing` when the user wants DB rows whose rollout file is already missing.
6. When the user wants to inspect, preview, or verify one or more sessions, run the deletion script without `--apply`:

```powershell
python scripts/delete_codex_local_session.py <session-id> [<session-id> ...]
```

7. If the user gives multiple exact session IDs and explicitly asks to delete/remove/clean them, treat that as deletion approval. Run one batch command; do not preview each ID separately and do not ask for another confirmation.

```powershell
python scripts/delete_codex_local_session.py <session-id> [<session-id> ...] --apply --vacuum
```

8. For large exact-ID batches, add `--quiet` to the apply command to avoid per-ID output:

```powershell
python scripts/delete_codex_local_session.py <session-id> [<session-id> ...] --apply --vacuum --quiet
```

9. If IDs are inferred from a filter such as archived sessions or sessions before a date, preview the inferred batch once, summarize the count and IDs, then ask for one confirmation before applying the same batch command.
10. Include `--vacuum` by default for Codex chat deletion requests so SQLite files are compacted after deletion.
11. Omit `--vacuum` only when the user explicitly asks to delete without compaction.
12. Add `--keep-global-state` only when the user explicitly wants `.codex-global-state.json` left untouched.
13. Do not run a post-delete verification scan by default. Trust the deletion script's exit status and final summary. Verify afterward only if the user asks, the script reports an error, or the result is ambiguous.

## Listing Script Output

- Groups sessions by their actual parent folders such as `sessions/2026/04/18`
- Shows `session_id | title`
- Marks archived sessions with `| archived`
- Can also mark DB-only rows with `| missing` when `--include-missing` is used
- Treat requests like "give me the conversation ID list" as a request for the listing script's native output, unless the user explicitly asks for IDs only

## Batch Deletion Output

- Passing multiple IDs to `delete_codex_local_session.py` uses compact output by default.
- Add `--quiet` for exact-ID batch deletion when a count summary is enough.
- Add `--verbose` only when the user explicitly needs full paths and per-database details.
- Prefer one command containing all IDs over loops that call the script once per ID.

## What The Script Removes

- Matching rollout transcript files under `sessions/` and `archived_sessions/`
- Matching `session_index.jsonl` entries
- Matching rows in `state*.sqlite` from `threads`, `stage1_outputs`, `thread_dynamic_tools`, and `thread_spawn_edges`
- Matching `agent_job_items.assigned_thread_id` references in `state*.sqlite` are cleared to `NULL`
- Matching rows in `logs*.sqlite`
- Matching `generated_images/<session-id>/` directories
- Exact-key and exact-value references to the session ID inside `.codex-global-state.json`

## Safety Notes

- Default to listing or preview mode unless the user explicitly wants deletion.
- A request like "delete these IDs" with exact session IDs is already explicit deletion intent; do not add another confirmation turn.
- Tell the user to close the Codex app first when possible, because the UI may cache stale state.
- If the deleted thread still appears in the Codex app, tell the user to minimize the app to the taskbar and restore it first, because that often triggers a sidebar refresh.
- Tell the user that a restart may still be needed after deletion if minimizing and restoring the window does not refresh the UI.
- Do not claim that this skill deletes cloud/account history. It only cleans up local Codex storage.
