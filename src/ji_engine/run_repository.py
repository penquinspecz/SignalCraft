"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Dict, List, Optional, Protocol

from ji_engine.config import (
    DEFAULT_CANDIDATE_ID,
    RUN_METADATA_DIR,
    STATE_DIR,
    candidate_run_index_path,
    candidate_run_metadata_dir,
    candidate_state_dir,
    sanitize_candidate_id,
)

logger = logging.getLogger(__name__)


def _normalize_run_id(run_id: str) -> str:
    from ji_engine.pipeline.run_pathing import sanitize_run_id

    return sanitize_run_id(run_id)


_sanitize_run_id = _normalize_run_id


def _invalid_artifact_path() -> ValueError:
    return ValueError("Invalid artifact path")


def _absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(path))


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _assert_no_symlinks_in_existing_path(path: Path) -> None:
    absolute = _absolute_lexical(path)
    parts = absolute.parts
    if not parts:
        return

    if absolute.anchor:
        current = Path(absolute.anchor)
        start = 1
    else:
        current = Path(parts[0])
        start = 1

    for part in parts[start:]:
        current = current / part
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            break
        except OSError as exc:
            raise _invalid_artifact_path() from exc
        if stat.S_ISLNK(mode):
            raise _invalid_artifact_path()


def _normalize_artifact_relative_path(relative_path: str) -> tuple[str, ...]:
    if not isinstance(relative_path, str):
        raise _invalid_artifact_path()
    raw = relative_path.strip()
    if not raw or "\\" in raw:
        raise _invalid_artifact_path()
    parsed = PurePosixPath(raw)
    if parsed.is_absolute():
        raise _invalid_artifact_path()
    parts = tuple(part for part in parsed.parts if part not in ("", "."))
    if not parts or any(part == ".." for part in parts):
        raise _invalid_artifact_path()
    return parts


def _read_text_no_symlink(path: Path, *, encoding: str = "utf-8") -> str:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    if nofollow:
        fd = os.open(path, os.O_RDONLY | nofollow)
        with os.fdopen(fd, "r", encoding=encoding) as handle:
            return handle.read()
    _assert_no_symlinks_in_existing_path(path)
    return path.read_text(encoding=encoding)


def _profiles_from_run_payload(payload: Dict[str, Any]) -> List[str]:
    """Extract profile names from run index payload (index.json structure)."""
    profiles: set[str] = set()
    for prov_data in (payload.get("providers") or {}).values():
        if isinstance(prov_data, dict) and "profiles" in prov_data:
            profiles.update((prov_data.get("profiles") or {}).keys())
    return sorted(profiles)


class RunRepository(Protocol):
    def list_run_dirs(self, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> List[Path]: ...

    def resolve_run_dir(self, run_id: str, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Path: ...

    def list_run_metadata_paths(self, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> List[Path]: ...

    def resolve_run_metadata_path(self, run_id: str, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Path: ...

    def list_runs_for_profile(
        self,
        *,
        candidate_id: str = DEFAULT_CANDIDATE_ID,
        profile: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]: ...

    def resolve_run_artifact_path(
        self,
        run_id: str,
        relative_path: str,
        *,
        candidate_id: str = DEFAULT_CANDIDATE_ID,
    ) -> Path: ...

    def write_run_json(
        self,
        run_id: str,
        relative_path: str,
        payload: Dict[str, Any],
        *,
        candidate_id: str = DEFAULT_CANDIDATE_ID,
        sort_keys: bool = True,
    ) -> Path: ...

    def run_dir(self, run_id: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Path: ...

    def get_run(self, run_id: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Optional[Dict[str, Any]]: ...

    def list_runs(self, candidate_id: str = DEFAULT_CANDIDATE_ID, limit: int = 200) -> List[Dict[str, Any]]: ...

    def latest_run(self, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Optional[Dict[str, Any]]: ...

    def rebuild_index(self, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Dict[str, Any]: ...


@dataclass(frozen=True)
class _RunIndexEntry:
    run_id: str
    timestamp: str
    run_dir: Path
    index_path: Path
    payload: Dict[str, Any]


def list_run_metadata_paths_from_dir(runs_dir: Path) -> List[Path]:
    """List *.json run metadata files in runs_dir. Used by prune_state and other scripts."""
    if not runs_dir.exists():
        return []
    paths = sorted((p for p in runs_dir.glob("*.json") if p.is_file()), key=lambda p: p.name)
    return paths


class FileSystemRunRepository(RunRepository):
    def __init__(self, legacy_runs_dir: Path = RUN_METADATA_DIR) -> None:
        self._legacy_runs_dir = legacy_runs_dir
        self._fallback_logged: set[str] = set()

    def _db_path(self, candidate_id: str) -> Path:
        namespaced = candidate_run_index_path(candidate_id)
        legacy = candidate_state_dir(candidate_id) / "run_index.sqlite"
        if namespaced.exists() or not legacy.exists():
            return namespaced
        return legacy

    def _candidate_run_roots(self, candidate_id: str) -> List[Path]:
        roots: List[Path] = []
        namespaced = candidate_run_metadata_dir(candidate_id)
        roots.append(namespaced)
        if candidate_id == DEFAULT_CANDIDATE_ID and self._legacy_runs_dir != namespaced:
            roots.append(self._legacy_runs_dir)
        seen: set[Path] = set()
        unique_roots: List[Path] = []
        for root in roots:
            resolved = root.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            unique_roots.append(root)
        return unique_roots

    def run_dir(self, run_id: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Path:
        safe_candidate = sanitize_candidate_id(candidate_id)
        safe_run = _normalize_run_id(run_id)
        namespaced = candidate_run_metadata_dir(safe_candidate) / safe_run
        if namespaced.exists():
            return namespaced
        if safe_candidate == DEFAULT_CANDIDATE_ID:
            legacy = self._legacy_runs_dir / safe_run
            if legacy.exists():
                return legacy
        return namespaced

    # Compatibility seam methods kept for existing callers.
    def resolve_run_dir(self, run_id: str, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Path:
        return self.run_dir(run_id, candidate_id=candidate_id)

    def list_run_dirs(self, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> List[Path]:
        runs = self.list_runs(candidate_id=candidate_id, limit=1000)
        run_dirs: List[Path] = []
        seen: set[Path] = set()
        for item in runs:
            run_id = item.get("run_id")
            if not isinstance(run_id, str) or not run_id.strip():
                continue
            path = self.resolve_run_dir(run_id, candidate_id=candidate_id)
            resolved = path.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            run_dirs.append(path)
        return run_dirs

    def list_run_metadata_paths(self, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> List[Path]:
        paths_by_name: Dict[str, Path] = {}
        for root in self._candidate_run_roots(candidate_id):
            if not root.exists():
                continue
            for path in sorted(root.glob("*.json"), key=lambda p: p.name):
                if not path.is_file():
                    continue
                paths_by_name.setdefault(path.name, path)
        return [paths_by_name[name] for name in sorted(paths_by_name.keys())]

    def resolve_run_metadata_path(self, run_id: str, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Path:
        safe_run = _normalize_run_id(run_id)
        for root in self._candidate_run_roots(candidate_id):
            candidate = root / f"{safe_run}.json"
            if candidate.exists():
                return candidate
        return self._candidate_run_roots(candidate_id)[0] / f"{safe_run}.json"

    def resolve_run_artifact_path(
        self,
        run_id: str,
        relative_path: str,
        *,
        candidate_id: str = DEFAULT_CANDIDATE_ID,
    ) -> Path:
        safe_candidate = sanitize_candidate_id(candidate_id)
        run_root = _absolute_lexical(self.resolve_run_dir(run_id, candidate_id=safe_candidate))
        allowed_roots = [_absolute_lexical(root) for root in self._candidate_run_roots(safe_candidate)]
        if not any(_path_is_within(run_root, root) for root in allowed_roots):
            raise _invalid_artifact_path()

        parts = _normalize_artifact_relative_path(relative_path)
        candidate = run_root.joinpath(*parts)
        if not _path_is_within(candidate, run_root):
            raise _invalid_artifact_path()

        _assert_no_symlinks_in_existing_path(run_root)
        _assert_no_symlinks_in_existing_path(candidate)
        return candidate

    def write_run_json(
        self,
        run_id: str,
        relative_path: str,
        payload: Dict[str, Any],
        *,
        candidate_id: str = DEFAULT_CANDIDATE_ID,
        sort_keys: bool = True,
    ) -> Path:
        out_path = self.resolve_run_artifact_path(run_id, relative_path, candidate_id=candidate_id)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=sort_keys), encoding="utf-8")
        return out_path

    def _read_index_json(self, path: Path) -> Optional[Dict[str, Any]]:
        if not path.exists() or not path.is_file():
            return None
        try:
            payload = json.loads(_read_text_no_symlink(path))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return payload

    def _scan_runs_from_filesystem(self, candidate_id: str) -> List[_RunIndexEntry]:
        entries: Dict[str, _RunIndexEntry] = {}
        for root in self._candidate_run_roots(candidate_id):
            if not root.exists():
                continue
            for run_dir in sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name):
                index_path = run_dir / "index.json"
                payload = self._read_index_json(index_path)
                if payload is None:
                    continue
                run_id = payload.get("run_id")
                if not isinstance(run_id, str) or not run_id.strip():
                    continue
                if run_id in entries:
                    continue
                timestamp = payload.get("timestamp")
                if not isinstance(timestamp, str) or not timestamp.strip():
                    timestamp = run_id
                entries[run_id] = _RunIndexEntry(
                    run_id=run_id,
                    timestamp=timestamp,
                    run_dir=run_dir,
                    index_path=index_path,
                    payload=payload,
                )
        ordered = sorted(entries.values(), key=lambda e: (e.timestamp, e.run_id), reverse=True)
        return ordered

    def _ensure_schema(self, conn: sqlite3.Connection) -> None:
        conn.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS run_index (
                candidate_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                run_dir TEXT NOT NULL,
                index_path TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                PRIMARY KEY (candidate_id, run_id)
            );
            CREATE INDEX IF NOT EXISTS idx_run_index_latest
                ON run_index(candidate_id, timestamp DESC, run_id DESC);
            """
        )

    def rebuild_index(self, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Dict[str, Any]:
        safe_candidate = sanitize_candidate_id(candidate_id)
        db_path = self._db_path(safe_candidate)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = db_path.with_suffix(".tmp")
        if tmp_path.exists():
            tmp_path.unlink()

        entries = self._scan_runs_from_filesystem(safe_candidate)
        conn = sqlite3.connect(tmp_path)
        try:
            self._ensure_schema(conn)
            conn.execute("DELETE FROM run_index WHERE candidate_id = ?", (safe_candidate,))
            for entry in sorted(entries, key=lambda e: e.run_id):
                conn.execute(
                    """
                    INSERT OR REPLACE INTO run_index(
                        candidate_id, run_id, timestamp, run_dir, index_path, payload_json
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        safe_candidate,
                        entry.run_id,
                        entry.timestamp,
                        str(entry.run_dir),
                        str(entry.index_path),
                        json.dumps(entry.payload, sort_keys=True, separators=(",", ":")),
                    ),
                )
            conn.commit()
        finally:
            conn.close()
        os.replace(tmp_path, db_path)
        return {
            "candidate_id": safe_candidate,
            "db_path": str(db_path),
            "runs_indexed": len(entries),
        }

    def _read_rows(self, candidate_id: str, limit: int) -> List[Dict[str, Any]]:
        return self._read_rows_page(candidate_id, limit=limit, offset=0)

    def _read_rows_page(self, candidate_id: str, *, limit: int, offset: int) -> List[Dict[str, Any]]:
        safe_candidate = sanitize_candidate_id(candidate_id)
        db_path = self._db_path(safe_candidate)
        if not db_path.exists():
            self.rebuild_index(safe_candidate)
        conn = sqlite3.connect(db_path)
        try:
            rows = conn.execute(
                """
                SELECT payload_json
                FROM run_index
                WHERE candidate_id = ?
                ORDER BY timestamp DESC, run_id DESC
                LIMIT ?
                OFFSET ?
                """,
                (safe_candidate, limit, offset),
            ).fetchall()
            return [json.loads(row[0]) for row in rows]
        finally:
            conn.close()

    def _read_one(self, candidate_id: str, run_id: str) -> Optional[Dict[str, Any]]:
        safe_candidate = sanitize_candidate_id(candidate_id)
        db_path = self._db_path(safe_candidate)
        if not db_path.exists():
            self.rebuild_index(safe_candidate)
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute(
                """
                SELECT payload_json
                FROM run_index
                WHERE candidate_id = ? AND run_id = ?
                LIMIT 1
                """,
                (safe_candidate, run_id),
            ).fetchone()
            if not row:
                return None
            return json.loads(row[0])
        finally:
            conn.close()

    def _fallback(self, candidate_id: str, reason: str) -> List[Dict[str, Any]]:
        safe_candidate = sanitize_candidate_id(candidate_id)
        marker = f"{safe_candidate}:{reason}"
        if marker not in self._fallback_logged:
            logger.warning(
                "run_index fallback to filesystem scan: reason=%s candidate_id=%s",
                reason,
                safe_candidate,
            )
            self._fallback_logged.add(marker)
        return [entry.payload for entry in self._scan_runs_from_filesystem(safe_candidate)]

    def list_runs(self, candidate_id: str = DEFAULT_CANDIDATE_ID, limit: int = 200) -> List[Dict[str, Any]]:
        safe_candidate = sanitize_candidate_id(candidate_id)
        bounded_limit = max(1, min(limit, 1000))
        try:
            rows = self._read_rows(safe_candidate, bounded_limit)
            if rows:
                return rows
            return self._fallback(safe_candidate, "index_empty")
        except (json.JSONDecodeError, OSError, sqlite3.DatabaseError, sqlite3.OperationalError):
            self.rebuild_index(safe_candidate)
            try:
                return self._read_rows(safe_candidate, bounded_limit)
            except (json.JSONDecodeError, OSError, sqlite3.DatabaseError, sqlite3.OperationalError):
                return self._fallback(safe_candidate, "index_read_failed")

    def latest_run(self, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Optional[Dict[str, Any]]:
        rows = self.list_runs(candidate_id=candidate_id, limit=1)
        return rows[0] if rows else None

    def list_runs_for_profile(
        self,
        *,
        candidate_id: str = DEFAULT_CANDIDATE_ID,
        profile: str,
        limit: int = 200,
    ) -> List[Dict[str, Any]]:
        """
        List runs that include the given profile, newest-first.
        Deterministic ordering matches list_runs(): timestamp DESC, run_id DESC.
        """
        safe_candidate = sanitize_candidate_id(candidate_id)
        bounded_limit = max(1, min(limit, 1000))
        page_size = min(200, bounded_limit)

        def _select(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            selected: List[Dict[str, Any]] = []
            for payload in items:
                profiles = _profiles_from_run_payload(payload)
                if profile in profiles:
                    selected.append({"run_id": payload.get("run_id"), "profiles": profiles})
                    if len(selected) >= bounded_limit:
                        break
            return selected

        try:
            result: List[Dict[str, Any]] = []
            offset = 0
            while len(result) < bounded_limit:
                page = self._read_rows_page(safe_candidate, limit=page_size, offset=offset)
                if not page:
                    break
                for item in _select(page):
                    result.append(item)
                    if len(result) >= bounded_limit:
                        break
                if len(page) < page_size:
                    break
                offset += page_size
            return result
        except (json.JSONDecodeError, OSError, sqlite3.DatabaseError, sqlite3.OperationalError):
            self.rebuild_index(safe_candidate)
            try:
                result = []
                offset = 0
                while len(result) < bounded_limit:
                    page = self._read_rows_page(safe_candidate, limit=page_size, offset=offset)
                    if not page:
                        break
                    for item in _select(page):
                        result.append(item)
                        if len(result) >= bounded_limit:
                            break
                    if len(page) < page_size:
                        break
                    offset += page_size
                return result
            except (json.JSONDecodeError, OSError, sqlite3.DatabaseError, sqlite3.OperationalError):
                return _select(self._fallback(safe_candidate, "profile_index_read_failed"))

    def get_run(self, run_id: str, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Optional[Dict[str, Any]]:
        safe_candidate = sanitize_candidate_id(candidate_id)
        try:
            payload = self._read_one(safe_candidate, run_id)
            if payload:
                return payload
        except (json.JSONDecodeError, OSError, sqlite3.DatabaseError, sqlite3.OperationalError):
            self.rebuild_index(safe_candidate)
            try:
                payload = self._read_one(safe_candidate, run_id)
                if payload:
                    return payload
            except (json.JSONDecodeError, OSError, sqlite3.DatabaseError, sqlite3.OperationalError):
                pass

        for entry in self._scan_runs_from_filesystem(safe_candidate):
            if entry.run_id == run_id:
                return entry.payload
        return None


def discover_candidates() -> List[str]:
    candidates = {DEFAULT_CANDIDATE_ID}
    root = STATE_DIR / "candidates"
    if root.exists():
        for path in root.iterdir():
            if not path.is_dir():
                continue
            try:
                candidates.add(sanitize_candidate_id(path.name))
            except ValueError:
                continue
    return sorted(candidates)
