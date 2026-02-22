#!/usr/bin/env bash
set -euo pipefail

fail() { echo "[FAIL] $*" >&2; exit 1; }
note() { echo "[INFO] $*"; }

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
NAMESPACE="${NAMESPACE:-jobintel}"
RUN_JOB="${RUN_JOB:-0}"
IMAGE_REF="${IMAGE_REF:-}"
CHECK_IMAGE_ONLY="${CHECK_IMAGE_ONLY:-0}"
CHECK_ARCH="${CHECK_ARCH:-arm64}"
CONTROL_PLANE_BUCKET="${CONTROL_PLANE_BUCKET:-${BUCKET:-}}"
CONTROL_PLANE_PREFIX="${CONTROL_PLANE_PREFIX:-${PREFIX:-}}"
ECR_PULL_SECRET_NAME="${ECR_PULL_SECRET_NAME:-ecr-pull}"
ECR_PULL_SECRET_SERVICE_ACCOUNT="${ECR_PULL_SECRET_SERVICE_ACCOUNT:-jobintel}"
ECR_REGISTRY="${ECR_REGISTRY:-}"
ENSURE_ECR_PULL_SECRET="${ENSURE_ECR_PULL_SECRET:-1}"
VALIDATE_REQUEST_CPU="${VALIDATE_REQUEST_CPU:-250m}"
VALIDATE_REQUEST_MEMORY="${VALIDATE_REQUEST_MEMORY:-512Mi}"
VALIDATE_LIMIT_CPU="${VALIDATE_LIMIT_CPU:-1}"
VALIDATE_LIMIT_MEMORY="${VALIDATE_LIMIT_MEMORY:-2Gi}"
VALIDATE_STARTUP_WINDOW_SECONDS="${VALIDATE_STARTUP_WINDOW_SECONDS:-180}"
VALIDATE_JOB_TIMEOUT_SECONDS="${VALIDATE_JOB_TIMEOUT_SECONDS:-2700}"
VALIDATE_SKIP_WORKLOAD_ASSUME="${VALIDATE_SKIP_WORKLOAD_ASSUME:-0}"

AWS_REGION="${AWS_REGION:-us-east-1}"
AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-${AWS_REGION}}"
AWS_PAGER=""
EXPECTED_ACCOUNT_ID="${EXPECTED_ACCOUNT_ID:-048622080012}"
RECEIPT_DIR="${RECEIPT_DIR:-/tmp/signalcraft-m19-phasea-20260221/ops/proof/bundles/m19-dr-validate-$(date -u +%Y%m%dT%H%M%SZ)}"
export AWS_REGION AWS_DEFAULT_REGION AWS_PAGER

command -v kubectl >/dev/null 2>&1 || fail "kubectl is required"
command -v grep >/dev/null 2>&1 || fail "grep is required (POSIX)"
command -v python3 >/dev/null 2>&1 || fail "python3 is required"

mkdir -p "${RECEIPT_DIR}" || fail "cannot create receipt dir: ${RECEIPT_DIR}"
touch "${RECEIPT_DIR}/.write-test" || fail "receipt dir not writable: ${RECEIPT_DIR}"

# Record deps preflight (grep used instead of rg for POSIX portability).
{
  echo "kubectl=$(command -v kubectl 2>/dev/null || echo 'missing')"
  echo "grep=$(command -v grep 2>/dev/null || echo 'missing')"
  echo "python3=$(command -v python3 2>/dev/null || echo 'missing')"
  echo "state_write_check=grep -q (replaces rg -q for portability)"
} > "${RECEIPT_DIR}/dr_validate.deps.env"

# Safe AWS env preflight receipt (no secret material).
{
  env | sort | grep '^AWS_' || true
} | while IFS='=' read -r key value; do
  if [[ -n "${key}" ]]; then
    printf '%s=%s\n' "${key}" "set(len=${#value})"
  fi
done > "${RECEIPT_DIR}/dr_validate.aws_env.summary"

aws_cli_status="missing"
aws_identity_status="unavailable"
actual_account=""

if command -v aws >/dev/null 2>&1; then
  aws_cli_status="present"
  set +e
  aws sts get-caller-identity --output json > "${RECEIPT_DIR}/dr_validate.sts_identity.json" 2> "${RECEIPT_DIR}/dr_validate.sts_identity.stderr.log"
  sts_rc=$?
  set -e
  if [[ "${sts_rc}" -eq 0 ]]; then
    aws_identity_status="ok"
    actual_account="$(python3 - "${RECEIPT_DIR}/dr_validate.sts_identity.json" <<'PY'
import json,sys
print(json.load(open(sys.argv[1], "r", encoding="utf-8")).get("Account", ""))
PY
)"
    [[ -n "${actual_account}" ]] || fail "unable to parse AWS account from sts identity receipt"
    [[ "${actual_account}" == "${EXPECTED_ACCOUNT_ID}" ]] || fail "AWS account mismatch: expected=${EXPECTED_ACCOUNT_ID} actual=${actual_account}"
  fi
fi

cat > "${RECEIPT_DIR}/dr_validate.aws_preflight.env" <<EOF_ENV
AWS_CLI_STATUS=${aws_cli_status}
AWS_IDENTITY_STATUS=${aws_identity_status}
EXPECTED_ACCOUNT_ID=${EXPECTED_ACCOUNT_ID}
ACTUAL_ACCOUNT_ID=${actual_account}
EOF_ENV

resolve_image_ref_from_control_plane() {
  local bucket="$1"
  local prefix="$2"
  local pointer_uri="s3://${bucket}/${prefix%/}/control-plane/current.json"
  [[ "${aws_cli_status}" == "present" ]] || return 1
  [[ -n "${bucket}" && -n "${prefix}" ]] || return 1

  set +e
  aws s3 cp "${pointer_uri}" - > "${RECEIPT_DIR}/dr_validate.control_plane.current.json" 2> "${RECEIPT_DIR}/dr_validate.control_plane.current.stderr.log"
  local cp_rc=$?
  set -e
  [[ "${cp_rc}" -eq 0 ]] || return 1

  local ref
  ref="$(python3 - "${RECEIPT_DIR}/dr_validate.control_plane.current.json" <<'PY'
import json,sys
obj = json.load(open(sys.argv[1], "r", encoding="utf-8"))
print(obj.get("image_ref_digest", ""))
PY
)"
  [[ -n "${ref}" ]] || return 1
  printf '%s\n' "${pointer_uri}" > "${RECEIPT_DIR}/dr_validate.control_plane.pointer_uri.txt"
  printf '%s\n' "${ref}"
}

resolved_image_ref="${IMAGE_REF}"
image_ref_source="explicit"
if [[ -z "${resolved_image_ref}" ]]; then
  image_ref_source="unset"
  if resolved_image_ref="$(resolve_image_ref_from_control_plane "${CONTROL_PLANE_BUCKET}" "${CONTROL_PLANE_PREFIX}" 2>/dev/null || true)"; then
    if [[ -n "${resolved_image_ref}" ]]; then
      image_ref_source="control_plane_current"
    fi
  fi
fi

cat > "${RECEIPT_DIR}/dr_validate.image_ref_resolution.env" <<EOF_IMG
IMAGE_REF_INPUT=${IMAGE_REF}
IMAGE_REF_RESOLVED=${resolved_image_ref}
IMAGE_REF_SOURCE=${image_ref_source}
CONTROL_PLANE_BUCKET=${CONTROL_PLANE_BUCKET}
CONTROL_PLANE_PREFIX=${CONTROL_PLANE_PREFIX}
EOF_IMG

cat > "${RECEIPT_DIR}/dr_validate.context.env" <<EOF_CTX
AWS_REGION=${AWS_REGION}
AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}
EXPECTED_ACCOUNT_ID=${EXPECTED_ACCOUNT_ID}
ACTUAL_ACCOUNT_ID=${actual_account}
NAMESPACE=${NAMESPACE}
RUN_JOB=${RUN_JOB}
CHECK_IMAGE_ONLY=${CHECK_IMAGE_ONLY}
CHECK_ARCH=${CHECK_ARCH}
IMAGE_REF=${IMAGE_REF}
IMAGE_REF_RESOLVED=${resolved_image_ref}
ECR_PULL_SECRET_NAME=${ECR_PULL_SECRET_NAME}
ECR_PULL_SECRET_SERVICE_ACCOUNT=${ECR_PULL_SECRET_SERVICE_ACCOUNT}
ECR_REGISTRY=${ECR_REGISTRY}
ENSURE_ECR_PULL_SECRET=${ENSURE_ECR_PULL_SECRET}
VALIDATE_REQUEST_CPU=${VALIDATE_REQUEST_CPU}
VALIDATE_REQUEST_MEMORY=${VALIDATE_REQUEST_MEMORY}
VALIDATE_LIMIT_CPU=${VALIDATE_LIMIT_CPU}
VALIDATE_LIMIT_MEMORY=${VALIDATE_LIMIT_MEMORY}
VALIDATE_STARTUP_WINDOW_SECONDS=${VALIDATE_STARTUP_WINDOW_SECONDS}
VALIDATE_JOB_TIMEOUT_SECONDS=${VALIDATE_JOB_TIMEOUT_SECONDS}
VALIDATE_SKIP_WORKLOAD_ASSUME=${VALIDATE_SKIP_WORKLOAD_ASSUME}
EOF_CTX

if [[ "${CHECK_IMAGE_ONLY}" == "1" ]]; then
  [[ "${aws_identity_status}" == "ok" ]] || fail "AWS credentials unavailable for image precheck; ensure env creds, instance role, or a valid AWS profile is available"
  [[ -n "${resolved_image_ref}" ]] || fail "IMAGE_REF is required for CHECK_IMAGE_ONLY when no control-plane pointer is available"
  "${ROOT_DIR}/scripts/release/verify_ecr_image_arch.py" --image-ref "${resolved_image_ref}" --require-arch "${CHECK_ARCH}" \
    2>&1 | tee "${RECEIPT_DIR}/dr_validate.image_precheck.log"
  echo "dr validate image precheck completed" | tee "${RECEIPT_DIR}/dr_validate.result.txt"
  note "validate image check complete; receipt_dir=${RECEIPT_DIR}"
  exit 0
fi

[[ "${VALIDATE_SKIP_WORKLOAD_ASSUME}" == "0" || "${VALIDATE_SKIP_WORKLOAD_ASSUME}" == "1" ]] || fail "VALIDATE_SKIP_WORKLOAD_ASSUME must be 0 or 1"
if [[ "${VALIDATE_SKIP_WORKLOAD_ASSUME}" == "1" ]]; then
  VALIDATION_MODE="skip_workload_assume"
else
  VALIDATION_MODE="strict_workload"
fi
cat > "${RECEIPT_DIR}/dr_validate.mode.env" <<EOF_MODE
VALIDATION_MODE=${VALIDATION_MODE}
VALIDATE_SKIP_WORKLOAD_ASSUME=${VALIDATE_SKIP_WORKLOAD_ASSUME}
EOF_MODE

kubectl get ns "${NAMESPACE}" >/dev/null
cronjob_present=0
if [[ "${VALIDATE_SKIP_WORKLOAD_ASSUME}" == "0" ]]; then
  if kubectl -n "${NAMESPACE}" get cronjob jobintel-daily > "${RECEIPT_DIR}/dr_validate.cronjob.txt" 2>&1; then
    cronjob_present=1
  fi
else
  printf '%s\n' "skip_workload_assume=1; cronjob baseline check bypassed" > "${RECEIPT_DIR}/dr_validate.cronjob.txt"
fi
kubectl -n "${NAMESPACE}" get deploy jobintel-dashboard > "${RECEIPT_DIR}/dr_validate.deploy.txt" 2>&1 || true
kubectl -n "${NAMESPACE}" get pods -o wide > "${RECEIPT_DIR}/dr_validate.pods.txt" 2>&1 || true
kubectl -n "${NAMESPACE}" get all > "${RECEIPT_DIR}/dr_validate.diagnostics.get_all.txt" 2>&1 || true
kubectl -n "${NAMESPACE}" get cronjob -o wide > "${RECEIPT_DIR}/dr_validate.diagnostics.get_cronjob_wide.txt" 2>&1 || true
kubectl -n "${NAMESPACE}" get cm,secret -o name > "${RECEIPT_DIR}/dr_validate.diagnostics.get_cm_secret_name.txt" 2>&1 || true
kubectl get nodes -o wide > "${RECEIPT_DIR}/dr_validate.nodes.txt" 2>&1 || true
kubectl describe nodes > "${RECEIPT_DIR}/dr_validate.nodes.describe.txt" 2>&1 || true
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{" allocatable.cpu="}{.status.allocatable.cpu}{" allocatable.memory="}{.status.allocatable.memory}{" capacity.cpu="}{.status.capacity.cpu}{" capacity.memory="}{.status.capacity.memory}{"\n"}{end}' \
  > "${RECEIPT_DIR}/dr_validate.node_allocatable.txt" 2>&1 || true
kubectl top nodes > "${RECEIPT_DIR}/dr_validate.nodes.top.txt" 2>&1 || true

if [[ "${RUN_JOB}" == "1" ]]; then
  if [[ "${VALIDATE_SKIP_WORKLOAD_ASSUME}" == "1" ]]; then
    required_control_plane_cms=(
      "jobintel-control-plane-candidates"
      "jobintel-control-plane-alerts"
      "jobintel-control-plane-providers"
      "jobintel-control-plane-scoring"
    )
    : > "${RECEIPT_DIR}/dr_validate.control_plane_cm.checks.txt"
    for cm in "${required_control_plane_cms[@]}"; do
      if kubectl -n "${NAMESPACE}" get "configmap/${cm}" >/dev/null 2>&1; then
        echo "present:${cm}" >> "${RECEIPT_DIR}/dr_validate.control_plane_cm.checks.txt"
      else
        echo "missing:${cm}" >> "${RECEIPT_DIR}/dr_validate.control_plane_cm.checks.txt"
        fail "validate skip-workload mode requires control-plane ConfigMaps; missing=${cm} (see ${RECEIPT_DIR}/dr_validate.control_plane_cm.checks.txt)"
      fi
    done
  fi

  if [[ "${ENSURE_ECR_PULL_SECRET}" == "1" ]]; then
    ecr_secret_cmd=("${ROOT_DIR}/scripts/ops/dr_ensure_ecr_pull_secret.sh"
      --namespace "${NAMESPACE}"
      --aws-region "${AWS_REGION}"
      --secret-name "${ECR_PULL_SECRET_NAME}"
      --service-account "${ECR_PULL_SECRET_SERVICE_ACCOUNT}"
      --receipt-dir "${RECEIPT_DIR}/ecr_pull_secret")
    if [[ -n "${ECR_REGISTRY}" ]]; then
      ecr_secret_cmd+=(--ecr-registry "${ECR_REGISTRY}")
    fi
    if [[ -n "${resolved_image_ref}" ]]; then
      ecr_secret_cmd+=(--image-ref "${resolved_image_ref}")
    fi
    "${ecr_secret_cmd[@]}" > "${RECEIPT_DIR}/dr_validate.ecr_pull_secret.log" 2>&1
  else
    printf '%s\n' "skip=true" > "${RECEIPT_DIR}/dr_validate.ecr_pull_secret.log"
  fi
  if [[ "${VALIDATE_SKIP_WORKLOAD_ASSUME}" == "1" ]]; then
    kubectl -n "${NAMESPACE}" get "secret/${ECR_PULL_SECRET_NAME}" > "${RECEIPT_DIR}/dr_validate.ecr_pull_secret.presence.txt" 2>&1 \
      || fail "validate skip-workload mode requires ECR pull secret ${ECR_PULL_SECRET_NAME}"
  fi

  run_label="$(date -u +%Y%m%d%H%M%S)"
  job="jobintel-dr-validate-${run_label}"
  manifest_path="${RECEIPT_DIR}/validate.job_manifest.yaml"
  : > "${RECEIPT_DIR}/validate.run_id.txt"

  if [[ "${cronjob_present}" == "1" ]]; then
    kubectl -n "${NAMESPACE}" create job --from=cronjob/jobintel-daily "${job}" --dry-run=client -o yaml > "${manifest_path}"
    manifest_source="cronjob"
  else
    [[ -n "${resolved_image_ref}" ]] || fail "cronjob jobintel-daily is missing and no IMAGE_REF could be resolved"
    manifest_source="inline_fallback"
    cat > "${manifest_path}" <<EOF_MANIFEST
apiVersion: batch/v1
kind: Job
metadata:
  name: ${job}
  namespace: ${NAMESPACE}
  labels:
    app: jobintel
    purpose: dr-validate
    run_id: "${run_label}"
spec:
  backoffLimit: 1
  activeDeadlineSeconds: 3600
  template:
    metadata:
      labels:
        app.kubernetes.io/name: jobintel
        app.kubernetes.io/component: job
        app: jobintel
        purpose: dr-validate
        run_id: "${run_label}"
    spec:
      serviceAccountName: jobintel
      restartPolicy: Never
      terminationGracePeriodSeconds: 30
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        runAsGroup: 1000
      containers:
        - name: jobintel
          image: ${resolved_image_ref}
          imagePullPolicy: IfNotPresent
          workingDir: /app
          command:
            - python
            - scripts/run_daily.py
          args:
            - --profiles
            - cs
            - --us_only
            - --no_post
          env:
            - name: PUBLISH_S3_REQUIRE
              value: "1"
            - name: JOBINTEL_SNAPSHOT_WRITE_DIR
              value: "/work/jobintel_snapshots"
            - name: CAREERS_MODE
              value: "AUTO"
          envFrom:
            - configMapRef:
                name: jobintel-config
            - secretRef:
                name: jobintel-secrets
          resources:
            requests:
              cpu: "250m"
              memory: "512Mi"
            limits:
              cpu: "1"
              memory: "2Gi"
          securityContext:
            readOnlyRootFilesystem: true
          volumeMounts:
            - name: tmp
              mountPath: /tmp
            - name: work
              mountPath: /work
            - name: jobintel-data
              mountPath: /app/data/ashby_cache
            - name: jobintel-state
              mountPath: /app/state
      volumes:
        - name: tmp
          emptyDir: {}
        - name: work
          emptyDir: {}
        - name: jobintel-data
          emptyDir: {}
        - name: jobintel-state
          emptyDir: {}
EOF_MANIFEST
  fi

  kubectl label --local -f "${manifest_path}" app=jobintel purpose=dr-validate "run_id=${run_label}" -o yaml > "${manifest_path}.tmp"
  mv "${manifest_path}.tmp" "${manifest_path}"
  kubectl patch --local -f "${manifest_path}" --type=json \
    -p "[{\"op\":\"add\",\"path\":\"/spec/template/spec/containers/0/resources\",\"value\":{\"requests\":{\"cpu\":\"${VALIDATE_REQUEST_CPU}\",\"memory\":\"${VALIDATE_REQUEST_MEMORY}\"},\"limits\":{\"cpu\":\"${VALIDATE_LIMIT_CPU}\",\"memory\":\"${VALIDATE_LIMIT_MEMORY}\"}}}]" \
    -o yaml > "${manifest_path}.tmp"
  mv "${manifest_path}.tmp" "${manifest_path}"
  kubectl patch --local -f "${manifest_path}" --type=merge \
    -p '{"spec":{"template":{"spec":{"securityContext":{"runAsNonRoot":true,"runAsUser":1000,"runAsGroup":1000,"fsGroup":1000}}}}}' \
    -o yaml > "${manifest_path}.tmp"
  mv "${manifest_path}.tmp" "${manifest_path}"
  if [[ "${ENSURE_ECR_PULL_SECRET}" == "1" ]]; then
    kubectl patch --local -f "${manifest_path}" --type=merge \
      -p "{\"spec\":{\"template\":{\"spec\":{\"imagePullSecrets\":[{\"name\":\"${ECR_PULL_SECRET_NAME}\"}]}}}}" \
      -o yaml > "${manifest_path}.tmp"
    mv "${manifest_path}.tmp" "${manifest_path}"
  fi

  if [[ -n "${resolved_image_ref}" ]]; then
    if [[ "${aws_identity_status}" == "ok" ]]; then
      "${ROOT_DIR}/scripts/release/verify_ecr_image_arch.py" --image-ref "${resolved_image_ref}" --require-arch "${CHECK_ARCH}" \
        2>&1 | tee "${RECEIPT_DIR}/dr_validate.image_override_precheck.log"
    else
      echo "aws identity unavailable; skipping image arch precheck for runtime validate" \
        > "${RECEIPT_DIR}/dr_validate.image_override_precheck.log"
    fi
    kubectl set image --local -f "${manifest_path}" jobintel="${resolved_image_ref}" -o yaml > "${manifest_path}.tmp"
    mv "${manifest_path}.tmp" "${manifest_path}"
  fi
  state_test_image="$(kubectl create --dry-run=client -f "${manifest_path}" -o jsonpath='{.spec.template.spec.containers[0].image}' 2>/dev/null || true)"
  [[ -n "${state_test_image}" ]] || fail "unable to resolve validate job image for state write preflight"
  kubectl patch --local -f "${manifest_path}" --type=merge \
    -p "{\"spec\":{\"template\":{\"spec\":{\"initContainers\":[{\"name\":\"state-writable-preflight\",\"image\":\"${state_test_image}\",\"imagePullPolicy\":\"IfNotPresent\",\"command\":[\"python\",\"-c\",\"import pathlib; p=pathlib.Path('/app/state/history'); p.mkdir(parents=True, exist_ok=True); f=pathlib.Path('/app/state/history/.dr_write_test'); f.write_text('ok\\\\n', encoding='utf-8'); print('state_write_test=ok path=' + str(f))\"],\"securityContext\":{\"readOnlyRootFilesystem\":true},\"volumeMounts\":[{\"name\":\"tmp\",\"mountPath\":\"/tmp\"},{\"name\":\"jobintel-state\",\"mountPath\":\"/app/state\"}]}]}}}}" \
    -o yaml > "${manifest_path}.tmp"
  mv "${manifest_path}.tmp" "${manifest_path}"

  cat > "${RECEIPT_DIR}/dr_validate.job_submission.env" <<EOF_JOB
JOB_NAME=${job}
RUN_LABEL=${run_label}
MANIFEST_SOURCE=${manifest_source}
IMAGE_REF_RESOLVED=${resolved_image_ref}
VALIDATE_REQUEST_CPU=${VALIDATE_REQUEST_CPU}
VALIDATE_REQUEST_MEMORY=${VALIDATE_REQUEST_MEMORY}
VALIDATE_LIMIT_CPU=${VALIDATE_LIMIT_CPU}
VALIDATE_LIMIT_MEMORY=${VALIDATE_LIMIT_MEMORY}
EOF_JOB
  kubectl create --dry-run=client -f "${manifest_path}" -o json > "${RECEIPT_DIR}/dr_validate.job_manifest.json"
  python3 - "${RECEIPT_DIR}/dr_validate.job_manifest.json" "${RECEIPT_DIR}/dr_validate.job_resources.env" "${job}" <<'PY'
import json
import pathlib
import sys

src, out, job_name = sys.argv[1:]
doc = json.loads(pathlib.Path(src).read_text(encoding="utf-8"))
spec = doc.get("spec", {}).get("template", {}).get("spec", {})
containers = spec.get("containers", [])
jobintel = next((c for c in containers if c.get("name") == "jobintel"), containers[0] if containers else {})
resources = jobintel.get("resources", {})
requests = resources.get("requests", {})
limits = resources.get("limits", {})
security = spec.get("securityContext", {})
init_containers = spec.get("initContainers", [])
image_pull_secrets = ",".join(s.get("name", "") for s in spec.get("imagePullSecrets", []) if s.get("name"))
volume_mounts = ",".join(f"{m.get('name','')}:{m.get('mountPath','')}" for m in jobintel.get("volumeMounts", []))
init_summary = ",".join(f"{c.get('name','')}:{c.get('image','')}" for c in init_containers)
lines = [
    f"JOB_NAME={job_name}",
    f"REQUEST_CPU={requests.get('cpu', '')}",
    f"REQUEST_MEMORY={requests.get('memory', '')}",
    f"LIMIT_CPU={limits.get('cpu', '')}",
    f"LIMIT_MEMORY={limits.get('memory', '')}",
    f"SERVICE_ACCOUNT={spec.get('serviceAccountName', '')}",
    f"IMAGE_PULL_SECRETS={image_pull_secrets}",
    f"POD_RUN_AS_USER={security.get('runAsUser', '')}",
    f"POD_RUN_AS_GROUP={security.get('runAsGroup', '')}",
    f"POD_FS_GROUP={security.get('fsGroup', '')}",
    f"INIT_CONTAINERS={init_summary}",
    f"VOLUME_MOUNTS={volume_mounts}",
]
pathlib.Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
PY

  kubectl -n "${NAMESPACE}" apply -f "${manifest_path}" > "${RECEIPT_DIR}/dr_validate.create_job.log" 2>&1

  resolved_job="$(kubectl -n "${NAMESPACE}" get jobs -l purpose=dr-validate,run_id="${run_label}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
  if [[ -n "${resolved_job}" ]]; then
    job="${resolved_job}"
  fi

  echo "DR_JOB_NAME=${job}" | tee "${RECEIPT_DIR}/dr_validate.job_name.txt"
  printf '%s\n' "${job}" > "${RECEIPT_DIR}/validate.job_name.txt"

  pod_name=""
  for _ in $(seq 1 90); do
    pod_name="$(kubectl -n "${NAMESPACE}" get pods -l job-name="${job}" -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
    if [[ -n "${pod_name}" ]]; then
      break
    fi
    sleep 2
  done

  if [[ -z "${pod_name}" ]]; then
    kubectl -n "${NAMESPACE}" describe "job/${job}" > "${RECEIPT_DIR}/dr_validate.describe_job.txt" 2>&1 || true
    kubectl -n "${NAMESPACE}" get events --sort-by=.metadata.creationTimestamp > "${RECEIPT_DIR}/dr_validate.events.txt" 2>&1 || true
    fail "validate job ${job} created no pod; see ${RECEIPT_DIR}/dr_validate.describe_job.txt and ${RECEIPT_DIR}/dr_validate.events.txt"
  fi

  printf '%s\n' "${pod_name}" > "${RECEIPT_DIR}/dr_validate.pod_name.txt"
  kubectl -n "${NAMESPACE}" get "pod/${pod_name}" -o json > "${RECEIPT_DIR}/dr_validate.pod_spec.json"
  python3 - "${RECEIPT_DIR}/dr_validate.pod_spec.json" "${RECEIPT_DIR}/dr_validate.pod_spec_receipt.env" <<'PY'
import json
import pathlib
import sys

src, out = sys.argv[1:]
doc = json.loads(pathlib.Path(src).read_text(encoding="utf-8"))
spec = doc.get("spec", {})
status = doc.get("status", {})
containers = spec.get("containers", [])
jobintel = next((c for c in containers if c.get("name") == "jobintel"), containers[0] if containers else {})
volume_mounts = ",".join(f"{m.get('name','')}:{m.get('mountPath','')}" for m in jobintel.get("volumeMounts", []))
init_status = []
for item in status.get("initContainerStatuses", []):
    reason = (
        item.get("state", {}).get("terminated", {}).get("reason")
        or item.get("state", {}).get("waiting", {}).get("reason")
        or item.get("state", {}).get("running", {}) and "Running"
        or ""
    )
    init_status.append(f"{item.get('name','')}:{reason}")
lines = [
    f"POD_SECURITY_CONTEXT={json.dumps(spec.get('securityContext', {}), sort_keys=True)}",
    f"POD_VOLUME_MOUNTS={volume_mounts}",
    f"INIT_CONTAINER_STATUS={','.join(init_status)}",
]
pathlib.Path(out).write_text("\n".join(lines) + "\n", encoding="utf-8")
PY
  startup_checks=$((VALIDATE_STARTUP_WINDOW_SECONDS / 2))
  if [[ "${startup_checks}" -lt 1 ]]; then
    startup_checks=1
  fi
  init_state=""
  for _ in $(seq 1 "${startup_checks}"); do
    init_state="$(kubectl -n "${NAMESPACE}" get "pod/${pod_name}" -o jsonpath='{.status.initContainerStatuses[?(@.name=="state-writable-preflight")].state.terminated.reason}' 2>/dev/null || true)"
    if [[ "${init_state}" == "Completed" ]]; then
      break
    fi
    if [[ "${init_state}" == "Error" ]]; then
      break
    fi
    sleep 2
  done
  if ! kubectl -n "${NAMESPACE}" logs "pod/${pod_name}" -c state-writable-preflight > "${RECEIPT_DIR}/dr_validate.state_write_test.log" 2>&1; then
    kubectl -n "${NAMESPACE}" describe "pod/${pod_name}" > "${RECEIPT_DIR}/dr_validate.describe_pod.txt" 2>&1 || true
    fail "unable to read state write preflight logs; see ${RECEIPT_DIR}/dr_validate.state_write_test.log"
  fi
  if [[ "${init_state}" != "Completed" ]] || ! grep -q "state_write_test=ok" "${RECEIPT_DIR}/dr_validate.state_write_test.log"; then
    kubectl -n "${NAMESPACE}" describe "pod/${pod_name}" > "${RECEIPT_DIR}/dr_validate.describe_pod.txt" 2>&1 || true
    fail "validate state write preflight failed; see ${RECEIPT_DIR}/dr_validate.state_write_test.log"
  fi

  # Fast-fail on terminal pull/runtime blockers before the long completion wait.
  pod_ready=0
  for _ in $(seq 1 "${startup_checks}"); do
    pod_phase="$(kubectl -n "${NAMESPACE}" get "pod/${pod_name}" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
    waiting_reason="$(kubectl -n "${NAMESPACE}" get "pod/${pod_name}" -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null || true)"
    if [[ "${waiting_reason}" == "ImagePullBackOff" || "${waiting_reason}" == "ErrImagePull" || "${waiting_reason}" == "InvalidImageName" ]]; then
      kubectl -n "${NAMESPACE}" describe "job/${job}" > "${RECEIPT_DIR}/dr_validate.describe_job.txt" 2>&1 || true
      kubectl -n "${NAMESPACE}" describe "pod/${pod_name}" > "${RECEIPT_DIR}/dr_validate.describe_pod.txt" 2>&1 || true
      kubectl -n "${NAMESPACE}" get events --sort-by=.metadata.creationTimestamp > "${RECEIPT_DIR}/dr_validate.events.txt" 2>&1 || true
      fail "validate pod ${pod_name} blocked with ${waiting_reason}; see ${RECEIPT_DIR}/dr_validate.describe_pod.txt"
    fi
    if [[ "${pod_phase}" == "Failed" ]]; then
      kubectl -n "${NAMESPACE}" logs "pod/${pod_name}" > "${RECEIPT_DIR}/dr_validate.pod.log" 2>&1 || true
      kubectl -n "${NAMESPACE}" describe "job/${job}" > "${RECEIPT_DIR}/dr_validate.describe_job.txt" 2>&1 || true
      kubectl -n "${NAMESPACE}" describe "pod/${pod_name}" > "${RECEIPT_DIR}/dr_validate.describe_pod.txt" 2>&1 || true
      kubectl -n "${NAMESPACE}" get events --sort-by=.metadata.creationTimestamp > "${RECEIPT_DIR}/dr_validate.events.txt" 2>&1 || true
      fail "validate pod ${pod_name} failed before ready; see ${RECEIPT_DIR}/dr_validate.pod.log"
    fi
    if [[ "${pod_phase}" == "Running" || "${pod_phase}" == "Succeeded" ]]; then
      pod_ready=1
      break
    fi
    sleep 2
  done
  if [[ "${pod_ready}" -ne 1 ]]; then
    kubectl -n "${NAMESPACE}" describe "job/${job}" > "${RECEIPT_DIR}/dr_validate.describe_job.txt" 2>&1 || true
    kubectl -n "${NAMESPACE}" describe "pod/${pod_name}" > "${RECEIPT_DIR}/dr_validate.describe_pod.txt" 2>&1 || true
    kubectl -n "${NAMESPACE}" get events --sort-by=.metadata.creationTimestamp > "${RECEIPT_DIR}/dr_validate.events.txt" 2>&1 || true
    fail "validate pod ${pod_name} did not reach Running/Succeeded in startup window; see ${RECEIPT_DIR}/dr_validate.describe_pod.txt"
  fi

  job_completed=0
  job_timeout_checks=$((VALIDATE_JOB_TIMEOUT_SECONDS / 3))
  if [[ "${job_timeout_checks}" -lt 1 ]]; then
    job_timeout_checks=1
  fi
  : > "${RECEIPT_DIR}/dr_validate.wait.log"
  for _ in $(seq 1 "${job_timeout_checks}"); do
    job_succeeded="$(kubectl -n "${NAMESPACE}" get "job/${job}" -o jsonpath='{.status.succeeded}' 2>/dev/null || true)"
    job_failed="$(kubectl -n "${NAMESPACE}" get "job/${job}" -o jsonpath='{.status.failed}' 2>/dev/null || true)"
    echo "succeeded=${job_succeeded:-0} failed=${job_failed:-0}" >> "${RECEIPT_DIR}/dr_validate.wait.log"
    if [[ "${job_succeeded:-0}" =~ ^[1-9][0-9]*$ ]]; then
      job_completed=1
      break
    fi
    if [[ "${job_failed:-0}" =~ ^[1-9][0-9]*$ ]]; then
      kubectl -n "${NAMESPACE}" logs "job/${job}" > "${RECEIPT_DIR}/dr_validate.job.log" 2>&1 || true
      tail -n 200 "${RECEIPT_DIR}/dr_validate.job.log" > "${RECEIPT_DIR}/dr_validate.job_tail.log" || true
      kubectl -n "${NAMESPACE}" describe "job/${job}" > "${RECEIPT_DIR}/dr_validate.describe_job.txt" 2>&1 || true
      kubectl -n "${NAMESPACE}" describe "pod/${pod_name}" > "${RECEIPT_DIR}/dr_validate.describe_pod.txt" 2>&1 || true
      kubectl -n "${NAMESPACE}" get events --sort-by=.metadata.creationTimestamp > "${RECEIPT_DIR}/dr_validate.events.txt" 2>&1 || true
      fail "validate job ${job} failed before completion; see ${RECEIPT_DIR}/dr_validate.job_tail.log"
    fi
    sleep 3
  done
  if [[ "${job_completed}" -ne 1 ]]; then
    kubectl -n "${NAMESPACE}" describe "job/${job}" > "${RECEIPT_DIR}/dr_validate.describe_job.txt" 2>&1 || true
    kubectl -n "${NAMESPACE}" describe "pod/${pod_name}" > "${RECEIPT_DIR}/dr_validate.describe_pod.txt" 2>&1 || true
    kubectl -n "${NAMESPACE}" get events --sort-by=.metadata.creationTimestamp > "${RECEIPT_DIR}/dr_validate.events.txt" 2>&1 || true
    fail "validate job ${job} timed out without completion; see ${RECEIPT_DIR}/dr_validate.wait.log"
  fi

  kubectl -n "${NAMESPACE}" logs "job/${job}" > "${RECEIPT_DIR}/dr_validate.job.log" 2>&1 || true
  tail -n 200 "${RECEIPT_DIR}/dr_validate.job.log" > "${RECEIPT_DIR}/dr_validate.job_tail.log"

  run_id="$(sed -n 's/.*JOBINTEL_RUN_ID=//p' "${RECEIPT_DIR}/dr_validate.job.log" | head -n 1 | tr -d '[:space:]' || true)"
  printf '%s\n' "${run_id}" > "${RECEIPT_DIR}/validate.run_id.txt"
  echo "DR_JOB_NAME=${job}"
fi

echo "dr validate checks completed" | tee "${RECEIPT_DIR}/dr_validate.result.txt"
note "validate complete; receipt_dir=${RECEIPT_DIR}"
