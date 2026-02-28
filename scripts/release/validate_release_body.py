#!/usr/bin/env python3
"""Validate canonical SignalCraft release-body structure."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

SEMVER_RE = re.compile(r"^v(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)$")
IMAGE_REF_PIN_RE = re.compile(r"IMAGE_REF\s*:\s*`?[^`\s]+@sha256:[0-9a-f]{64}`?", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"\b(TODO|TBD)\b|fill\s*in", re.IGNORECASE)

PRODUCT_BASE_HEADINGS = [
    "Highlights",
    "What's Proven (Operator Reality Check)",
    "Images (Digest-pinned)",
    "Upgrade / Operational Notes",
    "Changes (categorized)",
    "Breaking Changes",
    "Known Issues",
    "Proof References",
    "Integrity",
]

PRODUCT_MAJOR_EXTRA_HEADINGS = [
    "Why this release exists",
    "Migration / Upgrade Guide",
    "Compatibility Matrix",
    "Deprecations Timeline",
]

MILESTONE_HEADINGS = [
    "Milestone Context",
    "What was exercised",
    "Execution Evidence",
    "Images (Digest-pinned)",
    "Guardrails/Determinism checks",
    "Outcome + Next steps",
    "Proof References",
]


class ValidationError(Exception):
    pass


def _run(cmd: list[str]) -> str:
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def _load_body(args: argparse.Namespace, tag: str | None, repo: str | None) -> str:
    if args.body:
        return args.body
    if args.body_file:
        return Path(args.body_file).read_text(encoding="utf-8")
    env_body = os.environ.get("RELEASE_BODY", "")
    if env_body:
        return env_body

    if not tag or not repo:
        raise ValidationError("release body not provided and tag/repo unavailable for GitHub lookup")

    try:
        return _run(["gh", "api", f"repos/{repo}/releases/tags/{tag}", "--jq", ".body"])
    except FileNotFoundError as exc:
        raise ValidationError("gh CLI is required when validating from GitHub release body") from exc
    except subprocess.CalledProcessError as exc:
        raise ValidationError(f"failed to fetch release body from GitHub: {exc.stderr.strip()}") from exc


def _infer_semver_level(tag: str, explicit: str) -> str:
    if explicit in {"major", "minor", "patch"}:
        return explicit

    match = SEMVER_RE.match(tag)
    if not match:
        return "minor"

    major = int(match.group("major"))
    minor = int(match.group("minor"))
    patch = int(match.group("patch"))

    if major > 0 and minor == 0 and patch == 0:
        return "major"
    if patch > 0:
        return "patch"
    return "minor"


def _heading_exists(body: str, heading: str) -> bool:
    pattern = re.compile(rf"(?im)^\s{{0,3}}#{{1,6}}\s+{re.escape(heading)}\s*$")
    return bool(pattern.search(body))


def _validate_headings(kind: str, semver_level: str, body: str) -> list[str]:
    errors: list[str] = []

    if kind == "product":
        required = list(PRODUCT_BASE_HEADINGS)
        if semver_level == "major":
            required.extend(PRODUCT_MAJOR_EXTRA_HEADINGS)
    else:
        required = list(MILESTONE_HEADINGS)

    for heading in required:
        if not _heading_exists(body, heading):
            errors.append(f"missing required heading: '{heading}'")

    return errors


def _validate_digest_image_ref(body: str, dev_mode: bool) -> list[str]:
    if dev_mode:
        return []
    if IMAGE_REF_PIN_RE.search(body):
        return []
    return ["digest-pinned IMAGE_REF is required (set DEV_MODE=1 only for explicit dev-only releases)"]


def _validate_placeholders(body: str) -> list[str]:
    if PLACEHOLDER_RE.search(body):
        return ["release body contains disallowed placeholder text (TODO/TBD/fill in)"]
    return []


def _value_for_key(body: str, key: str) -> str | None:
    pattern = re.compile(rf"(?im)^\s*[-*]\s+{re.escape(key)}\s*:\s*(.+)$")
    match = pattern.search(body)
    if not match:
        return None
    return match.group(1).strip()


def _validate_ci_evidence(body: str, require_ci_evidence: bool) -> list[str]:
    if not require_ci_evidence:
        return []

    errors: list[str] = []
    for key in ["CI workflow", "CI run ID", "CI workflow URL"]:
        value = _value_for_key(body, key)
        if value is None:
            errors.append(f"missing CI evidence field: '{key}'")
            continue
        if "Not recorded at tag time" in value:
            errors.append(f"CI evidence field '{key}' is present but unset")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-kind", choices=["product", "milestone"], default=None)
    parser.add_argument("--semver-level", choices=["auto", "major", "minor", "patch"], default="auto")
    parser.add_argument("--tag", default=None)
    parser.add_argument("--repo", default=None)
    parser.add_argument("--body", default=None)
    parser.add_argument("--body-file", default=None)
    parser.add_argument("--require-ci-evidence", action="store_true")
    parser.add_argument("--dev-mode", action="store_true")
    args = parser.parse_args()

    tag = args.tag or os.environ.get("RELEASE_TAG") or os.environ.get("GITHUB_REF_NAME") or ""
    repo = args.repo or os.environ.get("GITHUB_REPOSITORY")
    kind = args.release_kind or os.environ.get("RELEASE_KIND")
    if not kind:
        if tag.startswith("v"):
            kind = "product"
        elif tag.startswith("m"):
            kind = "milestone"
        else:
            print("FAIL: release kind is required (use --release-kind or RELEASE_KIND)")
            return 1

    dev_mode = args.dev_mode or os.environ.get("DEV_MODE", "").strip().lower() in {"1", "true", "yes"}

    try:
        body = _load_body(args, tag if tag else None, repo)
    except ValidationError as exc:
        print(f"FAIL: {exc}")
        return 1

    semver_level = _infer_semver_level(tag, args.semver_level) if kind == "product" else "minor"

    errors: list[str] = []
    errors.extend(_validate_headings(kind, semver_level, body))
    errors.extend(_validate_digest_image_ref(body, dev_mode))
    errors.extend(_validate_placeholders(body))
    errors.extend(_validate_ci_evidence(body, args.require_ci_evidence))

    if errors:
        print("FAIL: release body validation failed")
        for err in errors:
            print(f"- {err}")
        return 1

    mode = "dev" if dev_mode else "strict"
    print(f"PASS: release body valid kind={kind} semver_level={semver_level} mode={mode}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
