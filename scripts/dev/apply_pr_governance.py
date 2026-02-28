#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

PROVENANCE_LABELS = ("from-composer", "from-codex", "from-human")
TYPE_LABELS = ("type:feat", "type:fix", "type:chore", "type:docs", "type:refactor", "type:test")
AREA_LABELS = ("area:engine", "area:providers", "area:dr", "area:release", "area:infra", "area:docs", "area:unknown")
DOCS_OR_UNKNOWN_AREAS = {"area:docs", "area:unknown"}
TITLE_PROVENANCE_RE = re.compile(r"\[from-(composer|codex|human)\]", re.IGNORECASE)

REQUIRED_LABELS: dict[str, tuple[str, str]] = {
    "from-composer": ("5319E7", "PRs authored/executed via Composer flows"),
    "from-codex": ("1D76DB", "PRs authored/executed directly by Codex"),
    "from-human": ("0E8A16", "PRs authored directly by a human"),
    "type:feat": ("0E8A16", "Feature change"),
    "type:fix": ("D73A4A", "Bug fix"),
    "type:chore": ("6F42C1", "Maintenance or process change"),
    "type:docs": ("0075CA", "Documentation-only or docs-primary change"),
    "type:refactor": ("FBCA04", "Code structure change without behavior intent"),
    "type:test": ("C2E0C6", "Test-only change"),
    "area:engine": ("0052CC", "Engine/runtime/pipeline area"),
    "area:providers": ("5319E7", "Provider ingestion/policy area"),
    "area:dr": ("B60205", "Disaster recovery area"),
    "area:release": ("1D76DB", "Release and distribution area"),
    "area:infra": ("0366D6", "Infrastructure/tooling area"),
    "area:docs": ("0E8A16", "Docs-only area label"),
    "area:unknown": ("6A737D", "Fallback area when no specific domain applies"),
}

GOVERNANCE_LABELS = set(PROVENANCE_LABELS) | set(TYPE_LABELS) | set(AREA_LABELS)


@dataclass(frozen=True)
class PrTarget:
    pr_number: int
    milestone_title: Optional[str] = None
    provenance: Optional[str] = None
    type_label: Optional[str] = None
    areas: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class PrSummary:
    pr_number: int
    title: str
    milestone: Optional[str]
    labels: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


class GovernanceError(RuntimeError):
    """Raised when desired PR governance metadata is invalid or cannot be applied."""


def _run_cmd(cmd: list[str], *, stdin_text: Optional[str] = None) -> str:
    proc = subprocess.run(cmd, check=False, text=True, capture_output=True, input=stdin_text)
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "command failed"
        raise GovernanceError(f"{' '.join(cmd)}: {detail}")
    return proc.stdout


def _gh_api(endpoint: str, *, method: str = "GET", payload: Optional[dict[str, Any]] = None) -> Any:
    cmd = ["gh", "api", "--method", method, endpoint]
    stdin_text: Optional[str] = None
    if payload is not None:
        cmd.extend(["--input", "-"])
        stdin_text = json.dumps(payload, sort_keys=True)
    out = _run_cmd(cmd, stdin_text=stdin_text).strip()
    if not out:
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError as exc:  # pragma: no cover - defensive branch
        raise GovernanceError(f"non-json response for endpoint {endpoint}") from exc


def _detect_repo() -> str:
    out = _run_cmd(["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"]).strip()
    if not out or "/" not in out:
        raise GovernanceError("unable to determine repository (expected owner/repo from gh repo view)")
    return out


def _fetch_repo_labels(repo: str) -> dict[str, dict[str, Any]]:
    payload = _gh_api(f"/repos/{repo}/labels?per_page=100")
    if not isinstance(payload, list):
        raise GovernanceError("failed to load repository labels")
    labels: dict[str, dict[str, Any]] = {}
    for item in payload:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name:
                labels[name] = item
    return labels


def _ensure_required_labels(repo: str, *, dry_run: bool) -> None:
    existing = _fetch_repo_labels(repo)
    missing = [name for name in REQUIRED_LABELS if name not in existing]
    for name in missing:
        color, description = REQUIRED_LABELS[name]
        if dry_run:
            print(f"DRY-RUN create label: {name} color=#{color}")
            continue
        _gh_api(
            f"/repos/{repo}/labels",
            method="POST",
            payload={"name": name, "color": color, "description": description},
        )
        print(f"created label: {name}")


def _fetch_milestones(repo: str) -> dict[str, int]:
    payload = _gh_api(f"/repos/{repo}/milestones?state=all&per_page=100")
    if not isinstance(payload, list):
        raise GovernanceError("failed to load milestones")
    milestones: dict[str, int] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        number = item.get("number")
        if isinstance(title, str) and title and isinstance(number, int):
            milestones[title] = number
    return milestones


def _fetch_pr(repo: str, pr_number: int) -> dict[str, Any]:
    payload = _gh_api(f"/repos/{repo}/pulls/{pr_number}")
    if not isinstance(payload, dict):
        raise GovernanceError(f"failed to load PR #{pr_number}")
    return payload


def _labels_from_pr(pr_payload: dict[str, Any]) -> list[str]:
    labels: list[str] = []
    for item in pr_payload.get("labels") or []:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name:
                labels.append(name)
    return labels


def _normalize_target(raw: PrTarget, *, verify_only: bool) -> PrTarget:
    if raw.pr_number <= 0:
        raise GovernanceError(f"invalid pr number: {raw.pr_number}")

    areas = tuple(dict.fromkeys(raw.areas))
    for area in areas:
        if area not in AREA_LABELS:
            raise GovernanceError(f"invalid area label for PR #{raw.pr_number}: {area}")
    if "area:docs" in areas and len(areas) > 1:
        raise GovernanceError(f"PR #{raw.pr_number}: area:docs is docs-only and cannot be mixed with other areas")
    if "area:unknown" in areas and len(areas) > 1:
        raise GovernanceError(
            f"PR #{raw.pr_number}: area:unknown is fallback-only and cannot be mixed with other areas"
        )

    provenance = raw.provenance
    if provenance is not None and provenance not in PROVENANCE_LABELS:
        raise GovernanceError(f"invalid provenance label for PR #{raw.pr_number}: {provenance}")

    type_label = raw.type_label
    if type_label is not None and type_label not in TYPE_LABELS:
        raise GovernanceError(f"invalid type label for PR #{raw.pr_number}: {type_label}")

    if not verify_only:
        if not raw.milestone_title:
            raise GovernanceError(f"PR #{raw.pr_number}: milestone is required")
        if provenance is None:
            raise GovernanceError(f"PR #{raw.pr_number}: provenance label is required")
        if type_label is None:
            raise GovernanceError(f"PR #{raw.pr_number}: type label is required")
        if not areas:
            raise GovernanceError(f"PR #{raw.pr_number}: at least one area label is required")

    return PrTarget(
        pr_number=raw.pr_number,
        milestone_title=raw.milestone_title,
        provenance=provenance,
        type_label=type_label,
        areas=areas,
    )


def _parse_cli_groups(tokens: list[str]) -> list[PrTarget]:
    specs: list[PrTarget] = []
    current: Optional[dict[str, Any]] = None
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if token not in {"--pr", "--milestone", "--provenance", "--type", "--area"}:
            raise GovernanceError(f"unknown argument: {token}")
        if idx + 1 >= len(tokens):
            raise GovernanceError(f"missing value for {token}")
        value = tokens[idx + 1]
        idx += 2

        if token == "--pr":
            if current is not None:
                specs.append(
                    PrTarget(
                        pr_number=current["pr_number"],
                        milestone_title=current["milestone_title"],
                        provenance=current["provenance"],
                        type_label=current["type_label"],
                        areas=tuple(current["areas"]),
                    )
                )
            try:
                pr_number = int(value)
            except ValueError as exc:
                raise GovernanceError(f"invalid --pr value: {value}") from exc
            current = {
                "pr_number": pr_number,
                "milestone_title": None,
                "provenance": None,
                "type_label": None,
                "areas": [],
            }
            continue

        if current is None:
            raise GovernanceError(f"{token} must appear after --pr")
        if token == "--milestone":
            if current["milestone_title"] is not None:
                raise GovernanceError(f"duplicate --milestone for PR #{current['pr_number']}")
            current["milestone_title"] = value
        elif token == "--provenance":
            if current["provenance"] is not None:
                raise GovernanceError(f"duplicate --provenance for PR #{current['pr_number']}")
            current["provenance"] = value
        elif token == "--type":
            if current["type_label"] is not None:
                raise GovernanceError(f"duplicate --type for PR #{current['pr_number']}")
            current["type_label"] = value
        elif token == "--area":
            current["areas"].append(value)

    if current is not None:
        specs.append(
            PrTarget(
                pr_number=current["pr_number"],
                milestone_title=current["milestone_title"],
                provenance=current["provenance"],
                type_label=current["type_label"],
                areas=tuple(current["areas"]),
            )
        )
    return specs


def _load_config(path: Path) -> list[PrTarget]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceError(f"failed to read config json at {path}") from exc

    items: list[Any]
    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("prs"), list):
        items = payload["prs"]
    else:
        raise GovernanceError("config json must be either a list or an object with key 'prs'")

    specs: list[PrTarget] = []
    for item in items:
        if isinstance(item, int):
            specs.append(PrTarget(pr_number=item))
            continue
        if not isinstance(item, dict):
            raise GovernanceError("each config entry must be an object or integer PR number")
        pr_raw = item.get("pr", item.get("number"))
        if not isinstance(pr_raw, int):
            raise GovernanceError("each config entry requires integer field 'pr'")
        areas_raw = item.get("areas", item.get("area", []))
        if isinstance(areas_raw, str):
            areas = (areas_raw,)
        elif isinstance(areas_raw, list):
            areas = tuple(str(x) for x in areas_raw)
        else:
            raise GovernanceError(f"PR #{pr_raw}: area/areas must be string or list")
        specs.append(
            PrTarget(
                pr_number=pr_raw,
                milestone_title=item.get("milestone"),
                provenance=item.get("provenance"),
                type_label=item.get("type"),
                areas=areas,
            )
        )
    return specs


def _defaults_for_hardening_epoch(milestones: dict[str, int]) -> list[PrTarget]:
    docs_title = "Docs & Governance"
    if docs_title in milestones:
        docs_milestone = docs_title
    else:
        docs_milestone = "M22"
        print("warning: milestone 'Docs & Governance' not found; using fallback 'M22' for PR #255")
    return [
        PrTarget(252, "M22", "from-codex", "type:fix", ("area:engine",)),
        PrTarget(253, "M22", "from-codex", "type:fix", ("area:dr",)),
        PrTarget(254, "M22", "from-codex", "type:fix", ("area:engine",)),
        PrTarget(255, docs_milestone, "from-codex", "type:docs", ("area:docs",)),
    ]


def _governance_errors(*, title: str, labels: list[str], milestone: Optional[str]) -> list[str]:
    errors: list[str] = []
    provenance = [label for label in labels if label in PROVENANCE_LABELS]
    type_labels = [label for label in labels if label.startswith("type:")]
    area_labels = [label for label in labels if label.startswith("area:")]

    if TITLE_PROVENANCE_RE.search(title or ""):
        errors.append("title contains forbidden provenance marker ([from-*])")
    if len(provenance) != 1:
        errors.append(f"provenance label count must be 1 (found {len(provenance)})")
    if len(type_labels) != 1:
        errors.append(f"type label count must be 1 (found {len(type_labels)})")
    if len(area_labels) < 1:
        errors.append("at least one area:* label is required")
    non_docs_areas = [label for label in area_labels if label not in DOCS_OR_UNKNOWN_AREAS]
    if "area:docs" in area_labels and non_docs_areas:
        errors.append("area:docs must not be combined with another specific area:* label")
    if "area:unknown" in area_labels and len(area_labels) > 1:
        errors.append("area:unknown is fallback-only and must not be combined with other area labels")
    if not milestone:
        errors.append("milestone is required")
    return errors


def _put_labels(repo: str, pr_number: int, labels: list[str], *, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY-RUN set labels on PR #{pr_number}: {labels}")
        return
    _gh_api(f"/repos/{repo}/issues/{pr_number}/labels", method="PUT", payload={"labels": labels})
    print(f"updated labels on PR #{pr_number}")


def _set_milestone(repo: str, pr_number: int, milestone_number: int, milestone_title: str, *, dry_run: bool) -> None:
    if dry_run:
        print(f"DRY-RUN set milestone on PR #{pr_number}: {milestone_title}")
        return
    _gh_api(
        f"/repos/{repo}/issues/{pr_number}",
        method="PATCH",
        payload={"milestone": milestone_number},
    )
    print(f"updated milestone on PR #{pr_number}: {milestone_title}")


def _apply_target(repo: str, target: PrTarget, milestones: dict[str, int], *, dry_run: bool) -> None:
    if not target.milestone_title:
        raise GovernanceError(f"PR #{target.pr_number}: milestone is required")
    milestone_number = milestones.get(target.milestone_title)
    if milestone_number is None:
        raise GovernanceError(
            f"PR #{target.pr_number}: milestone '{target.milestone_title}' not found in repository milestones"
        )

    pr_payload = _fetch_pr(repo, target.pr_number)
    current_labels = _labels_from_pr(pr_payload)
    current_milestone = pr_payload.get("milestone")
    current_milestone_num = current_milestone.get("number") if isinstance(current_milestone, dict) else None

    desired_governance = {target.provenance or "", target.type_label or "", *target.areas}
    desired_governance.discard("")
    current_other = [label for label in current_labels if label not in GOVERNANCE_LABELS]
    final_labels = sorted(set(current_other) | desired_governance)

    if set(current_labels) != set(final_labels):
        _put_labels(repo, target.pr_number, final_labels, dry_run=dry_run)
    else:
        print(f"labels already compliant on PR #{target.pr_number}")

    if current_milestone_num != milestone_number:
        _set_milestone(repo, target.pr_number, milestone_number, target.milestone_title, dry_run=dry_run)
    else:
        print(f"milestone already set on PR #{target.pr_number}: {target.milestone_title}")


def _planned_state(repo: str, target: PrTarget, milestones: dict[str, int]) -> tuple[tuple[str, ...], str]:
    if not target.milestone_title:
        raise GovernanceError(f"PR #{target.pr_number}: milestone is required")
    if target.milestone_title not in milestones:
        raise GovernanceError(
            f"PR #{target.pr_number}: milestone '{target.milestone_title}' not found in repository milestones"
        )
    pr_payload = _fetch_pr(repo, target.pr_number)
    current_labels = _labels_from_pr(pr_payload)
    desired_governance = {target.provenance or "", target.type_label or "", *target.areas}
    desired_governance.discard("")
    current_other = [label for label in current_labels if label not in GOVERNANCE_LABELS]
    final_labels = tuple(sorted(set(current_other) | desired_governance))
    return final_labels, target.milestone_title


def _summarize_pr(repo: str, pr_number: int) -> PrSummary:
    pr_payload = _fetch_pr(repo, pr_number)
    title = str(pr_payload.get("title") or "")
    labels = sorted(_labels_from_pr(pr_payload))
    milestone = None
    milestone_payload = pr_payload.get("milestone")
    if isinstance(milestone_payload, dict):
        raw_title = milestone_payload.get("title")
        if isinstance(raw_title, str) and raw_title.strip():
            milestone = raw_title
    errors = _governance_errors(title=title, labels=labels, milestone=milestone)
    return PrSummary(pr_number=pr_number, title=title, milestone=milestone, labels=tuple(labels), errors=tuple(errors))


def _summarize_projected_pr(
    repo: str,
    pr_number: int,
    *,
    labels: tuple[str, ...],
    milestone: str,
) -> PrSummary:
    pr_payload = _fetch_pr(repo, pr_number)
    title = str(pr_payload.get("title") or "")
    sorted_labels = tuple(sorted(labels))
    errors = _governance_errors(title=title, labels=list(sorted_labels), milestone=milestone)
    return PrSummary(
        pr_number=pr_number,
        title=title,
        milestone=milestone,
        labels=sorted_labels,
        errors=tuple(errors),
    )


def _print_summary(summary: PrSummary) -> None:
    status = "PASS" if summary.ok else "FAIL"
    milestone = summary.milestone or "(none)"
    labels = ", ".join(summary.labels) if summary.labels else "(none)"
    print(f"PR #{summary.pr_number}: {status}")
    print(f"  milestone: {milestone}")
    print(f"  labels: {labels}")
    if summary.errors:
        for err in summary.errors:
            print(f"  error: {err}")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Apply and verify SignalCraft PR governance metadata via GitHub API (through gh CLI)."
    )
    parser.add_argument("--repo", help="owner/repo override (default: current gh repo)")
    parser.add_argument("--config-json", type=Path, help="JSON file describing PR governance targets")
    parser.add_argument(
        "--apply-defaults-for-hardening-epoch",
        action="store_true",
        help="Apply defaults for PRs 252-255 with deterministic milestone fallback behavior",
    )
    parser.add_argument("--verify-only", action="store_true", help="Only verify governance on selected PRs")
    parser.add_argument("--dry-run", action="store_true", help="Print intended writes without mutating GitHub state")
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = _build_parser()
    args, extra = parser.parse_known_args(argv)

    has_cli_groups = "--pr" in extra
    if args.apply_defaults_for_hardening_epoch and (args.config_json or has_cli_groups):
        raise GovernanceError("--apply-defaults-for-hardening-epoch cannot be combined with --config-json or --pr")
    if args.config_json and has_cli_groups:
        raise GovernanceError("--config-json cannot be combined with --pr group arguments")

    repo = args.repo or _detect_repo()
    milestones = _fetch_milestones(repo)

    if args.apply_defaults_for_hardening_epoch:
        targets = _defaults_for_hardening_epoch(milestones)
    elif args.config_json:
        targets = _load_config(args.config_json)
    else:
        targets = _parse_cli_groups(extra)

    if not targets:
        raise GovernanceError(
            "no PR targets provided (use --config-json, --pr groups, or --apply-defaults-for-hardening-epoch)"
        )

    normalized: list[PrTarget] = []
    seen_prs: set[int] = set()
    for target in targets:
        clean = _normalize_target(target, verify_only=args.verify_only)
        if clean.pr_number in seen_prs:
            raise GovernanceError(f"duplicate PR target provided: #{clean.pr_number}")
        seen_prs.add(clean.pr_number)
        normalized.append(clean)

    projected: dict[int, tuple[tuple[str, ...], str]] = {}
    if not args.verify_only:
        _ensure_required_labels(repo, dry_run=args.dry_run)
        for target in normalized:
            projected[target.pr_number] = _planned_state(repo, target, milestones)
            _apply_target(repo, target, milestones, dry_run=args.dry_run)

    print("verification summary")
    failed = False
    for target in normalized:
        if args.dry_run and not args.verify_only:
            labels, milestone = projected[target.pr_number]
            summary = _summarize_projected_pr(repo, target.pr_number, labels=labels, milestone=milestone)
        else:
            summary = _summarize_pr(repo, target.pr_number)
        _print_summary(summary)
        if not summary.ok:
            failed = True

    if failed:
        return 1
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GovernanceError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2)
