#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }
note() { echo "[INFO] $*"; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

usage() {
  cat <<'USAGE'
Usage:
  scripts/control_plane/publish_bundle.sh --bucket <bucket> --prefix <prefix> [--source-dir <dir>] [--image-ref-digest <repo@sha256:...>] [--receipt-dir <dir>] [--dry-run]

Behavior:
  - Builds deterministic control-plane bundle with candidates/ alerts/ providers/ scoring/ + manifest.json.
  - Uploads bundle and current pointer unless --dry-run.
USAGE
}

BUCKET=""
PREFIX=""
SOURCE_DIR=""
IMAGE_REF_DIGEST="${IMAGE_REF_DIGEST:-}"
RECEIPT_DIR=""
DRY_RUN=0
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
AWS_PAGER=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bucket) BUCKET="${2:-}"; shift 2 ;;
    --prefix) PREFIX="${2:-}"; shift 2 ;;
    --source-dir) SOURCE_DIR="${2:-}"; shift 2 ;;
    --image-ref-digest) IMAGE_REF_DIGEST="${2:-}"; shift 2 ;;
    --receipt-dir) RECEIPT_DIR="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown arg: $1" ;;
  esac
done

[[ -n "${BUCKET}" ]] || fail "--bucket is required"
[[ -n "${PREFIX}" ]] || fail "--prefix is required"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"
command -v git >/dev/null 2>&1 || fail "git is required"

if [[ "${DRY_RUN}" -ne 1 ]]; then
  command -v aws >/dev/null 2>&1 || fail "aws is required"
fi

export AWS_REGION AWS_DEFAULT_REGION AWS_PAGER

if [[ -z "${RECEIPT_DIR}" ]]; then
  RECEIPT_DIR="/tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/control-plane-publish-$(date -u +%Y%m%dT%H%M%SZ)"
fi
mkdir -p "${RECEIPT_DIR}" || fail "cannot create receipt dir: ${RECEIPT_DIR}"
touch "${RECEIPT_DIR}/.write-test" || fail "receipt dir not writable: ${RECEIPT_DIR}"

ACTUAL_ACCOUNT_ID="dry-run"
if [[ "${DRY_RUN}" -ne 1 ]]; then
  ACTUAL_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
  [[ "${ACTUAL_ACCOUNT_ID}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "AWS account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${ACTUAL_ACCOUNT_ID}"
fi

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
GIT_SHA="$(git -C "${ROOT_DIR}" rev-parse HEAD)"
SHORT_SHA="$(git -C "${ROOT_DIR}" rev-parse --short=12 HEAD)"
STAGING_ROOT="$(mktemp -d)"
trap 'rm -rf "${STAGING_ROOT}"' EXIT
STAGING_DIR="${STAGING_ROOT}/control-plane"
mkdir -p "${STAGING_DIR}"/{candidates,alerts,providers,scoring}

if [[ -n "${SOURCE_DIR}" ]]; then
  [[ -d "${SOURCE_DIR}" ]] || fail "source dir not found: ${SOURCE_DIR}"
  for section in candidates alerts providers scoring; do
    [[ -d "${SOURCE_DIR}/${section}" ]] || fail "source dir missing required section: ${SOURCE_DIR}/${section}"
  done
  python3 - "${SOURCE_DIR}" "${STAGING_DIR}" <<'PY'
import pathlib
import shutil
import sys

src = pathlib.Path(sys.argv[1])
stage = pathlib.Path(sys.argv[2])
for section in ("candidates", "alerts", "providers", "scoring"):
    target = stage / section
    for path in sorted((src / section).rglob("*")):
        if path.is_dir():
            continue
        rel = path.relative_to(src / section)
        out = target / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, out)
PY
else
  CANDIDATE_REGISTRY="${ROOT_DIR}/state/candidates/registry.json"
  PROVIDERS_FILE="${ROOT_DIR}/config/providers.json"
  SCORING_FILE="${ROOT_DIR}/config/scoring.v1.json"
  ALERTS_FILE="${ROOT_DIR}/config/alerts.json"
  LOCAL_PROFILE_FALLBACK="${ROOT_DIR}/data/candidate_profile.json"

  [[ -f "${CANDIDATE_REGISTRY}" ]] || fail "missing required candidate registry: ${CANDIDATE_REGISTRY}"
  [[ -f "${PROVIDERS_FILE}" ]] || fail "missing required providers config: ${PROVIDERS_FILE}"
  [[ -f "${SCORING_FILE}" ]] || fail "missing required scoring config: ${SCORING_FILE}"
  [[ -f "${ALERTS_FILE}" ]] || fail "missing required alerts config: ${ALERTS_FILE}"

  cp "${CANDIDATE_REGISTRY}" "${STAGING_DIR}/candidates/registry.json"
  cp "${PROVIDERS_FILE}" "${STAGING_DIR}/providers/providers.json"
  cp "${SCORING_FILE}" "${STAGING_DIR}/scoring/scoring.v1.json"
  cp "${ALERTS_FILE}" "${STAGING_DIR}/alerts/alerts.json"

  python3 - "${ROOT_DIR}" "${CANDIDATE_REGISTRY}" "${STAGING_DIR}" "${LOCAL_PROFILE_FALLBACK}" <<'PY'
import json
import pathlib
import shutil
import sys

root = pathlib.Path(sys.argv[1])
registry_path = pathlib.Path(sys.argv[2])
staging_dir = pathlib.Path(sys.argv[3])
local_fallback = pathlib.Path(sys.argv[4])

registry = json.loads(registry_path.read_text(encoding="utf-8"))
entries = registry.get("candidates", [])
if not isinstance(entries, list) or not entries:
    raise SystemExit("candidate registry has no candidates")

for entry in entries:
    if not isinstance(entry, dict):
        raise SystemExit("candidate registry entry is not an object")
    candidate_id = str(entry.get("candidate_id", "")).strip()
    profile_rel = str(entry.get("profile_path", "")).strip()
    if not candidate_id or not profile_rel:
        raise SystemExit(f"invalid candidate entry: {entry}")

    rel = pathlib.PurePosixPath(profile_rel)
    if str(rel).startswith("candidates/"):
        rel = pathlib.PurePosixPath(*rel.parts[1:])
    source = root / "state" / "candidates" / rel

    if not source.exists() and candidate_id == "local" and local_fallback.exists():
        source = local_fallback

    if not source.exists():
        raise SystemExit(f"missing candidate profile for {candidate_id}: {source}")

    out = staging_dir / "candidates" / candidate_id / "candidate_profile.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, out)
PY
fi

python3 - "${STAGING_DIR}" "${GIT_SHA}" "${IMAGE_REF_DIGEST}" "${TIMESTAMP}" <<'PY'
import hashlib
import json
import pathlib
import sys

staging_dir = pathlib.Path(sys.argv[1])
git_sha = sys.argv[2]
image_ref_digest = sys.argv[3]
created_at = sys.argv[4]

required = ["candidates", "alerts", "providers", "scoring"]
for section in required:
    section_dir = staging_dir / section
    if not section_dir.exists():
        raise SystemExit(f"missing section dir: {section_dir}")
    files = sorted(p for p in section_dir.rglob("*") if p.is_file())
    if not files:
        raise SystemExit(f"section has no files: {section_dir}")

files_payload = []
for path in sorted(p for p in staging_dir.rglob("*") if p.is_file() and p.name != "manifest.json"):
    rel = path.relative_to(staging_dir).as_posix()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    files_payload.append({"path": rel, "sha256": digest, "bytes": path.stat().st_size})

schema_versions = {
    "candidate_registry": None,
    "alerts": None,
    "providers": None,
    "scoring": None,
}

candidate_registry = staging_dir / "candidates" / "registry.json"
if candidate_registry.exists():
    try:
        schema_versions["candidate_registry"] = json.loads(candidate_registry.read_text(encoding="utf-8")).get("schema_version")
    except Exception:
        schema_versions["candidate_registry"] = None

for key, candidate in (
    ("alerts", sorted((staging_dir / "alerts").glob("*.json"))),
    ("providers", sorted((staging_dir / "providers").glob("*.json"))),
    ("scoring", sorted((staging_dir / "scoring").glob("*.json"))),
):
    if candidate:
        try:
            obj = json.loads(candidate[0].read_text(encoding="utf-8"))
            schema_versions[key] = obj.get("schema_version", obj.get("version"))
        except Exception:
            schema_versions[key] = None

manifest = {
    "schema_version": 1,
    "created_at": created_at,
    "git_sha": git_sha,
    "image_ref_digest": image_ref_digest,
    "supported_sections": required,
    "schema_versions": schema_versions,
    "files": files_payload,
}
(staging_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

BUNDLE_FILE="${RECEIPT_DIR}/control-plane-bundle-${TIMESTAMP}-${SHORT_SHA}.tar.gz"
python3 - "${STAGING_DIR}" "${BUNDLE_FILE}" <<'PY'
import gzip
import pathlib
import tarfile
import sys

src = pathlib.Path(sys.argv[1])
out = pathlib.Path(sys.argv[2])

files = sorted(p for p in src.rglob("*") if p.is_file())
with out.open("wb") as raw:
    with gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        with tarfile.open(fileobj=gz, mode="w") as tar:
            for path in files:
                rel = path.relative_to(src).as_posix()
                arc = f"control-plane/{rel}"
                info = tar.gettarinfo(str(path), arcname=arc)
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                info.mtime = 0
                info.mode = 0o644
                with path.open("rb") as f:
                    tar.addfile(info, f)
PY

BUNDLE_SHA256="$(python3 - "${BUNDLE_FILE}" <<'PY'
import hashlib
import pathlib
import sys
p = pathlib.Path(sys.argv[1])
h = hashlib.sha256()
with p.open('rb') as f:
    for chunk in iter(lambda: f.read(1024 * 1024), b''):
        h.update(chunk)
print(h.hexdigest())
PY
)"

BUNDLE_KEY="${PREFIX%/}/control-plane/bundles/${TIMESTAMP}-${SHORT_SHA}.tar.gz"
BUNDLE_URI="s3://${BUCKET}/${BUNDLE_KEY}"
CURRENT_KEY="${PREFIX%/}/control-plane/current.json"
CURRENT_URI="s3://${BUCKET}/${CURRENT_KEY}"

python3 - "${CURRENT_URI}" "${BUNDLE_URI}" "${BUNDLE_SHA256}" "${TIMESTAMP}" "${GIT_SHA}" "${IMAGE_REF_DIGEST}" "${RECEIPT_DIR}/current.json" <<'PY'
import json
import pathlib
import sys

current_uri, bundle_uri, bundle_sha, created_at, git_sha, image_ref_digest, out = sys.argv[1:]
payload = {
    "schema_version": 1,
    "current_uri": current_uri,
    "bundle_uri": bundle_uri,
    "bundle_sha256": bundle_sha,
    "created_at": created_at,
    "git_sha": git_sha,
    "image_ref_digest": image_ref_digest,
}
pathlib.Path(out).write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

cp "${STAGING_DIR}/manifest.json" "${RECEIPT_DIR}/manifest.json"
printf '%s\n' "${BUNDLE_SHA256}" > "${RECEIPT_DIR}/bundle.sha256"

if [[ "${DRY_RUN}" -eq 1 ]]; then
  note "dry-run enabled: skipping S3 upload"
else
  aws s3 cp "${BUNDLE_FILE}" "${BUNDLE_URI}" >/dev/null
  aws s3 cp "${RECEIPT_DIR}/current.json" "${CURRENT_URI}" >/dev/null
fi

cat > "${RECEIPT_DIR}/publish.summary.env" <<EOF_SUMMARY
BUNDLE_URI=${BUNDLE_URI}
BUNDLE_SHA256=${BUNDLE_SHA256}
CURRENT_URI=${CURRENT_URI}
MANIFEST_PATH=${RECEIPT_DIR}/manifest.json
BUNDLE_FILE=${BUNDLE_FILE}
DRY_RUN=${DRY_RUN}
RECEIPT_DIR=${RECEIPT_DIR}
EOF_SUMMARY

note "control-plane bundle publish complete"
echo "RECEIPT_DIR=${RECEIPT_DIR}"
echo "BUNDLE_URI=${BUNDLE_URI}"
echo "BUNDLE_SHA256=${BUNDLE_SHA256}"
echo "CURRENT_URI=${CURRENT_URI}"
