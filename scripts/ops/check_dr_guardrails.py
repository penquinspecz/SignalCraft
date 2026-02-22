#!/usr/bin/env python3
"""Static DR guardrail checks for CI and local preflight."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CheckResult:
    ok: bool
    message: str


ROOT = Path(__file__).resolve().parents[2]


def _read(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"missing required file: {path}")
    return path.read_text(encoding="utf-8")


def _check_backend_present() -> CheckResult:
    path = ROOT / "ops/dr/terraform/backend.tf"
    content = _read(path)
    if re.search(r'backend\s+"s3"\s*\{', content):
        return CheckResult(True, f"backend_s3_present path={path}")
    return CheckResult(False, f"backend_s3_missing path={path}")


def _extract_variable_default(content: str, var_name: str) -> str | None:
    pat = re.compile(
        rf'variable\s+"{re.escape(var_name)}"\s*\{{(?P<body>.*?)\}}',
        re.DOTALL,
    )
    m = pat.search(content)
    if not m:
        return None
    body = m.group("body")
    dm = re.search(r"default\s*=\s*(?P<value>.+)", body)
    if not dm:
        return None
    value = dm.group("value").strip()
    value = value.split("#", 1)[0].strip()
    if value.startswith('"') and '"' in value[1:]:
        value = value[1 : value[1:].index('"') + 1]
    return value.strip('"')


def _check_enable_triggers_default_false() -> CheckResult:
    path = ROOT / "ops/dr/orchestrator/variables.tf"
    content = _read(path)
    default = _extract_variable_default(content, "enable_triggers")
    if default is None:
        return CheckResult(False, f"enable_triggers_default_missing path={path}")
    if default == "false":
        return CheckResult(True, f"enable_triggers_default_false path={path}")
    return CheckResult(False, f"enable_triggers_default_not_false value={default} path={path}")


def _check_arm_instance_defaults(allow_non_arm: bool) -> list[CheckResult]:
    checks: list[tuple[Path, str]] = [
        (ROOT / "ops/dr/terraform/variables.tf", "instance_type"),
        (ROOT / "ops/dr/orchestrator/variables.tf", "dr_instance_type"),
    ]
    out: list[CheckResult] = []
    for path, var_name in checks:
        content = _read(path)
        default = _extract_variable_default(content, var_name)
        if default is None:
            out.append(CheckResult(False, f"{var_name}_default_missing path={path}"))
            continue
        if re.match(r"^t4g\.[A-Za-z0-9]+$", default):
            out.append(CheckResult(True, f"{var_name}_arm_default_ok value={default} path={path}"))
            continue
        if allow_non_arm:
            out.append(CheckResult(True, f"{var_name}_non_arm_allowed_by_override value={default} path={path}"))
        else:
            out.append(
                CheckResult(
                    False,
                    f"{var_name}_must_be_t4g_default value={default} path={path} use --allow-non-arm-instance-type to override",
                )
            )
    return out


def _check_no_hardcoded_ami_ids() -> list[CheckResult]:
    tf_files = sorted((ROOT / "ops/dr").rglob("*.tf"))
    bad: list[str] = []
    pat = re.compile(r"\bami-[0-9a-fA-F]{8,17}\b")
    for tf in tf_files:
        content = tf.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), start=1):
            if pat.search(line):
                bad.append(f"{tf}:{i}:{line.strip()}")
    if bad:
        return [CheckResult(False, f"hardcoded_ami_ids_found count={len(bad)}"), *[CheckResult(False, b) for b in bad]]
    return [CheckResult(True, "hardcoded_ami_ids_none_found")]


def _check_no_unpinned_dr_manifest_images() -> list[CheckResult]:
    manifest_files = sorted(list((ROOT / "ops/dr").rglob("*.yaml")) + list((ROOT / "ops/dr").rglob("*.yml")))
    image_pat = re.compile(r"^\s*image:\s*(?P<value>\S+)\s*$")
    violations: list[str] = []
    scanned = 0
    for path in manifest_files:
        content = path.read_text(encoding="utf-8")
        for i, line in enumerate(content.splitlines(), start=1):
            m = image_pat.match(line)
            if not m:
                continue
            scanned += 1
            value = m.group("value").strip().strip('"').strip("'")
            # Allowed: digest-pinned refs and templated/runtime-provided refs.
            if "@sha256:" in value:
                continue
            if "${" in value or value.startswith("<") or value in {"", "IMAGE_REF"}:
                continue
            violations.append(f"{path}:{i}:{value}")
    if violations:
        return [
            CheckResult(False, f"unpinned_dr_manifest_images_found count={len(violations)} scanned={scanned}"),
            *[CheckResult(False, v) for v in violations],
        ]
    return [CheckResult(True, f"unpinned_dr_manifest_images_none_found scanned={scanned}")]


def _check_dr_ami_filter_arm64() -> CheckResult:
    path = ROOT / "ops/dr/terraform/main.tf"
    content = _read(path)
    if "ubuntu-noble-24.04-arm64-server-*" in content:
        return CheckResult(True, f"dr_ami_filter_arm64_present path={path}")
    return CheckResult(False, f"dr_ami_filter_arm64_missing path={path}")


def run(allow_non_arm: bool) -> int:
    results: list[CheckResult] = []
    results.append(_check_backend_present())
    results.append(_check_enable_triggers_default_false())
    results.extend(_check_arm_instance_defaults(allow_non_arm=allow_non_arm))
    results.extend(_check_no_hardcoded_ami_ids())
    results.extend(_check_no_unpinned_dr_manifest_images())
    results.append(_check_dr_ami_filter_arm64())

    failed = [r for r in results if not r.ok]
    for r in results:
        prefix = "PASS" if r.ok else "FAIL"
        print(f"{prefix}: {r.message}")
    return 1 if failed else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--allow-non-arm-instance-type",
        action="store_true",
        help="Allow non-t4g defaults for DR instance type checks",
    )
    args = ap.parse_args()
    return run(allow_non_arm=args.allow_non_arm_instance_type)


if __name__ == "__main__":
    raise SystemExit(main())
