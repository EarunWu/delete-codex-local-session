#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


SESSION_ID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
REMOVE = object()


@dataclass
class SessionPlan:
    session_id: str
    codex_home: Path
    thread_rows: list[dict[str, Any]] = field(default_factory=list)
    state_db_counts: dict[str, dict[str, int]] = field(default_factory=dict)
    log_db_counts: dict[str, int] = field(default_factory=dict)
    rollout_files: list[Path] = field(default_factory=list)
    generated_image_dir: Path | None = None
    session_index_matches: int = 0
    global_state_would_change: bool = False

    def has_anything_to_delete(self) -> bool:
        if self.thread_rows or self.rollout_files or self.generated_image_dir:
            return True
        if self.session_index_matches or self.global_state_would_change:
            return True
        if any(any(value for value in table_counts.values()) for table_counts in self.state_db_counts.values()):
            return True
        if any(value for value in self.log_db_counts.values()):
            return True
        return False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Delete a local Codex session by session/thread ID."
    )
    parser.add_argument("session_id", help="Codex local session ID to remove")
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=None,
        help="Override Codex home directory (default: CODEX_HOME or ~/.codex)",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually perform the deletion. Without this flag the tool only previews.",
    )
    parser.add_argument(
        "--vacuum",
        action="store_true",
        help="Run VACUUM on touched SQLite databases after deleting rows.",
    )
    parser.add_argument(
        "--keep-global-state",
        action="store_true",
        help="Do not rewrite .codex-global-state.json.",
    )
    return parser.parse_args()


def detect_codex_home(override: Path | None) -> Path:
    if override is not None:
        return override.expanduser().resolve()
    env_value = os.environ.get("CODEX_HOME")
    if env_value:
        return Path(env_value).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def find_sqlite_files(codex_home: Path, pattern: str) -> list[Path]:
    return sorted(path for path in codex_home.glob(pattern) if path.is_file())


def fetch_rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> list[dict[str, Any]]:
    conn.row_factory = sqlite3.Row
    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def count_rows(conn: sqlite3.Connection, query: str, params: tuple[Any, ...]) -> int:
    cursor = conn.execute(query, params)
    row = cursor.fetchone()
    return int(row[0] if row else 0)


def scrub_json_value(value: Any, needle: str) -> tuple[Any, bool]:
    if isinstance(value, dict):
        changed = False
        new_dict: dict[str, Any] = {}
        for key, child in value.items():
            if key == needle:
                changed = True
                continue
            new_child, child_changed = scrub_json_value(child, needle)
            if child_changed:
                changed = True
            if new_child is REMOVE:
                changed = True
                continue
            new_dict[key] = new_child
        return new_dict, changed

    if isinstance(value, list):
        changed = False
        new_list: list[Any] = []
        for child in value:
            new_child, child_changed = scrub_json_value(child, needle)
            if child_changed:
                changed = True
            if new_child is REMOVE:
                changed = True
                continue
            new_list.append(new_child)
        return new_list, changed

    if value == needle:
        return REMOVE, True

    return value, False


def collect_rollout_files(codex_home: Path, session_id: str, thread_rows: list[dict[str, Any]]) -> list[Path]:
    candidates: set[Path] = set()

    for row in thread_rows:
        rollout_path = row.get("rollout_path")
        if rollout_path:
            candidates.add(Path(rollout_path))

    for base_name in ("sessions", "archived_sessions"):
        base_dir = codex_home / base_name
        if not base_dir.exists():
            continue
        for path in base_dir.rglob(f"*{session_id}*.jsonl"):
            candidates.add(path)

    return sorted(path for path in candidates if path.exists())


def build_plan(session_id: str, codex_home: Path, keep_global_state: bool) -> SessionPlan:
    plan = SessionPlan(session_id=session_id, codex_home=codex_home)

    for state_db in find_sqlite_files(codex_home, "state*.sqlite"):
        with sqlite3.connect(state_db, timeout=30) as conn:
            thread_rows = fetch_rows(
                conn,
                "SELECT * FROM threads WHERE id = ?",
                (session_id,),
            )
            if thread_rows:
                plan.thread_rows.extend(thread_rows)

            plan.state_db_counts[str(state_db)] = {
                "threads": len(thread_rows),
                "thread_dynamic_tools": count_rows(
                    conn,
                    "SELECT COUNT(*) FROM thread_dynamic_tools WHERE thread_id = ?",
                    (session_id,),
                ),
                "thread_spawn_edges": count_rows(
                    conn,
                    "SELECT COUNT(*) FROM thread_spawn_edges WHERE parent_thread_id = ? OR child_thread_id = ?",
                    (session_id, session_id),
                ),
            }

    for logs_db in find_sqlite_files(codex_home, "logs*.sqlite"):
        with sqlite3.connect(logs_db, timeout=30) as conn:
            plan.log_db_counts[str(logs_db)] = count_rows(
                conn,
                "SELECT COUNT(*) FROM logs WHERE thread_id = ?",
                (session_id,),
            )

    plan.rollout_files = collect_rollout_files(codex_home, session_id, plan.thread_rows)

    image_dir = codex_home / "generated_images" / session_id
    if image_dir.exists():
        plan.generated_image_dir = image_dir

    session_index_path = codex_home / "session_index.jsonl"
    if session_index_path.exists():
        with session_index_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    record = json.loads(stripped)
                    if record.get("id") == session_id:
                        plan.session_index_matches += 1
                except json.JSONDecodeError:
                    if session_id in stripped:
                        plan.session_index_matches += 1

    if not keep_global_state:
        global_state_path = codex_home / ".codex-global-state.json"
        if global_state_path.exists():
            with global_state_path.open("r", encoding="utf-8") as handle:
                state = json.load(handle)
            _, changed = scrub_json_value(state, session_id)
            plan.global_state_would_change = changed

    return plan


def print_plan(plan: SessionPlan) -> None:
    print(f"Codex home: {plan.codex_home}")
    print(f"Session ID: {plan.session_id}")
    print()
    print("Matches:")

    if plan.thread_rows:
        for row in plan.thread_rows:
            print(f"- thread row: title={row.get('title')!r} rollout_path={row.get('rollout_path')}")
    else:
        print("- thread row: none")

    if plan.rollout_files:
        for path in plan.rollout_files:
            print(f"- rollout file: {path}")
    else:
        print("- rollout file: none")

    if plan.generated_image_dir is not None:
        print(f"- generated image dir: {plan.generated_image_dir}")
    else:
        print("- generated image dir: none")

    print(f"- session_index.jsonl entries: {plan.session_index_matches}")
    print(f"- .codex-global-state.json changes needed: {'yes' if plan.global_state_would_change else 'no'}")

    for db_path, counts in sorted(plan.state_db_counts.items()):
        print(f"- state db: {db_path}")
        for table_name, count in counts.items():
            print(f"  {table_name}: {count}")

    for db_path, count in sorted(plan.log_db_counts.items()):
        print(f"- logs db: {db_path}")
        print(f"  logs: {count}")


def rewrite_session_index(session_index_path: Path, session_id: str) -> int:
    if not session_index_path.exists():
        return 0

    removed = 0
    with session_index_path.open("r", encoding="utf-8") as src, tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=session_index_path.parent,
    ) as tmp:
        tmp_path = Path(tmp.name)
        for line in src:
            stripped = line.strip()
            drop_line = False
            if stripped:
                try:
                    record = json.loads(stripped)
                    drop_line = record.get("id") == session_id
                except json.JSONDecodeError:
                    drop_line = session_id in stripped
            if drop_line:
                removed += 1
                continue
            tmp.write(line)

    os.replace(tmp_path, session_index_path)
    return removed


def rewrite_global_state(global_state_path: Path, session_id: str) -> bool:
    if not global_state_path.exists():
        return False

    with global_state_path.open("r", encoding="utf-8") as handle:
        state = json.load(handle)

    new_state, changed = scrub_json_value(state, session_id)
    if not changed:
        return False

    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=global_state_path.parent,
    ) as tmp:
        tmp.write(json.dumps(new_state, ensure_ascii=False, separators=(",", ":")))
        tmp_path = Path(tmp.name)

    os.replace(tmp_path, global_state_path)
    return True


def delete_rows_from_state_db(db_path: Path, session_id: str, vacuum: bool) -> dict[str, int]:
    deleted = {"threads": 0, "thread_dynamic_tools": 0, "thread_spawn_edges": 0}
    with sqlite3.connect(db_path, timeout=30) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM thread_dynamic_tools WHERE thread_id = ?", (session_id,))
        deleted["thread_dynamic_tools"] = cursor.rowcount
        cursor.execute(
            "DELETE FROM thread_spawn_edges WHERE parent_thread_id = ? OR child_thread_id = ?",
            (session_id, session_id),
        )
        deleted["thread_spawn_edges"] = cursor.rowcount
        cursor.execute("DELETE FROM threads WHERE id = ?", (session_id,))
        deleted["threads"] = cursor.rowcount
        conn.commit()
        if vacuum:
            conn.execute("VACUUM")
    return deleted


def delete_rows_from_logs_db(db_path: Path, session_id: str, vacuum: bool) -> int:
    with sqlite3.connect(db_path, timeout=30) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM logs WHERE thread_id = ?", (session_id,))
        deleted = cursor.rowcount
        conn.commit()
        if vacuum:
            conn.execute("VACUUM")
    return deleted


def prune_empty_parents(path: Path, stop_at: Path) -> None:
    current = path.parent
    stop_at = stop_at.resolve()
    while current.exists():
        resolved = current.resolve()
        if resolved == stop_at:
            break
        if any(current.iterdir()):
            break
        current.rmdir()
        current = current.parent


def apply_plan(plan: SessionPlan, keep_global_state: bool, vacuum: bool) -> None:
    for state_db in find_sqlite_files(plan.codex_home, "state*.sqlite"):
        deleted = delete_rows_from_state_db(state_db, plan.session_id, vacuum)
        if any(deleted.values()):
            print(f"Updated state db: {state_db}")
            for table_name, count in deleted.items():
                print(f"  {table_name}: deleted {count}")

    for logs_db in find_sqlite_files(plan.codex_home, "logs*.sqlite"):
        deleted = delete_rows_from_logs_db(logs_db, plan.session_id, vacuum)
        if deleted:
            print(f"Updated logs db: {logs_db}")
            print(f"  logs: deleted {deleted}")

    session_index_path = plan.codex_home / "session_index.jsonl"
    removed_index_entries = rewrite_session_index(session_index_path, plan.session_id)
    if removed_index_entries:
        print(f"Updated session index: removed {removed_index_entries} entries")

    if not keep_global_state:
        global_state_path = plan.codex_home / ".codex-global-state.json"
        if rewrite_global_state(global_state_path, plan.session_id):
            print("Updated .codex-global-state.json")

    for rollout_file in plan.rollout_files:
        if rollout_file.exists():
            rollout_file.unlink()
            print(f"Deleted rollout file: {rollout_file}")
            if (plan.codex_home / "sessions") in rollout_file.parents:
                prune_empty_parents(rollout_file, plan.codex_home / "sessions")

    if plan.generated_image_dir and plan.generated_image_dir.exists():
        shutil.rmtree(plan.generated_image_dir)
        print(f"Deleted generated image dir: {plan.generated_image_dir}")


def main() -> int:
    args = parse_args()

    if not SESSION_ID_RE.match(args.session_id):
        print("Session ID does not look valid.", file=sys.stderr)
        return 2

    codex_home = detect_codex_home(args.codex_home)
    if not codex_home.exists():
        print(f"Codex home does not exist: {codex_home}", file=sys.stderr)
        return 2

    plan = build_plan(args.session_id, codex_home, args.keep_global_state)
    print_plan(plan)
    print()

    if not plan.has_anything_to_delete():
        print("No local matches found for that session ID.")
        return 1

    if not args.apply:
        print("Preview only. Re-run with --apply to delete the local session.")
        print("Tip: close the Codex app first so it does not keep stale state in memory.")
        return 0

    apply_plan(plan, args.keep_global_state, args.vacuum)
    print()
    print("Deletion finished.")
    print("Tip: restart the Codex app if the deleted thread still appears in the UI.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
