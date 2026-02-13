"""
SignalCraft
Copyright (c) 2026 Chris Menendez.
All Rights Reserved.
See LICENSE for permitted use.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Protocol, runtime_checkable

from ji_engine.config import DEFAULT_CANDIDATE_ID, RUN_METADATA_DIR, sanitize_candidate_id


@runtime_checkable
class RunRepository(Protocol):
    """Minimal seam for run storage operations."""

    def list_run_dirs(self, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> List[Path]: ...

    def resolve_run_dir(self, run_id: str, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Path: ...

    def list_run_metadata_paths(self, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> List[Path]: ...

    def resolve_run_metadata_path(self, run_id: str, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Path: ...

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


@dataclass(frozen=True)
class FileSystemRunRepository:
    """
    Run repository backed by the filesystem state layout.

    For candidate_id="local", reads remain backward-compatible by checking namespaced
    paths first and then legacy un-namespaced paths.
    """

    legacy_runs_dir: Path = RUN_METADATA_DIR

    def _sanitize_run_id(self, run_id: str) -> str:
        return run_id.replace(":", "").replace("-", "").replace(".", "")

    def _candidate_runs_dir(self, candidate_id: str) -> Path:
        safe_candidate = sanitize_candidate_id(candidate_id)
        return self.legacy_runs_dir.parent / "candidates" / safe_candidate / "runs"

    def _candidate_roots(self, candidate_id: str) -> List[Path]:
        safe_candidate = sanitize_candidate_id(candidate_id)
        roots = [self._candidate_runs_dir(safe_candidate)]
        if safe_candidate == DEFAULT_CANDIDATE_ID:
            roots.append(self.legacy_runs_dir)
        return roots

    def list_run_dirs(self, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> List[Path]:
        paths_by_name: Dict[str, Path] = {}
        for root in self._candidate_roots(candidate_id):
            if not root.exists():
                continue
            for path in sorted(root.iterdir(), key=lambda p: p.name):
                if not path.is_dir():
                    continue
                paths_by_name.setdefault(path.name, path)
        return [paths_by_name[name] for name in sorted(paths_by_name.keys())]

    def resolve_run_dir(self, run_id: str, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Path:
        safe_id = self._sanitize_run_id(run_id)
        roots = self._candidate_roots(candidate_id)
        for root in roots:
            candidate = root / safe_id
            if candidate.exists():
                return candidate
        return roots[0] / safe_id

    def list_run_metadata_paths(self, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> List[Path]:
        paths_by_name: Dict[str, Path] = {}
        for root in self._candidate_roots(candidate_id):
            if not root.exists():
                continue
            for path in sorted(root.glob("*.json"), key=lambda p: p.name):
                if not path.is_file():
                    continue
                paths_by_name.setdefault(path.name, path)
        return [paths_by_name[name] for name in sorted(paths_by_name.keys())]

    def resolve_run_metadata_path(self, run_id: str, *, candidate_id: str = DEFAULT_CANDIDATE_ID) -> Path:
        safe_id = self._sanitize_run_id(run_id)
        roots = self._candidate_roots(candidate_id)
        for root in roots:
            candidate = root / f"{safe_id}.json"
            if candidate.exists():
                return candidate
        return roots[0] / f"{safe_id}.json"

    def resolve_run_artifact_path(
        self,
        run_id: str,
        relative_path: str,
        *,
        candidate_id: str = DEFAULT_CANDIDATE_ID,
    ) -> Path:
        run_dir = self.resolve_run_dir(run_id, candidate_id=candidate_id)
        candidate = (run_dir / relative_path).resolve()
        run_root = run_dir.resolve()
        if run_root not in candidate.parents and candidate != run_root:
            raise ValueError("Invalid artifact path")
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


__all__ = ["FileSystemRunRepository", "RunRepository"]
