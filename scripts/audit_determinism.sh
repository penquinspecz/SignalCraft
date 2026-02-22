#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

FAIL_COUNT=0
WARN_COUNT=0

pass() { echo "PASS: $*"; }
warn() { echo "WARN: $*"; WARN_COUNT=$((WARN_COUNT+1)); }
fail() { echo "FAIL: $*"; FAIL_COUNT=$((FAIL_COUNT+1)); }

check_committed_local_state() {
  local matches
  matches="$(git -C "${ROOT_DIR}" ls-files \
    | rg -n '(^|/)__pycache__/|(^|/)\.terraform/|terraform\.tfstate(\.backup)?$|(^|/)tfplan(-destroy)?$|\.tfplan$' -S || true)"
  if [[ -n "${matches}" ]]; then
    fail "committed_local_state_or_cache_files_found"
    printf '%s\n' "${matches}"
  else
    pass "no_committed_local_state_or_cache_files"
  fi
}

check_untracked_local_state_warning() {
  local matches
  matches="$(git -C "${ROOT_DIR}" status --short --untracked-files=all \
    | rg -n '__pycache__/|\.terraform/|terraform\.tfstate|tfplan' -S || true)"
  if [[ -n "${matches}" ]]; then
    warn "untracked_local_state_or_cache_files_present"
    printf '%s\n' "${matches}"
  else
    pass "no_untracked_local_state_or_cache_files"
  fi
}

check_no_local_kubeconfig_paths() {
  local matches
  matches="$(rg -n '(~/.kube/config|/Users/.+/.kube/config|/home/.+/.kube/config)' -S "${ROOT_DIR}/scripts" -g '!audit_determinism.sh' || true)"
  if [[ -n "${matches}" ]]; then
    fail "local_only_kubeconfig_paths_found_in_scripts"
    printf '%s\n' "${matches}"
  else
    pass "no_local_only_kubeconfig_paths_in_scripts"
  fi
}

check_dr_script_region_contract() {
  local missing=0
  local f
  while IFS= read -r f; do
    [[ -n "${f}" ]] || continue
    if ! rg -q 'AWS_REGION=' "${f}"; then
      fail "missing_AWS_REGION_default file=${f}"
      missing=1
    fi
    if ! rg -q 'AWS_DEFAULT_REGION=' "${f}"; then
      fail "missing_AWS_DEFAULT_REGION_default file=${f}"
      missing=1
    fi
    if ! rg -q '\bexport\b.*\bAWS_REGION\b' "${f}"; then
      fail "missing_export_AWS_REGION file=${f}"
      missing=1
    fi
    if ! rg -q '\bexport\b.*\bAWS_DEFAULT_REGION\b' "${f}"; then
      fail "missing_export_AWS_DEFAULT_REGION file=${f}"
      missing=1
    fi
  done < <(cd "${ROOT_DIR}" && rg --files scripts/ops -g 'dr_*.sh' | sed "s|^|${ROOT_DIR}/|")

  if [[ "${missing}" -eq 0 ]]; then
    pass "all_dr_scripts_export_AWS_region_defaults"
  fi
}

check_dr_script_account_contract_for_aws_calls() {
  local missing=0
  local f
  while IFS= read -r f; do
    [[ -n "${f}" ]] || continue
    if rg -q '\baws\b' "${f}"; then
      if ! rg -q 'EXPECTED_ACCOUNT_ID' "${f}"; then
        fail "aws_calls_without_expected_account_id file=${f}"
        missing=1
        continue
      fi
      if ! rg -q 'sts get-caller-identity' "${f}"; then
        fail "aws_calls_without_sts_account_gate file=${f}"
        missing=1
      fi
    fi
  done < <(cd "${ROOT_DIR}" && rg --files scripts/ops -g 'dr_*.sh' | sed "s|^|${ROOT_DIR}/|")

  if [[ "${missing}" -eq 0 ]]; then
    pass "all_dr_scripts_with_aws_calls_enforce_expected_account"
  fi
}

check_tf_apply_requires_automation() {
  local missing=0
  local f
  while IFS= read -r f; do
    [[ -n "${f}" ]] || continue
    if rg -q 'terraform apply' "${f}"; then
      if ! rg -q 'TF_IN_AUTOMATION' "${f}"; then
        fail "terraform_apply_without_TF_IN_AUTOMATION file=${f}"
        missing=1
      fi
      if ! rg -q 'TF_IN_AUTOMATION.*1|must be 1' "${f}"; then
        fail "terraform_apply_without_TF_IN_AUTOMATION_eq_1_guard file=${f}"
        missing=1
      fi
    fi
  done < <(cd "${ROOT_DIR}" && rg --files scripts/ops -g 'dr_*.sh' | sed "s|^|${ROOT_DIR}/|")

  if [[ "${missing}" -eq 0 ]]; then
    pass "all_dr_terraform_apply_paths_require_TF_IN_AUTOMATION_1"
  fi
}

check_floating_latest_tags() {
  local matches
  matches="$(
    {
      rg -n 'image:\s*[^#\s]+:latest\b|newTag:\s*latest\b' -S \
        "${ROOT_DIR}/ops" "${ROOT_DIR}/.github/workflows" \
        --glob '*.yaml' --glob '*.yml' || true
      rg -n 'FROM\s+[^#\s]+:latest\b' -S "${ROOT_DIR}" --glob 'Dockerfile*' --glob '*.Dockerfile' || true
    } | sed '/^$/d'
  )"
  if [[ -n "${matches}" ]]; then
    fail "floating_latest_image_tags_found"
    printf '%s\n' "${matches}"
  else
    pass "no_floating_latest_image_tags"
  fi
}

check_unpinned_helm_charts() {
  local report
  report="$(python3 - "${ROOT_DIR}" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
violations = []
for tf in root.rglob('*.tf'):
    if '.terraform' in tf.parts:
        continue
    text = tf.read_text(encoding='utf-8')
    for m in re.finditer(r'resource\s+"helm_release"\s+"[^"]+"\s*\{', text):
        start = m.start()
        depth = 0
        end = None
        for idx, ch in enumerate(text[start:], start=start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = idx
                    break
        block = text[start:end+1] if end is not None else text[start:]
        if not re.search(r'\n\s*version\s*=\s*"[^"]+"', block):
            line = text[:start].count('\n') + 1
            violations.append(f"{tf}:{line}:helm_release_missing_version")

if violations:
    print("FAIL")
    print("\n".join(violations))
else:
    print("PASS")
PY
)"
  if [[ "${report%%$'\n'*}" == "FAIL" ]]; then
    fail "unpinned_helm_release_chart_version_found"
    printf '%s\n' "${report#*$'\n'}"
  else
    pass "all_helm_release_resources_have_pinned_version"
  fi
}

check_ami_drift_risk() {
  local matches
  matches="$(rg -n 'most_recent\s*=\s*true' -S "${ROOT_DIR}/ops/dr" || true)"
  if [[ -n "${matches}" ]]; then
    if rg -q 'variable\s+"ami_id"' "${ROOT_DIR}/ops/dr/terraform/variables.tf"; then
      pass "ami_drift_risk_present_but_overridable_with_ami_id"
      printf '%s\n' "${matches}"
    else
      fail "ami_drift_risk_present_without_ami_id_override"
      printf '%s\n' "${matches}"
    fi
  else
    pass "no_ami_most_recent_drift_risk"
  fi
}

check_dr_receipt_writes() {
  local missing=0
  local scripts=(
    "${ROOT_DIR}/scripts/ops/dr_bringup.sh"
    "${ROOT_DIR}/scripts/ops/dr_restore.sh"
    "${ROOT_DIR}/scripts/ops/dr_validate.sh"
    "${ROOT_DIR}/scripts/ops/dr_teardown.sh"
    "${ROOT_DIR}/scripts/ops/dr_drill.sh"
    "${ROOT_DIR}/scripts/ops/dr_failback.sh"
  )
  local f
  for f in "${scripts[@]}"; do
    [[ -f "${f}" ]] || { fail "missing_script_for_receipt_check file=${f}"; missing=1; continue; }
    if ! rg -q 'RECEIPT_DIR' "${f}"; then
      fail "missing_RECEIPT_DIR_usage file=${f}"
      missing=1
      continue
    fi
    if ! rg -q '\.write-test|write_text\(|tee\s+"\$\{RECEIPT_DIR\}' "${f}"; then
      fail "missing_explicit_receipt_write file=${f}"
      missing=1
    fi
  done
  if [[ "${missing}" -eq 0 ]]; then
    pass "dr_phase_scripts_write_receipts"
  fi
}

run_existing_dr_guardrails() {
  if [[ -f "${ROOT_DIR}/scripts/ops/check_dr_guardrails.py" ]]; then
    if python3 "${ROOT_DIR}/scripts/ops/check_dr_guardrails.py"; then
      pass "check_dr_guardrails.py"
    else
      fail "check_dr_guardrails.py_failed"
    fi
  else
    warn "scripts/ops/check_dr_guardrails.py_missing"
  fi
}

check_control_plane_continuity_mechanism() {
  local missing=0
  local required_scripts=(
    "${ROOT_DIR}/scripts/control_plane/publish_bundle.sh"
    "${ROOT_DIR}/scripts/control_plane/fetch_bundle.sh"
    "${ROOT_DIR}/scripts/control_plane/apply_bundle_k8s.sh"
  )
  local f
  for f in "${required_scripts[@]}"; do
    if [[ ! -x "${f}" ]]; then
      fail "missing_or_not_executable_control_plane_script file=${f}"
      missing=1
    fi
  done

  if ! rg -q 'scripts/control_plane/fetch_bundle\.sh' "${ROOT_DIR}/scripts/ops/dr_restore.sh"; then
    fail "dr_restore_missing_control_plane_fetch_hook"
    missing=1
  fi
  if ! rg -q 'scripts/control_plane/apply_bundle_k8s\.sh' "${ROOT_DIR}/scripts/ops/dr_restore.sh"; then
    fail "dr_restore_missing_control_plane_apply_hook"
    missing=1
  fi
  if ! rg -q -- '--kubeconfig "\$\{DR_KUBECONFIG_PUBLIC\}"' "${ROOT_DIR}/scripts/ops/dr_drill.sh"; then
    fail "dr_drill_missing_restore_kubeconfig_wiring"
    missing=1
  fi

  if [[ "${missing}" -eq 0 ]]; then
    pass "control_plane_bundle_continuity_hooks_present"
  fi
}

main() {
  cd "${ROOT_DIR}"
  check_committed_local_state
  check_untracked_local_state_warning
  check_no_local_kubeconfig_paths
  check_dr_script_region_contract
  check_dr_script_account_contract_for_aws_calls
  check_tf_apply_requires_automation
  check_floating_latest_tags
  check_unpinned_helm_charts
  check_ami_drift_risk
  check_dr_receipt_writes
  check_control_plane_continuity_mechanism
  run_existing_dr_guardrails

  if [[ "${FAIL_COUNT}" -ne 0 ]]; then
    echo "SUMMARY: FAIL fail_count=${FAIL_COUNT} warn_count=${WARN_COUNT}"
    exit 1
  fi
  echo "SUMMARY: PASS fail_count=0 warn_count=${WARN_COUNT}"
}

main "$@"
