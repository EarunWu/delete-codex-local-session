---
name: delete-codex-local-session
description: List, inspect, or delete a local Codex session/thread. Use when Codex needs to enumerate local session IDs and titles, group sessions by folders under `CODEX_HOME` or `~/.codex`, find which local files belong to a session, preview what would be removed, or safely delete a local thread from transcript files, session indexes, SQLite state, logs, and generated-images folders. This skill is for local-only Codex cleanup, not cloud/account chat deletion.
---

# Delete Codex Local Session

Use the bundled scripts to list local sessions or delete one by its ID.

## Workflow

1. Confirm the user wants to work with local Codex session storage, not a cloud/account chat.
2. When the user needs to find session IDs first, list them by folder:

```powershell
python scripts/list_codex_sessions_by_folder.py
```

3. Add `--show-paths` when the user also wants rollout file paths.
4. Add `--include-missing` when the user wants DB rows whose rollout file is already missing.
5. When the user wants to inspect or delete one session, run the deletion script in preview mode first:

```powershell
python scripts/delete_codex_local_session.py <session-id>
```

6. Show the user what the script found.
7. Only run deletion after the user clearly asks for it:

```powershell
python scripts/delete_codex_local_session.py <session-id> --apply
```

8. Add `--vacuum` only when the user wants SQLite compaction after deletion.
9. Add `--keep-global-state` only when the user explicitly wants `.codex-global-state.json` left untouched.

## Listing Script Output

- Groups sessions by their actual parent folders such as `sessions/2026/04/18`
- Shows `session_id | title`
- Marks archived sessions with `| archived`
- Can also mark DB-only rows with `| missing` when `--include-missing` is used

## What The Script Removes

- Matching rollout transcript files under `sessions/` and `archived_sessions/`
- Matching `session_index.jsonl` entries
- Matching rows in `state*.sqlite` from `threads`, `thread_dynamic_tools`, and `thread_spawn_edges`
- Matching rows in `logs*.sqlite`
- Matching `generated_images/<session-id>/` directories
- Exact-key and exact-value references to the session ID inside `.codex-global-state.json`

## Safety Notes

- Default to listing or preview mode unless the user explicitly wants deletion.
- Tell the user to close the Codex app first when possible, because the UI may cache stale state.
- Tell the user that a restart may still be needed after deletion.
- Do not claim that this skill deletes cloud/account history. It only cleans up local Codex storage.
