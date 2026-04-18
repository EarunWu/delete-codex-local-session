#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


SESSION_ID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
)


@dataclass
class ThreadMeta:
    session_id: str
    title: str
    archived: bool
    created_at_ms: int | None
    rollout_path: Path | None


@dataclass
class SessionEntry:
    folder: str
    session_id: str
    title: str
    archived: bool
    path: str
    exists: bool
    created_at_ms: int | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List local Codex session IDs and titles grouped by folder."
    )
    parser.add_argument(
        "--codex-home",
        type=Path,
        default=None,
        help="Override Codex home directory (default: CODEX_HOME or ~/.codex).",
    )
    parser.add_argument(
        "--show-paths",
        action="store_true",
        help="Show the full rollout path in text output.",
    )
    parser.add_argument(
        "--include-missing",
        action="store_true",
        help="Include DB rows whose rollout_path is missing on disk.",
    )
    return parser.parse_args()


def detect_codex_home(override: Path | None) -> Path:
    if override is not None:
        return override.expanduser().resolve()
    env_value = os.environ.get("CODEX_HOME")
    if env_value:
        return Path(env_value).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def sanitize_title(title: str | None) -> str:
    return " ".join((title or "").replace("\r", " ").replace("\n", " ").split())


def configure_stdout() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def find_state_dbs(codex_home: Path) -> list[Path]:
    return sorted(path for path in codex_home.glob("state*.sqlite") if path.is_file())


def load_thread_metadata(codex_home: Path) -> dict[str, ThreadMeta]:
    metadata: dict[str, ThreadMeta] = {}

    for db_path in find_state_dbs(codex_home):
        with sqlite3.connect(db_path, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT id, title, archived, created_at_ms, rollout_path FROM threads"
            ).fetchall()

        for row in rows:
            session_id = row["id"]
            current = metadata.get(session_id)
            created_at_ms = row["created_at_ms"]
            if current is not None:
                current_created = current.created_at_ms or -1
                next_created = created_at_ms or -1
                if current_created > next_created:
                    continue

            rollout_path = Path(row["rollout_path"]) if row["rollout_path"] else None
            metadata[session_id] = ThreadMeta(
                session_id=session_id,
                title=sanitize_title(row["title"]),
                archived=bool(row["archived"]),
                created_at_ms=created_at_ms,
                rollout_path=rollout_path,
            )

    return metadata


def extract_session_id(path: Path) -> str | None:
    match = SESSION_ID_RE.search(path.name)
    return match.group(0) if match else None


def collect_rollout_files(codex_home: Path) -> list[Path]:
    files: list[Path] = []
    for base_name in ("sessions", "archived_sessions"):
        base_dir = codex_home / base_name
        if not base_dir.exists():
            continue
        files.extend(path for path in base_dir.rglob("rollout-*.jsonl") if path.is_file())
    return sorted(files)


def fallback_title_from_rollout(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as handle:
            for _ in range(40):
                line = handle.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    continue

                if record.get("type") == "session_meta":
                    payload = record.get("payload") or {}
                    first_user_message = sanitize_title(payload.get("first_user_message"))
                    if first_user_message:
                        return first_user_message

                if record.get("type") == "response_item":
                    payload = record.get("payload") or {}
                    if payload.get("type") != "message" or payload.get("role") != "user":
                        continue
                    contents = payload.get("content") or []
                    text_parts = []
                    for item in contents:
                        if item.get("type") == "input_text" and item.get("text"):
                            text_parts.append(item["text"])
                    title = sanitize_title(" ".join(text_parts))
                    if title:
                        return title
    except OSError:
        return ""

    return ""


def folder_key(path: Path, codex_home: Path) -> str:
    try:
        return path.parent.relative_to(codex_home).as_posix()
    except ValueError:
        return str(path.parent)


def build_entries(codex_home: Path, include_missing: bool) -> list[SessionEntry]:
    metadata = load_thread_metadata(codex_home)
    entries: list[SessionEntry] = []
    seen_ids: set[str] = set()

    for path in collect_rollout_files(codex_home):
        session_id = extract_session_id(path)
        if not session_id:
            continue

        meta = metadata.get(session_id)
        title = meta.title if meta and meta.title else fallback_title_from_rollout(path)
        if not title:
            title = "<title not found>"
        archived = meta.archived if meta else "archived_sessions" in path.parts
        created_at_ms = meta.created_at_ms if meta else None
        entries.append(
            SessionEntry(
                folder=folder_key(path, codex_home),
                session_id=session_id,
                title=title,
                archived=bool(archived),
                path=str(path),
                exists=True,
                created_at_ms=created_at_ms,
            )
        )
        seen_ids.add(session_id)

    if include_missing:
        for session_id, meta in metadata.items():
            if session_id in seen_ids:
                continue
            if meta.rollout_path is None:
                continue
            entries.append(
                SessionEntry(
                    folder="missing_rollout_path",
                    session_id=session_id,
                    title=meta.title or "<title not found>",
                    archived=meta.archived,
                    path=str(meta.rollout_path),
                    exists=False,
                    created_at_ms=meta.created_at_ms,
                )
            )

    entries.sort(
        key=lambda item: (
            item.folder == "missing_rollout_path",
            item.folder,
            item.created_at_ms or 0,
            item.session_id,
        )
    )
    return entries


def print_text(entries: list[SessionEntry], show_paths: bool) -> None:
    grouped: dict[str, list[SessionEntry]] = defaultdict(list)
    for entry in entries:
        grouped[entry.folder].append(entry)

    for folder in sorted(grouped):
        print(f"[{folder}]")
        for entry in grouped[folder]:
            line = f"- {entry.session_id} | {entry.title}"
            if entry.archived:
                line += " | archived"
            if not entry.exists:
                line += " | missing"
            if show_paths:
                line += f" | {entry.path}"
            print(line)
        print()


def main() -> int:
    configure_stdout()
    args = parse_args()
    codex_home = detect_codex_home(args.codex_home)
    if not codex_home.exists():
        print(f"Codex home does not exist: {codex_home}", file=sys.stderr)
        return 2

    entries = build_entries(codex_home, args.include_missing)
    print_text(entries, args.show_paths)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
