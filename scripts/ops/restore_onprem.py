#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any

import boto3

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ji_engine.utils.time import utc_now_z  # noqa: E402
from scripts.ops.dr_contract import parse_s3_uri  # noqa: E402


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def _run_checked(cmd: list[str], *, env: dict[str, str] | None = None) -> None:
    result = subprocess.run(cmd, check=False, text=True, capture_output=True, env=env)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise RuntimeError(f"{' '.join(cmd)}: {detail}")


def _decrypt_file(src: Path, dst: Path, *, passphrase: str) -> None:
    env = os.environ.copy()
    env["JOBINTEL_BACKUP_PASSPHRASE_VALUE"] = passphrase
    _run_checked(
        [
            "openssl",
            "enc",
            "-d",
            "-aes-256-cbc",
            "-pbkdf2",
            "-iter",
            "200000",
            "-in",
            str(src),
            "-out",
            str(dst),
            "-pass",
            "env:JOBINTEL_BACKUP_PASSPHRASE_VALUE",
        ],
        env=env,
    )


def _sanitize_mode(mode: int, *, is_dir: bool) -> int:
    sanitized = mode & 0o777
    if sanitized:
        return sanitized
    return 0o755 if is_dir else 0o644


def _safe_extract_tar(tf: tarfile.TarFile, dest: Path) -> None:
    dest_resolved = dest.resolve()
    for member in tf.getmembers():
        member_name = str(member.name or "")
        posix_path = PurePosixPath(member_name)
        if posix_path.is_absolute():
            raise RuntimeError(f"unsafe tar member path: {member_name}")

        parts = [part for part in posix_path.parts if part not in ("", ".")]
        if not parts or any(part == ".." for part in parts):
            raise RuntimeError(f"unsafe tar member path: {member_name}")

        target = (dest_resolved / Path(*parts)).resolve()
        try:
            target.relative_to(dest_resolved)
        except ValueError as exc:
            raise RuntimeError(f"unsafe tar member path: {member_name}") from exc

        if member.isdir():
            target.mkdir(parents=True, exist_ok=True)
            os.chmod(target, _sanitize_mode(member.mode, is_dir=True))
            continue

        if not member.isfile():
            raise RuntimeError(f"unsafe tar member type: {member_name}")

        target.parent.mkdir(parents=True, exist_ok=True)
        src = tf.extractfile(member)
        if src is None:
            raise RuntimeError(f"failed to read tar member: {member_name}")
        with src, target.open("wb") as out:
            shutil.copyfileobj(src, out)
        os.chmod(target, _sanitize_mode(member.mode, is_dir=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Restore rehearsal from encrypted S3 backup and verify contents.")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--backup-uri", required=True)
    ap.add_argument("--restore-dir", required=True)
    ap.add_argument("--bundle-root", default="ops/proof/bundles")
    ap.add_argument("--passphrase-env", default="JOBINTEL_BACKUP_PASSPHRASE")
    ap.add_argument("--region", default=os.environ.get("AWS_REGION", ""))
    args = ap.parse_args(argv)

    passphrase = os.environ.get(args.passphrase_env, "")
    if not passphrase:
        print(f"Missing passphrase in env var {args.passphrase_env}", file=sys.stderr)
        return 2

    try:
        location = parse_s3_uri(args.backup_uri)
        bucket, prefix = location.bucket, location.key_prefix
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    bundle_dir = (REPO_ROOT / args.bundle_root / f"m4-{args.run_id}").resolve()
    bundle_dir.mkdir(parents=True, exist_ok=True)
    restore_log = bundle_dir / "restore.log"
    verify_log = bundle_dir / "restore_verify.log"

    def log(msg: str) -> None:
        line = f"{utc_now_z(seconds_precision=True)} {msg}"
        print(line)
        with restore_log.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    client = boto3.client("s3", region_name=args.region or None)
    restore_dir = Path(args.restore_dir).resolve()
    if restore_dir.exists():
        shutil.rmtree(restore_dir)
    restore_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix=f"jobintel-m4-restore-{args.run_id}-") as td:
        tmpdir = Path(td)
        required = ["metadata.json", "checksums.json", "db_backup.enc", "artifacts_backup.enc"]
        for name in required:
            s3_key = f"{prefix}/{name}"
            local = tmpdir / name
            log(f"downloading s3://{bucket}/{s3_key}")
            client.download_file(bucket, s3_key, str(local))

        metadata = json.loads((tmpdir / "metadata.json").read_text(encoding="utf-8"))
        checksums = json.loads((tmpdir / "checksums.json").read_text(encoding="utf-8"))
        verify_lines: list[str] = []
        for name in ("db_backup.enc", "artifacts_backup.enc"):
            got = _sha256_file(tmpdir / name)
            want = str(checksums.get(name, ""))
            ok = got == want
            verify_lines.append(f"sha256 {name}: expected={want} actual={got} ok={ok}")
            if not ok:
                raise RuntimeError(f"checksum mismatch for {name}")

        db_plain = tmpdir / "db_backup.out"
        artifacts_plain = tmpdir / "artifacts_backup.tar.gz"
        _decrypt_file(tmpdir / "db_backup.enc", db_plain, passphrase=passphrase)
        _decrypt_file(tmpdir / "artifacts_backup.enc", artifacts_plain, passphrase=passphrase)

        db_mode = str(metadata.get("db_mode", "unknown"))
        if db_mode == "pg_dump":
            db_target = restore_dir / "db" / "postgres.dump"
            db_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(db_plain, db_target)
            verify_lines.append(f"db restored: {db_target}")
        else:
            db_target_dir = restore_dir / "db_export"
            db_target_dir.mkdir(parents=True, exist_ok=True)
            with tarfile.open(db_plain, "r:gz") as tf:
                _safe_extract_tar(tf, db_target_dir)
            verify_lines.append(f"db alternative restored: {db_target_dir}")

        with tarfile.open(artifacts_plain, "r:gz") as tf:
            _safe_extract_tar(tf, restore_dir)

        state_ok = (restore_dir / "state").exists()
        proof_ok = (restore_dir / "ops" / "proof").exists()
        db_ok = (restore_dir / "db" / "postgres.dump").exists() or (
            restore_dir / "db_export" / "state" / "runs"
        ).exists()
        verify_lines.append(f"verify state_present={state_ok}")
        verify_lines.append(f"verify proof_present={proof_ok}")
        verify_lines.append(f"verify db_present={db_ok}")
        if not (state_ok and proof_ok and db_ok):
            raise RuntimeError("restore verification failed: missing DB or artifact outputs")

        verify_log.write_text("\n".join(verify_lines) + "\n", encoding="utf-8")
        receipt: dict[str, Any] = {
            "schema_version": 1,
            "run_id": args.run_id,
            "backup_uri": args.backup_uri,
            "restore_dir": str(restore_dir),
            "db_mode": db_mode,
            "restore_log": str(restore_log),
            "verify_log": str(verify_log),
            "verified": {
                "state_present": state_ok,
                "proof_present": proof_ok,
                "db_present": db_ok,
            },
        }
        receipt_path = bundle_dir / "restore_receipt.json"
        receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"restore_receipt={receipt_path}")
        print("restore_status=ok")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
