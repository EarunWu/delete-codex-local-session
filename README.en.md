[简体中文](./README.md) | English

# delete-codex-local-session

A Codex skill for listing, inspecting, and deleting local Codex sessions by session ID.

This skill is designed for local Codex session management and cleanup only. It does not delete cloud/account chat history.

## What it does

- List local session IDs and titles grouped by local session folders
- Preview which local files and database records match a session ID
- Delete matching rollout transcripts under `sessions/` and `archived_sessions/`
- Remove matching entries from `session_index.jsonl`
- Remove matching rows from `state*.sqlite`
- Remove matching rows from `logs*.sqlite`
- Remove matching generated image folders under `generated_images/<session-id>/`
- Remove exact-key and exact-value references from `.codex-global-state.json`

## Safety model

- Preview is the default mode
- Nothing is deleted unless you pass `--apply`
- `--vacuum` is optional and compacts touched SQLite databases after deletion
- `--keep-global-state` leaves `.codex-global-state.json` untouched

## Disclaimer

- This skill only operates on local Codex data under `CODEX_HOME` or `~/.codex`. It does not delete cloud, account-level, or server-side chat history.
- Deletion is destructive. Run preview mode first and make your own backups when needed before removing local data.
- Codex local directory layouts, SQLite schemas, and internal storage details may change over time. Verify behavior on the version you are using.
- You are responsible for how you export, delete, back up, or share local conversation data, including compliance with your device policies, team rules, or legal obligations.

## Install

Place this repository's contents in your Codex skills directory as:

```text
~/.codex/skills/delete-codex-local-session/
```

On Windows, that usually means:

```text
C:\Users\<you>\.codex\skills\delete-codex-local-session\
```

The final structure should look like this:

```text
delete-codex-local-session/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── scripts/
    ├── list_codex_sessions_by_folder.py
    └── delete_codex_local_session.py
```

## Use in Codex chat

Ask Codex to use the skill explicitly:

```text
Use $delete-codex-local-session to list local session IDs and titles
Use $delete-codex-local-session to preview local session 019d...
Use $delete-codex-local-session to delete local session 019d...
```

Default interpretation:

- Requests like "conversation list", "session list", or "conversation ID list" should return the listing script's native output
- Only return bare IDs when the user explicitly asks for IDs only

## Usage examples

These screenshots show typical natural-language cleanup requests in a Codex conversation.

Delete local sessions before a specific date:

![Delete local sessions before a specific date](./docs/images/usage-delete-by-date.png)

Delete archived local sessions:

![Delete archived local sessions](./docs/images/usage-delete-archived.png)

## Use from the command line

List local sessions by folder:

```powershell
python scripts/list_codex_sessions_by_folder.py
```

List sessions and show full rollout paths:

```powershell
python scripts/list_codex_sessions_by_folder.py --show-paths
```

Include DB rows whose rollout file is missing:

```powershell
python scripts/list_codex_sessions_by_folder.py --include-missing
```

Preview only:

```powershell
python scripts/delete_codex_local_session.py <session-id>
```

Delete the local session:

```powershell
python scripts/delete_codex_local_session.py <session-id> --apply
```

Delete and compact SQLite databases:

```powershell
python scripts/delete_codex_local_session.py <session-id> --apply --vacuum
```

Keep `.codex-global-state.json` unchanged:

```powershell
python scripts/delete_codex_local_session.py <session-id> --apply --keep-global-state
```

## Recommendations

- Close the Codex app before deleting a session when possible
- If the deleted thread still appears in the UI, first minimize the Codex app to the taskbar and restore the window, because that often triggers a sidebar refresh
- Restart the Codex app only if minimizing and restoring the window does not refresh the UI
- Use preview mode first for every session ID

## Requirements

- Python 3
- No third-party Python packages are required for the bundled script

## Repository contents

- `SKILL.md`: skill trigger and usage guidance
- `agents/openai.yaml`: UI-facing metadata
- `docs/images/`: README usage screenshots
- `scripts/list_codex_sessions_by_folder.py`: list local session IDs and titles by folder
- `scripts/delete_codex_local_session.py`: the actual cleanup script

## Limitations

- Local only. This does not remove server-side or account-level chat history.
- The UI may temporarily show stale threads until Codex refreshes; minimizing and restoring the window often helps, but immediate refresh is not guaranteed.
