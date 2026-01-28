import os
import shutil
import subprocess
from pathlib import Path
from textwrap import dedent

import pytest


def _write_executable(path: Path, content: str) -> None:
    path.write_text(dedent(content).lstrip(), encoding="utf-8")
    path.chmod(0o755)


def _install_fake_aws(bin_dir: Path) -> None:
    _write_executable(
        bin_dir / "aws",
        """
        #!/usr/bin/env bash
        set -euo pipefail
        if [[ -n "${AWS_FAKE_LOG_PATH:-}" ]]; then
          echo "$*" >> "${AWS_FAKE_LOG_PATH}"
        fi
        if [[ "$1" == "s3" && "$2" == "cp" ]]; then
          uri="$3"
          dest="$4"
          body=""
          if [[ "${uri}" == "${AWS_FAKE_POINTER_URI:-}" ]]; then
            body="${AWS_FAKE_POINTER_JSON:-}"
          elif [[ "${uri}" == "${AWS_FAKE_RUN_REPORT_URI:-}" ]]; then
            body="${AWS_FAKE_RUN_REPORT_JSON:-}"
          elif [[ "${uri}" == "${AWS_FAKE_OBJ_URI_1:-}" ]]; then
            body="${AWS_FAKE_OBJ_BODY_1:-}"
          elif [[ "${uri}" == "${AWS_FAKE_OBJ_URI_2:-}" ]]; then
            body="${AWS_FAKE_OBJ_BODY_2:-}"
          fi
          if [[ -n "${body}" ]]; then
            if [[ "${dest}" == "-" ]]; then
              printf '%s' "${body}"
            else
              printf '%s' "${body}" > "${dest}"
            fi
            exit 0
          fi
          exit 1
        fi
        if [[ "$1" == "s3api" && "$2" == "head-object" ]]; then
          key=""
          for ((i=1; i<=$#; i++)); do
            if [[ "${!i}" == "--key" ]]; then
              next=$((i+1))
              key="${!next}"
              break
            fi
          done
          if [[ -n "${AWS_FAKE_HEAD_KEYS:-}" ]]; then
            IFS=';' read -r -a pairs <<< "${AWS_FAKE_HEAD_KEYS}"
            for pair in "${pairs[@]}"; do
              k="${pair%%|*}"
              v="${pair#*|}"
              if [[ "${key}" == "${k}" ]]; then
                printf '%s' "${v}"
                exit 0
              fi
            done
          fi
          exit 255
        fi
        if [[ "$1" == "s3api" && "$2" == "list-objects-v2" ]]; then
          prefix=""
          for ((i=1; i<=$#; i++)); do
            if [[ "${!i}" == "--prefix" ]]; then
              next=$((i+1))
              prefix="${!next}"
              break
            fi
          done
          if [[ -n "${AWS_FAKE_LIST_PREFIX:-}" && "${prefix}" == "${AWS_FAKE_LIST_PREFIX}" ]]; then
            printf '%s' "${AWS_FAKE_LIST_KEYS:-[]}"
            exit 0
          fi
          if [[ -n "${AWS_FAKE_LIST_PREFIX_2:-}" && "${prefix}" == "${AWS_FAKE_LIST_PREFIX_2}" ]]; then
            printf '%s' "${AWS_FAKE_LIST_KEYS_2:-[]}"
            exit 0
          fi
          printf '[]'
          exit 0
        fi
        exit 0
        """,
    )


def _install_fake_jq(bin_dir: Path) -> None:
    content = "\n".join(
        [
            "#!/usr/bin/env python3",
            "import json",
            "import re",
            "import sys",
            "",
            "args = sys.argv[1:]",
            "raw = sys.stdin.read()",
            "try:",
            "    data = json.loads(raw) if raw else None",
            "except json.JSONDecodeError:",
            "    data = None",
            "",
            'if "-r" in args:',
            '    if args and args[-1] == ".run_id // empty":',
            "        value = data.get(\"run_id\") if isinstance(data, dict) else None",
            "        sys.stdout.write(\"\" if value is None else str(value))",
            "        sys.exit(0)",
            '    if args and args[-1] == ".[]?":',
            "        if isinstance(data, list):",
            "            for item in data:",
            "                sys.stdout.write(f\"{item}\\n\")",
            "        sys.exit(0)",
            "    if args and \"select(test(\" in args[-1]:",
            "        pattern = r\"ranked_(jobs|families).*\\\\.(json|csv)$\"",
            "        if isinstance(data, list):",
            "            for item in data:",
            "                if isinstance(item, str) and re.search(pattern, item):",
            "                    sys.stdout.write(f\"{item}\\n\")",
            "                    break",
            "            else:",
            "                if data:",
            "                    sys.stdout.write(f\"{data[0]}\\n\")",
            "        sys.exit(0)",
            "    sys.stdout.write(\"\")",
            "    sys.exit(0)",
            "",
            'if "-e" in args and args[-1] == ".provenance.build":',
            "    exists = (",
            "        isinstance(data, dict)",
            "        and isinstance(data.get(\"provenance\"), dict)",
            "        and data[\"provenance\"].get(\"build\") is not None",
            "    )",
            "    sys.exit(0 if exists else 1)",
            "",
            'if "-c" in args and args[-1] == ".provenance.build":',
            "    value = None",
            "    if isinstance(data, dict) and isinstance(data.get(\"provenance\"), dict):",
            "        value = data[\"provenance\"].get(\"build\")",
            "    sys.stdout.write(json.dumps(value, separators=(\",\", \":\")))",
            "    sys.exit(0)",
            "",
            "sys.stdout.write(raw)",
            "sys.exit(0)",
            "",
        ]
    )
    _write_executable(bin_dir / "jq", content)


def test_shell_scripts_syntax() -> None:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available")
    repo_root = Path(__file__).resolve().parents[1]
    scripts_dir = repo_root / "scripts"
    script_paths = sorted(p for p in scripts_dir.glob("*.sh") if p.is_file())
    assert script_paths, "no shell scripts found"
    for path in script_paths:
        result = subprocess.run([bash, "-n", str(path)], capture_output=True, text=True)
        assert result.returncode == 0, f"bash -n failed for {path}: {result.stderr}"


@pytest.mark.parametrize(
    "script_name",
    [
        "run_ecs_once.sh",
        "verify_ops.sh",
        "ecs_verify_task.sh",
        "verify_s3_pointers.sh",
        "show_run_provenance.sh",
        "verify_publish_s3.sh",
    ],
)
def test_shell_script_smoke_no_unbound(script_name: str) -> None:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available")
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / script_name
    env = {"PATH": os.environ.get("PATH", "")}
    result = subprocess.run([bash, str(script)], capture_output=True, text=True, env=env)
    assert result.returncode != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "unbound variable" not in combined
    assert "bad substitution" not in combined


def test_show_run_provenance_success(tmp_path: Path) -> None:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available")
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "show_run_provenance.sh"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install_fake_aws(bin_dir)
    _install_fake_jq(bin_dir)
    pointer_uri = "s3://bucket/prefix/state/last_success.json"
    run_report_uri = "s3://bucket/prefix/runs/run-123/run_report.json"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "BUCKET": "bucket",
        "PREFIX": "prefix",
        "REGION": "us-east-1",
        "AWS_FAKE_POINTER_URI": pointer_uri,
        "AWS_FAKE_POINTER_JSON": '{"run_id":"run-123"}',
        "AWS_FAKE_RUN_REPORT_URI": run_report_uri,
        "AWS_FAKE_RUN_REPORT_JSON": (
            '{"provenance":{"build":{"git_sha":"abc","image":"img","taskdef":"td","ecs_task_arn":"arn"}}}'
        ),
    }
    result = subprocess.run([bash, str(script)], capture_output=True, text=True, env=env)
    assert result.returncode == 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert run_report_uri in combined
    assert '"ecs_task_arn":"arn"' in combined
    assert "Summary: SUCCESS" in combined


def test_show_run_provenance_missing_build(tmp_path: Path) -> None:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available")
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "show_run_provenance.sh"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install_fake_aws(bin_dir)
    _install_fake_jq(bin_dir)
    pointer_uri = "s3://bucket/prefix/state/last_success.json"
    run_report_uri = "s3://bucket/prefix/runs/run-123/run_report.json"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "BUCKET": "bucket",
        "PREFIX": "prefix",
        "REGION": "us-east-1",
        "AWS_FAKE_POINTER_URI": pointer_uri,
        "AWS_FAKE_POINTER_JSON": '{"run_id":"run-123"}',
        "AWS_FAKE_RUN_REPORT_URI": run_report_uri,
        "AWS_FAKE_RUN_REPORT_JSON": '{"run_id":"run-123"}',
    }
    result = subprocess.run([bash, str(script)], capture_output=True, text=True, env=env)
    assert result.returncode == 1
    combined = (result.stdout or "") + (result.stderr or "")
    assert run_report_uri in combined
    assert "run_id=run-123" in combined
    assert "Run a new ECS job" in combined
    assert "Summary: FAIL" in combined


def test_show_run_provenance_provider_pointer(tmp_path: Path) -> None:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available")
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "show_run_provenance.sh"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install_fake_aws(bin_dir)
    _install_fake_jq(bin_dir)
    log_path = tmp_path / "aws.log"
    pointer_uri = "s3://bucket/prefix/state/openai/cs/last_success.json"
    run_report_uri = "s3://bucket/prefix/runs/run-123/run_report.json"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "BUCKET": "bucket",
        "PREFIX": "prefix",
        "REGION": "us-east-1",
        "PROVIDER": "openai",
        "PROFILE": "cs",
        "AWS_FAKE_LOG_PATH": str(log_path),
        "AWS_FAKE_POINTER_URI": pointer_uri,
        "AWS_FAKE_POINTER_JSON": '{"run_id":"run-123"}',
        "AWS_FAKE_RUN_REPORT_URI": run_report_uri,
        "AWS_FAKE_RUN_REPORT_JSON": (
            '{"provenance":{"build":{"git_sha":"abc","image":"img","taskdef":"td","ecs_task_arn":"arn"}}}'
        ),
    }
    result = subprocess.run([bash, str(script)], capture_output=True, text=True, env=env)
    assert result.returncode == 0
    log_text = log_path.read_text(encoding="utf-8")
    assert pointer_uri in log_text


def test_verify_publish_s3_success(tmp_path: Path) -> None:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available")
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "verify_publish_s3.sh"
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _install_fake_aws(bin_dir)
    _install_fake_jq(bin_dir)
    run_id = "run-123"
    bucket = "bucket"
    prefix = "jobintel"
    run_report_key = f"{prefix}/runs/{run_id}/run_report.json"
    ranked_key = f"{prefix}/runs/{run_id}/openai/cs/openai_ranked_families.cs.json"
    latest_key = f"{prefix}/latest/openai/cs/openai_ranked_families.cs.json"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "BUCKET": bucket,
        "PREFIX": prefix,
        "RUN_ID": run_id,
        "REGION": "us-east-1",
        "PROVIDER": "openai",
        "PROFILE": "cs",
        "AWS_FAKE_POINTER_URI": f"s3://{bucket}/{prefix}/state/last_success.json",
        "AWS_FAKE_POINTER_JSON": '{"run_id":"run-123"}',
        "AWS_FAKE_LIST_PREFIX": f"{prefix}/runs/{run_id}/openai/cs/",
        "AWS_FAKE_LIST_KEYS": f'["{ranked_key}"]',
        "AWS_FAKE_LIST_PREFIX_2": f"{prefix}/latest/openai/cs/",
        "AWS_FAKE_LIST_KEYS_2": f'["{latest_key}"]',
        "AWS_FAKE_HEAD_KEYS": (
            f"{run_report_key}|application/json;"
            f"{ranked_key}|application/json;"
            f"{latest_key}|application/json"
        ),
        "AWS_FAKE_OBJ_URI_1": f"s3://{bucket}/{run_report_key}",
        "AWS_FAKE_OBJ_BODY_1": '{"run_id":"run-123"}',
        "AWS_FAKE_OBJ_URI_2": f"s3://{bucket}/{ranked_key}",
        "AWS_FAKE_OBJ_BODY_2": "[]",
    }
    result = subprocess.run([bash, str(script)], capture_output=True, text=True, env=env)
    assert result.returncode == 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "Summary: SUCCESS" in combined


def test_verify_publish_s3_missing_aws(tmp_path: Path) -> None:
    bash = shutil.which("bash")
    if not bash:
        pytest.skip("bash not available")
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "verify_publish_s3.sh"
    env = {"PATH": "", "BUCKET": "bucket", "PREFIX": "jobintel", "RUN_ID": "run-123"}
    result = subprocess.run([bash, str(script)], capture_output=True, text=True, env=env)
    assert result.returncode != 0
    combined = (result.stdout or "") + (result.stderr or "")
    assert "aws CLI is required" in combined
