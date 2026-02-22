#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }
note() { echo "[INFO] $*"; }

usage() {
  cat <<'USAGE'
Usage:
  scripts/control_plane/apply_bundle_k8s.sh --bundle-dir <dir> --namespace <ns> [--kubeconfig <path>] [--render-only] [--output-yaml <path>] [--receipt-dir <dir>]
USAGE
}

BUNDLE_DIR=""
NAMESPACE=""
KUBECONFIG_PATH=""
RENDER_ONLY=0
OUTPUT_YAML=""
RECEIPT_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --bundle-dir) BUNDLE_DIR="${2:-}"; shift 2 ;;
    --namespace) NAMESPACE="${2:-}"; shift 2 ;;
    --kubeconfig) KUBECONFIG_PATH="${2:-}"; shift 2 ;;
    --render-only) RENDER_ONLY=1; shift ;;
    --output-yaml) OUTPUT_YAML="${2:-}"; shift 2 ;;
    --receipt-dir) RECEIPT_DIR="${2:-}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) fail "unknown arg: $1" ;;
  esac
done

[[ -n "${BUNDLE_DIR}" ]] || fail "--bundle-dir is required"
[[ -n "${NAMESPACE}" ]] || fail "--namespace is required"
[[ -d "${BUNDLE_DIR}" ]] || fail "bundle dir not found: ${BUNDLE_DIR}"
[[ -f "${BUNDLE_DIR}/manifest.json" ]] || fail "bundle manifest missing: ${BUNDLE_DIR}/manifest.json"
for section in candidates alerts providers scoring; do
  [[ -d "${BUNDLE_DIR}/${section}" ]] || fail "bundle section missing: ${BUNDLE_DIR}/${section}"
done

command -v python3 >/dev/null 2>&1 || fail "python3 is required"
if [[ "${RENDER_ONLY}" -eq 0 ]]; then
  command -v kubectl >/dev/null 2>&1 || fail "kubectl is required when not using --render-only"
  [[ -n "${KUBECONFIG_PATH}" ]] || fail "--kubeconfig is required when not using --render-only"
fi

if [[ -z "${RECEIPT_DIR}" ]]; then
  RECEIPT_DIR="/tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/control-plane-apply-$(date -u +%Y%m%dT%H%M%SZ)"
fi
mkdir -p "${RECEIPT_DIR}" || fail "cannot create receipt dir: ${RECEIPT_DIR}"
touch "${RECEIPT_DIR}/.write-test" || fail "receipt dir not writable: ${RECEIPT_DIR}"

if [[ -z "${OUTPUT_YAML}" ]]; then
  OUTPUT_YAML="${RECEIPT_DIR}/control-plane.configmaps.yaml"
fi

python3 - "${BUNDLE_DIR}" "${NAMESPACE}" "${OUTPUT_YAML}" "${RECEIPT_DIR}/apply.summary.json" "${RECEIPT_DIR}" <<'PY'
import hashlib
import json
import pathlib
import sys

bundle = pathlib.Path(sys.argv[1])
namespace = sys.argv[2]
out_yaml = pathlib.Path(sys.argv[3])
summary_path = pathlib.Path(sys.argv[4])
receipt_dir = pathlib.Path(sys.argv[5])

manifest_path = bundle / "manifest.json"
manifest_obj = json.loads(manifest_path.read_text(encoding="utf-8"))
manifest_hash = hashlib.sha256(manifest_path.read_bytes()).hexdigest()

bundle_sha_file = bundle.parent.parent / "bundle.sha256"
bundle_sha = bundle_sha_file.read_text(encoding="utf-8").strip() if bundle_sha_file.exists() else ""

sections = ["candidates", "alerts", "providers", "scoring"]
section_counts = {}

def emit_configmap(name: str, data: dict[str, str]) -> str:
    lines = [
        "apiVersion: v1",
        "kind: ConfigMap",
        "metadata:",
        f"  name: {name}",
        f"  namespace: {namespace}",
        "data:",
    ]
    for key in sorted(data):
        lines.append(f"  {key}: |-" )
        payload = data[key].splitlines()
        if not payload:
            lines.append("    ")
        else:
            for line in payload:
                lines.append(f"    {line}")
    return "\n".join(lines) + "\n"

documents = []
for section in sections:
    section_dir = bundle / section
    files = sorted(p for p in section_dir.rglob("*.json") if p.is_file())
    if not files:
        raise SystemExit(f"section has no json files: {section}")
    data = {}
    for p in files:
        rel = p.relative_to(section_dir).as_posix()
        key = rel.replace("/", "__")
        data[key] = p.read_text(encoding="utf-8")
    documents.append(emit_configmap(f"jobintel-control-plane-{section}", data))
    if section == "candidates":
        section_counts[section] = sum(1 for p in files if p.name != "registry.json")
    else:
        section_counts[section] = len(files)

yaml_text = "---\n" + "---\n".join(documents)
out_yaml.write_text(yaml_text, encoding="utf-8")

summary = {
    "schema_version": 1,
    "namespace": namespace,
    "bundle_dir": str(bundle),
    "manifest_sha256": manifest_hash,
    "bundle_sha256": bundle_sha,
    "bundle_created_at": manifest_obj.get("created_at", ""),
    "bundle_git_sha": manifest_obj.get("git_sha", ""),
    "image_ref_digest": manifest_obj.get("image_ref_digest", ""),
    "candidate_count": section_counts.get("candidates", 0),
    "alert_count": section_counts.get("alerts", 0),
    "provider_count": section_counts.get("providers", 0),
    "scoring_count": section_counts.get("scoring", 0),
    "generated_yaml": str(out_yaml),
    "receipt_dir": str(receipt_dir),
}
summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY

if [[ "${RENDER_ONLY}" -eq 0 ]]; then
  KUBECONFIG="${KUBECONFIG_PATH}" kubectl apply -f "${OUTPUT_YAML}" > "${RECEIPT_DIR}/apply.kubectl.log"
  note "applied control-plane ConfigMaps to namespace=${NAMESPACE}"
else
  note "render-only mode: generated ${OUTPUT_YAML}"
fi

echo "RECEIPT_DIR=${RECEIPT_DIR}"
echo "OUTPUT_YAML=${OUTPUT_YAML}"
echo "SUMMARY_JSON=${RECEIPT_DIR}/apply.summary.json"
