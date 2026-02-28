#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

PROVENANCE_LABELS = ("from-composer", "from-codex", "from-human")
TYPE_LABELS = ("type:feat", "type:fix", "type:chore", "type:docs", "type:refactor", "type:test")
AREA_ORDER = (
    "area:engine",
    "area:providers",
    "area:dr",
    "area:release",
    "area:infra",
    "area:docs",
    "area:unknown",
)


@dataclass(frozen=True)
class LabelDecision:
    provenance: str
    type_label: str
    areas: tuple[str, ...]

    @property
    def labels(self) -> tuple[str, ...]:
        return (self.provenance, self.type_label, *self.areas)


def _is_readme_path(path: str) -> bool:
    return re.search(r"(^|/)README[^/]*$", path, re.IGNORECASE) is not None


def _is_docs_path(path: str) -> bool:
    return path.startswith("docs/") or _is_readme_path(path)


def _is_engine_path(path: str) -> bool:
    return path.startswith("src/ji_engine/") or path.startswith("src/jobintel/") or path == "scripts/run_daily.py"


def _is_provider_path(path: str) -> bool:
    return path.startswith("src/ji_engine/providers/")


def _is_dr_path(path: str) -> bool:
    if path.startswith("scripts/ops/"):
        return True
    if not path.startswith("ops/"):
        return False
    if _is_infra_path(path):
        return False
    return True


def _is_release_path(path: str) -> bool:
    return path.startswith("scripts/release/")


def _is_infra_path(path: str) -> bool:
    return path.startswith("ops/aws/") or path.startswith("ops/k8s/") or path.startswith("ops/launchd/")


def _choose_provenance(head_ref: str) -> str:
    if head_ref.startswith("composer/"):
        return "from-composer"
    if head_ref.startswith("codex/"):
        return "from-codex"
    return "from-human"


def _choose_type(title: str, changed_files: list[str]) -> str:
    docs_title = re.match(r"^\s*docs(?:\(|:)", title, re.IGNORECASE) is not None
    fix_title = re.match(r"^\s*fix(?:\(|:)", title, re.IGNORECASE) is not None
    feat_title = re.match(r"^\s*feat(?:\(|:)", title, re.IGNORECASE) is not None
    docs_only = bool(changed_files) and all(_is_docs_path(path) for path in changed_files)

    if docs_only or docs_title:
        return "type:docs"
    if fix_title:
        return "type:fix"
    if feat_title:
        return "type:feat"
    return "type:chore"


def _choose_areas(changed_files: list[str]) -> tuple[str, ...]:
    areas: set[str] = set()
    if any(_is_docs_path(path) for path in changed_files):
        areas.add("area:docs")
    if any(_is_provider_path(path) for path in changed_files):
        areas.add("area:providers")
    if any(_is_engine_path(path) for path in changed_files):
        areas.add("area:engine")
    if any(_is_dr_path(path) for path in changed_files):
        areas.add("area:dr")
    if any(_is_release_path(path) for path in changed_files):
        areas.add("area:release")
    if any(_is_infra_path(path) for path in changed_files):
        areas.add("area:infra")

    if not areas:
        areas.add("area:unknown")

    non_docs = [label for label in areas if label not in {"area:docs", "area:unknown"}]
    if "area:docs" in areas and non_docs:
        areas.remove("area:docs")
    if "area:unknown" in areas and len(areas) > 1:
        areas.remove("area:unknown")

    order = {label: idx for idx, label in enumerate(AREA_ORDER)}
    return tuple(sorted(areas, key=lambda label: order.get(label, 999)))


def infer_labels(title: str, head_ref: str, changed_files: list[str]) -> LabelDecision:
    provenance = _choose_provenance(head_ref=head_ref)
    type_label = _choose_type(title=title, changed_files=changed_files)
    areas = _choose_areas(changed_files=changed_files)
    return LabelDecision(provenance=provenance, type_label=type_label, areas=areas)


def _load_changed_files_from_file(path: str) -> list[str]:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    out: list[str] = []
    for raw in lines:
        candidate = raw.strip()
        if not candidate or candidate.startswith("#"):
            continue
        out.append(candidate)
    return out


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        out.append(item)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Simulate deterministic PR governance label inference.")
    parser.add_argument("--title", required=True, help="Pull request title.")
    parser.add_argument("--head-ref", default="", help="Pull request head branch ref.")
    parser.add_argument(
        "--changed-file",
        action="append",
        default=[],
        help="Changed file path (repeatable).",
    )
    parser.add_argument(
        "--changed-files-file",
        help="Path to newline-delimited changed file list.",
    )
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON output.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    changed_files = list(args.changed_file or [])
    if args.changed_files_file:
        changed_files.extend(_load_changed_files_from_file(args.changed_files_file))
    changed_files = _dedupe_preserve_order(changed_files)

    decision = infer_labels(title=args.title, head_ref=args.head_ref, changed_files=changed_files)
    if args.json:
        payload = {
            "title": args.title,
            "head_ref": args.head_ref,
            "changed_files": changed_files,
            "provenance": decision.provenance,
            "type": decision.type_label,
            "areas": list(decision.areas),
            "labels": list(decision.labels),
        }
        print(json.dumps(payload, sort_keys=True))
        return 0

    print(f"title: {args.title}")
    print(f"head_ref: {args.head_ref or '(none)'}")
    print(f"changed_files: {len(changed_files)}")
    for path in changed_files:
        print(f"  - {path}")
    print(f"provenance: {decision.provenance}")
    print(f"type: {decision.type_label}")
    print(f"areas: {', '.join(decision.areas)}")
    print(f"labels: {', '.join(decision.labels)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
