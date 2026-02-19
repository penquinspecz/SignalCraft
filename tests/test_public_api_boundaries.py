from __future__ import annotations

import ast
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _target_files() -> list[Path]:
    root = _repo_root()
    targets: list[Path] = []
    targets.extend(sorted((root / "src" / "jobintel").rglob("*.py")))
    targets.extend(sorted((root / "src" / "ji_engine" / "dashboard").rglob("*.py")))
    return targets


def _is_forbidden_module(module_name: str) -> bool:
    return module_name == "ji_engine.pipeline" or module_name.startswith("ji_engine.pipeline.")


def _scan_file(path: Path) -> list[str]:
    rel = path.relative_to(_repo_root()).as_posix()
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                name = alias.name
                if _is_forbidden_module(name):
                    violations.append(f"{rel}:{node.lineno} imports forbidden module '{name}'")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden_module(module):
                violations.append(f"{rel}:{node.lineno} imports forbidden module '{module}'")
    return violations


def test_public_api_layers_do_not_import_pipeline_internals() -> None:
    violations: list[str] = []
    for path in _target_files():
        violations.extend(_scan_file(path))
    assert not violations, "\n".join(violations)
