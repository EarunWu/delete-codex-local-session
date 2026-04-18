---
name: delete-codex-local-session
description: Delete or inspect a local Codex session/thread by session ID. Use when Codex needs to find which local files belong to a session, preview what would be removed from `CODEX_HOME` or `~/.codex`, or safely delete a local thread from transcript files, session indexes, SQLite state, logs, and generated-images folders. This skill is for local-only Codex cleanup, not cloud/account chat deletion.
---

# Delete Codex Local Session

Use `scripts/delete_codex_local_session.py` to inspect and remove a local Codex session by its ID.

## Workflow

1. Confirm the user wants to clean up a local Codex session, not a cloud/account chat.
2. Run the script in preview mode first:

```powershell
python scripts/delete_codex_local_session.py <session-id>
```

3. Show the user what the script found.
4. Only run deletion after the user clearly asks for it:

```powershell
python scripts/delete_codex_local_session.py <session-id> --apply
```

5. Add `--vacuum` only when the user wants SQLite compaction after deletion.
6. Add `--keep-global-state` only when the user explicitly wants `.codex-global-state.json` left untouched.

## What The Script Removes

- Matching rollout transcript files under `sessions/` and `archived_sessions/`
- Matching `session_index.jsonl` entries
- Matching rows in `state*.sqlite` from `threads`, `thread_dynamic_tools`, and `thread_spawn_edges`
- Matching rows in `logs*.sqlite`
- Matching `generated_images/<session-id>/` directories
- Exact-key and exact-value references to the session ID inside `.codex-global-state.json`

## Safety Notes

- Default to preview mode unless the user explicitly wants deletion.
- Tell the user to close the Codex app first when possible, because the UI may cache stale state.
- Tell the user that a restart may still be needed after deletion.
- Do not claim that this skill deletes cloud/account history. It only cleans up local Codex storage.
