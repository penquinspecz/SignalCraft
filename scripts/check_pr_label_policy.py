#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

PROVENANCE_LABELS = {"from-composer", "from-codex"}


def required_label_for_branch(head_ref: str) -> str | None:
    if head_ref.startswith("composer/"):
        return "from-composer"
    if head_ref.startswith("codex/"):
        return "from-codex"
    return None


def labels_from_event_payload(payload: dict[str, Any]) -> set[str]:
    pr = payload.get("pull_request")
    if not isinstance(pr, dict):
        return set()
    labels = pr.get("labels")
    if not isinstance(labels, list):
        return set()
    out: set[str] = set()
    for item in labels:
        if isinstance(item, dict):
            name = item.get("name")
            if isinstance(name, str) and name.strip():
                out.add(name.strip())
    return out


def load_event_payload(event_path: str | None) -> dict[str, Any]:
    if not event_path:
        return {}
    path = Path(event_path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def evaluate_label_policy(head_ref: str, labels: set[str]) -> list[str]:
    issues: list[str] = []
    required = required_label_for_branch(head_ref)
    present_provenance = sorted(labels & PROVENANCE_LABELS)

    if required is None:
        return issues

    if required not in labels:
        issues.append(f"branch '{head_ref}' requires label '{required}'")

    wrong = sorted((labels & PROVENANCE_LABELS) - {required})
    for name in wrong:
        issues.append(f"branch '{head_ref}' should not carry provenance label '{name}'")

    if present_provenance and required in labels and not wrong:
        return issues
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check provenance label policy for pull requests.")
    parser.add_argument("--head-ref", default=os.getenv("GITHUB_HEAD_REF", ""))
    parser.add_argument("--event-path", default=os.getenv("GITHUB_EVENT_PATH", ""))
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero when policy issues are found.",
    )
    args = parser.parse_args(argv)

    payload = load_event_payload(args.event_path or None)
    head_ref = args.head_ref.strip()
    if not head_ref and isinstance(payload.get("pull_request"), dict):
        pr = payload["pull_request"]
        head = pr.get("head")
        if isinstance(head, dict):
            ref = head.get("ref")
            if isinstance(ref, str):
                head_ref = ref.strip()

    labels = labels_from_event_payload(payload)
    issues = evaluate_label_policy(head_ref, labels)

    print("Label policy check")
    print(f"- head_ref: {head_ref or '(unknown)'}")
    print(f"- labels: {', '.join(sorted(labels)) if labels else '(none)'}")

    if issues:
        print("LABEL_POLICY_WARNING:")
        for issue in issues:
            print(f"- {issue}")
        print("Guidance:")
        print("- composer/* branches should use label from-composer")
        print("- codex/* branches should use label from-codex")
        print("- fix labels in PR sidebar or via: gh pr edit <num> --add-label <label>")
        return 1 if args.strict else 0

    print("LABEL_POLICY_OK: no provenance label issues detected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
