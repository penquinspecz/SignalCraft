from __future__ import annotations

import ast
from pathlib import Path

FORBIDDEN_NAMES = {"DATA_DIR", "STATE_DIR", "RUN_METADATA_DIR"}


def _target_files() -> list[Path]:
    repo_root = Path(__file__).resolve().parents[1]
    pipeline_dir = repo_root / "src" / "ji_engine" / "pipeline"
    stages_dir = pipeline_dir / "stages"
    return [pipeline_dir / "runner.py", *sorted(stages_dir.glob("*.py"))]


def _scan_file(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "ji_engine.config":
            for alias in node.names:
                if alias.name in FORBIDDEN_NAMES:
                    violations.append(f"{path}: imports forbidden config constant `{alias.name}`")
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id in FORBIDDEN_NAMES:
            violations.append(f"{path}: references forbidden constant `{node.id}`")
        elif isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_NAMES:
            violations.append(f"{path}: references forbidden attribute `{node.attr}`")
    return violations


def test_pipeline_seam_forbidden_config_path_constants() -> None:
    violations: list[str] = []
    for path in _target_files():
        violations.extend(_scan_file(path))
    assert not violations, "\n".join(violations)
