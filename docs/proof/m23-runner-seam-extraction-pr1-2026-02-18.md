# M23 Runner Seam Extraction PR1 - 2026-02-18

## Runner Decomposition Plan (Module Map)
Current monolith:  (6k+ LOC).

Proposed responsibility split:
- Stage orchestration:
  - 
  - 
- Artifact emission:
  - 
  -  (seam introduced in PR1)
- Failure handling:
  - 
  - 
- Redaction guard:
  - 
- Provider availability:
  - 
- Run report / receipts:
  - 
  - 
- Cost telemetry:
  - 

Notes:
- Keep  as orchestration entrypoint while extracting deterministic, low-coupling seams first.
- Prefer pure-function seams before IO-heavy stage blocks.

## PR1 Extraction Choice
Chosen seam: run path helpers (pure, deterministic, low coupling).

Why this seam:
- No network calls.
- No mutable global state required.
- Existing tests already exercise runner run-id/path behavior ( and broad run artifact tests).

## Extraction Implemented
New module:
- 

Functions moved:
1.  -> 
2.  logic -> 
3.  logic -> 

Integration approach:
-  now imports moved helpers.
- Thin wrappers retained for summary path helpers to minimize call-site churn and preserve behavior.
-  remains available via imported alias for backward compatibility in tests and scripts.

## Runner LOC Delta
- Before:  lines
- After:  lines

## Tests Added/Adjusted
Added:
- 
  - 
  - 
  - 

Validated compatibility:
-  still passes (uses ).

## Commands

audit:
    6075 src/ji_engine/pipeline/runner.py
146:def _unavailable_summary_for(provider: str) -> str:
162:def _unavailable_summary() -> str:
225:def _workspace_paths() -> WorkspacePaths:
253:def _workspace() -> WorkspacePaths:
292:def _run_repository() -> RunRepository:
321:def _flush_logging() -> None:
326:def _warn_if_not_user_writable(paths: List[Path], *, context: str) -> None:
388:def _utcnow_iso() -> str:
392:def _pid_alive(pid: int) -> bool:
404:def _acquire_lock(timeout_sec: int = 0) -> None:
452:def _run(cmd: List[str], *, stage: str) -> None:
516:def _read_json(path: Path) -> Any:
520:def _write_json(path: Path, obj: Any) -> None:
526:def _write_canonical_json(path: Path, obj: Any) -> None:
533:def _redaction_enforce_enabled() -> bool:
537:def _redaction_guard_text(path: Path, text: str) -> None:
548:def _redaction_guard_json(path: Path, payload: Any) -> None:
598:def _build_proof_receipt(
636:def _write_proof_receipt(
657:def _update_run_metadata_s3(path: Path, s3_meta: Dict[str, Any]) -> None:
670:def _update_run_metadata_publish(
690:def _pointer_write_ok(pointer_write: Any) -> bool:
701:def _build_publish_section(
723:def _publish_contract_failed(publish_section: Dict[str, Any]) -> bool:
731:def _resolve_publish_state(
743:def _score_meta_path(ranked_json: Path) -> Path:
747:def _scrape_meta_path(provider: str) -> Path:
751:def _load_scrape_provenance(providers: List[str]) -> Dict[str, Dict[str, Any]]:
768:def _provider_registry_hash(providers_config_path: Path) -> Optional[str]:
781:def _provider_config_map(providers_config_path: Path) -> Dict[str, Dict[str, Any]]:
789:def _provider_mode(provider_cfg: Optional[Dict[str, Any]]) -> str:
805:def _provider_policy_details(meta: Dict[str, Any]) -> Dict[str, Any]:
829:def _provider_reason_code(
862:def _write_provider_availability_artifact(
939:def _resolve_trigger_type() -> str:
946:def _resolve_actor() -> str:
965:def _current_profile_hash(candidate_id: str) -> Optional[str]:
976:def _previous_profile_hash(previous_run: Optional[Dict[str, Any]]) -> Optional[str]:
999:def _config_hashes(providers_config_path: Path, config_fingerprint: str) -> Dict[str, Optional[str]]:
1008:def _write_run_audit_artifact(
1044:def _get_env_float(name: str, default: float) -> float:
1054:def _get_env_int(name: str, default: int) -> int:
1064:def _provider_policy_thresholds() -> Dict[str, float]:
1072:def _load_enrich_stats(enriched_path: Path) -> Dict[str, int]:
1102:def _evaluate_provider_policy(
1154:def _ecs_task_arn_from_metadata() -> Optional[str]:
1182:def _resolve_ecs_task_arn() -> str:
1194:def _apply_score_fallback_metadata(selection: Dict[str, Any], ranked_json: Path) -> None:
1206:def _run_metadata_path(run_id: str) -> Path:
1211:def _run_health_path(run_id: str) -> Path:
1215:def _run_health_schema() -> Dict[str, Any]:
1223:def _run_summary_path(run_id: str) -> Path:
1227:def _run_summary_schema() -> Dict[str, Any]:
1235:def _provider_availability_path(run_id: str) -> Path:
1239:def _run_audit_path(run_id: str) -> Path:
1243:def _provider_availability_schema() -> Dict[str, Any]:
1251:def _run_audit_schema() -> Dict[str, Any]:
1259:def _summary_path_text(path: Path) -> str:
1263:def _resolve_summary_path(path_value: str) -> Path:
1267:def _artifact_pointer(path: Optional[Path], *, sha_hint: Optional[str] = None) -> Dict[str, Any]:
1282:def _run_report_pointer(run_id: str) -> Dict[str, Any]:
1292:def _ranked_output_pointers(run_report_payload: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
1330:def _primary_artifact_filename(output_key: str, provider: str, profile: str) -> Optional[str]:
1339:def _primary_artifacts(
1417:def _extract_scoring_config_reference(run_report_payload: Dict[str, Any]) -> Dict[str, Any]:
1463:def _snapshot_manifest_reference(run_report_payload: Dict[str, Any]) -> Dict[str, Any]:
1485:def _build_run_summary_payload(
1551:def _write_run_summary_artifact(
1607:def _phase_for_stage(stage_name: str) -> Optional[str]:
1622:def _coerce_duration(value: Any) -> float:
1629:def _duration_between_iso(started_at: Optional[str], ended_at: Optional[str]) -> Optional[float]:
1640:def _failure_code_for_context(
1706:def _build_run_health_payload(
1798:def _write_run_health_artifact(
1825:def _resolve_providers(args: argparse.Namespace) -> List[str]:
1838:def _resolve_output_dir() -> Path:
1848:def _provider_raw_jobs_json(provider: str) -> Path:
1854:def _provider_labeled_jobs_json(provider: str) -> Path:
1860:def _provider_enriched_jobs_json(provider: str) -> Path:
1866:def _alerts_paths(provider: str, profile: str) -> Tuple[Path, Path]:
1873:def _last_seen_path(provider: str, profile: str) -> Path:
1877:def _provider_ai_jobs_json(provider: str) -> Path:
1883:def _provider_ranked_jobs_json(provider: str, profile: str) -> Path:
1889:def _provider_ranked_jobs_csv(provider: str, profile: str) -> Path:
1895:def _provider_ranked_families_json(provider: str, profile: str) -> Path:
1901:def _provider_shortlist_md(provider: str, profile: str) -> Path:
1907:def _provider_top_md(provider: str, profile: str) -> Path:
1911:def _provider_diff_paths(provider: str, profile: str) -> Tuple[Path, Path]:
1918:def _state_last_ranked(provider: str, profile: str) -> Path:
1924:def _local_last_success_pointer_paths(provider: str, profile: str) -> List[Path]:
1933:def _resolve_local_last_success_ranked(provider: str, profile: str, current_run_id: str) -> Optional[Path]:
1951:def _resolve_latest_run_ranked(provider: str, profile: str, current_run_id: str) -> Optional[Path]:
1975:def _resolve_latest_run_ranked_legacy_scan(provider: str, profile: str, current_run_id: str) -> Optional[Path]:
1998:def _history_run_dir(run_id: str, profile: str, provider: Optional[str] = None) -> Path:
2006:def _latest_profile_dir(profile: str, provider: Optional[str] = None) -> Path:
2012:def _copy_artifact(src: Path, dest: Path) -> None:
2019:def _atomic_copy(src: Path, dest: Path) -> None:
2033:def _archive_input(
2063:def _archive_run_inputs(
2088:def _run_registry_dir(run_id: str) -> Path:
2095:def _write_run_registry(
2184:def _archive_profile_artifacts(
2215:def _persist_run_metadata(
2391:def _candidate_input_provenance(candidate_id: str) -> Dict[str, Any]:
2403:def _hash_file(path: Path) -> Optional[str]:
2412:def _count_jobs(path: Path) -> Optional[int]:
2424:def _classified_counts_by_provider(providers: List[str]) -> Dict[str, int]:
2434:def _baseline_latest_dir(provider: str, profile: str) -> Path:
2439:def _baseline_ranked_path(provider: str, profile: str, baseline_dir: Path) -> Path:
2443:def _baseline_run_info(baseline_dir: Path) -> Tuple[Optional[str], Optional[str]]:
2455:def _resolve_s3_baseline(
2588:def _build_delta_summary(run_id: str, providers: List[str], profiles: List[str]) -> Dict[str, Any]:
2648:def _file_metadata(path: Path) -> Dict[str, Optional[str]]:
2656:def _candidate_metadata(path: Path) -> Dict[str, Optional[str]]:
2662:def _output_metadata(path: Path) -> Dict[str, Optional[str]]:
2669:def _config_fingerprint(flags: Dict[str, Any], providers_config: Optional[str]) -> str:
2709:def _environment_fingerprint() -> Dict[str, Optional[str]]:
2727:def _verifiable_artifacts(
2744:def _best_effort_git_sha() -> Optional[str]:
2762:def _normalize_exit_code(code: Any) -> int:
2775:def _resolve_score_input_path_for(args: argparse.Namespace, provider: str) -> Tuple[Optional[Path], Optional[str]]:
2825:def _score_input_selection_detail_for(args: argparse.Namespace, provider: str) -> Dict[str, Any]:
3039:def _resolve_score_input_path(args: argparse.Namespace) -> Tuple[Optional[Path], Optional[str]]:
3043:def _score_input_selection_detail(args: argparse.Namespace) -> Dict[str, Any]:
3047:def _safe_len(path: Path) -> int:
3057:def _load_last_run() -> Dict[str, Any]:
3075:def _write_last_run(payload: Dict[str, Any]) -> None:
3081:def _parse_logical_key(logical_key: str) -> Optional[Tuple[str, str, str]]:
3090:def _build_last_success_pointer(run_report: Dict[str, Any], run_report_path: Path) -> Dict[str, Any]:
3124:def _write_last_success_pointer(run_report: Dict[str, Any], run_report_path: Path) -> None:
3138:def validate_config(args: argparse.Namespace, webhook: str) -> None:
3153:def _file_mtime(path: Path) -> Optional[float]:
3160:def _file_mtime_iso(path: Path) -> Optional[str]:
3167:def _setup_logging(json_mode: bool, *, file_sink_path: Optional[Path] = None) -> Optional[str]:
3193:def _run_logs_dir(run_id: str) -> Path:
3197:def _collect_run_log_pointers(run_id: str, file_sink_path: Optional[str]) -> Dict[str, Any]:
3264:def _enforce_run_log_retention(*, run_repository: RunRepository, candidate_id: str, keep_runs: int) -> Dict[str, Any]:
3289:def _should_short_circuit(prev_hashes: Dict[str, Any], curr_hashes: Dict[str, Any]) -> bool:
3296:def _job_key(job: Dict[str, Any]) -> str:
3300:def _job_description_text(job: Dict[str, Any]) -> str:
3306:def _job_field_value(job: Dict[str, Any], field: str) -> Any:
3324:def _hash_job(job: Dict[str, Any]) -> str:
3328:def _load_profile_user_state(profile: str) -> Dict[str, Dict[str, Any]]:
3340:def _user_state_sets(
3365:def _filter_by_ids(items: List[Dict[str, Any]], blocked_ids: set[str]) -> List[Dict[str, Any]]:
3371:def _status_for_item(item: Dict[str, Any], state_map: Dict[str, Dict[str, Any]]) -> str:
3379:def _annotate_and_deprioritize_items(
3397:def _apply_user_state_to_alerts(
3423:def _diff(
3460:def _format_before_after(
3478:def _sort_key_score_url(job: Dict[str, Any]) -> Tuple[float, str]:
3483:def _sort_key_url(job: Dict[str, Any]) -> str:
3488:def format_changes_section(
3567:def _append_shortlist_changes_section(
3604:def _diff_summary_entry(
3635:def _write_diff_summary(run_dir: Path, payload: Dict[str, Any]) -> None:
3655:def _write_identity_diff_artifacts(run_dir: Path, payload: Dict[str, Any]) -> None:
3688:def _dispatch_alerts(
3733:def _resolve_notify_mode(raw_mode: Optional[str]) -> str:
3742:def _should_notify(diff_counts: Dict[str, Any], mode: str) -> bool:
3752:def _maybe_post_run_summary(
3779:def _post_discord(webhook_url: str, message: str) -> bool:
3830:def _post_failure(
3851:def _post_run_summary(
3885:def _briefs_status_line(run_id: str, profile: str) -> Optional[str]:
3903:def _safe_int_env(name: str, default: int = 0) -> int:
3914:def _estimate_tokens_from_text(text: str) -> int:
3918:def _collect_run_costs(
4054:def _write_costs_artifact(run_id: str, payload: Dict[str, Any]) -> Path:
4062:def _rollup_periods_from_run_id(run_id: str) -> Tuple[Optional[str], Optional[str]]:
4071:def _write_ai_accounting_rollups(candidate_id: str) -> Dict[str, str]:
4163:def _all_providers_unavailable(provenance_by_provider: Dict[str, Dict[str, Any]], providers: List[str]) -> bool:
4173:def _provider_unavailable_line(provider: str, meta: Dict[str, Any]) -> Optional[str]:
4183:def _resolve_profiles(args: argparse.Namespace) -> List[str]:
4204:def resolve_stage_order(
4226:def _resolve_history_settings(args: argparse.Namespace) -> Tuple[bool, int, int]:
4252:def _resolve_log_file_enabled(args: argparse.Namespace) -> bool:
4259:def _resolve_semantic_settings() -> Dict[str, Any]:
4297:def _resolve_run_id() -> str:
4304:def main() -> int:

focused tests:
.....                                                                    [100%]
5 passed in 0.14s

full validation:
.venv/bin/python -m ruff check src scripts tests
I001 [*] Import block is un-sorted or un-formatted
   --> src/ji_engine/pipeline/runner.py:13:1
    |
 11 |   """
 12 |
 13 | / from __future__ import annotations
 14 | |
 15 | | import argparse
 16 | | import atexit
 17 | | import importlib
 18 | | import json
 19 | | import logging
 20 | | import os
 21 | | import platform
 22 | | import runpy
 23 | | import shutil
 24 | | import subprocess
 25 | | import sys
 26 | | import tempfile
 27 | | import time
 28 | | import urllib.error
 29 | | import urllib.request
 30 | | from dataclasses import dataclass
 31 | | from datetime import datetime, timezone
 32 | | from pathlib import Path
 33 | | from typing import Any, Callable, Dict, List, Literal, Optional, Tuple
 34 | |
 35 | | from ji_engine.config import (
 36 | |     DEFAULT_CANDIDATE_ID,
 37 | |     ENRICHED_JOBS_JSON,
 38 | |     LABELED_JOBS_JSON,
 39 | |     LOCK_PATH,
 40 | |     RAW_JOBS_JSON,
 41 | |     REPO_ROOT,
 42 | |     candidate_last_run_pointer_path,
 43 | |     candidate_last_run_read_paths,
 44 | |     candidate_last_success_pointer_path,
 45 | |     candidate_last_success_read_paths,
 46 | |     candidate_profile_path,
 47 | |     candidate_state_paths,
 48 | |     ensure_dirs,
 49 | |     ranked_families_json,
 50 | |     ranked_jobs_csv,
 51 | |     ranked_jobs_json,
 52 | |     sanitize_candidate_id,
 53 | | )
 54 | | from ji_engine.config import (
 55 | |     shortlist_md as shortlist_md_path,
 56 | | )
 57 | | from ji_engine.history_retention import update_history_retention, write_history_run_artifacts
 58 | | from ji_engine.pipeline.stages import (
 59 | |     build_ai_augment_command,
 60 | |     build_ai_insights_command,
 61 | |     build_ai_job_briefs_command,
 62 | |     build_classify_command,
 63 | |     build_enrich_command,
 64 | |     build_score_command,
 65 | |     build_scrape_command,
 66 | | )
 67 | | from ji_engine.pipeline.run_pathing import (
 68 | |     resolve_summary_path as _resolve_summary_path_impl,
 69 | |     sanitize_run_id as _sanitize_run_id,
 70 | |     summary_path_text as _summary_path_text_impl,
 71 | | )
 72 | | from ji_engine.providers.registry import (
 73 | |     load_providers_config,
 74 | |     provider_registry_provenance,
 75 | |     provider_tombstone_provenance,
 76 | | )
 77 | | from ji_engine.providers.retry import evaluate_allowlist_policy
 78 | | from ji_engine.providers.selection import DEFAULTS_CONFIG_PATH, select_provider_ids
 79 | | from ji_engine.run_repository import FileSystemRunRepository, RunRepository
 80 | | from ji_engine.scoring import (
 81 | |     ScoringConfig,
 82 | |     ScoringConfigError,
 83 | |     build_scoring_model_metadata,
 84 | |     load_scoring_config,
 85 | | )
 86 | | from ji_engine.semantic.core import DEFAULT_SEMANTIC_MODEL_ID, EMBEDDING_BACKEND_VERSION
 87 | | from ji_engine.semantic.step import finalize_semantic_artifacts, semantic_score_artifact_path
 88 | | from ji_engine.state.run_index import (
 89 | |     append_run_record as append_run_index_record,
 90 | | )
 91 | | from ji_engine.utils.atomic_write import atomic_write_text
 92 | | from ji_engine.utils.content_fingerprint import content_fingerprint
 93 | | from ji_engine.utils.diff_report import build_diff_markdown, build_diff_report
 94 | | from ji_engine.utils.dotenv import load_dotenv
 95 | | from ji_engine.utils.job_identity import job_identity
 96 | | from ji_engine.utils.redaction import scan_json_for_secrets, scan_text_for_secrets
 97 | | from ji_engine.utils.time import utc_now_naive, utc_now_z
 98 | | from ji_engine.utils.user_state import load_user_state_checked, normalize_user_status
 99 | | from ji_engine.utils.verification import (
100 | |     build_verifiable_artifacts,
101 | |     compute_sha256_bytes,
102 | |     compute_sha256_file,
103 | | )
104 | | from jobintel.alerts import (
105 | |     build_last_seen,
106 | |     compute_alerts,
107 | |     load_last_seen,
108 | |     resolve_score_delta,
109 | |     write_alerts,
110 | |     write_last_seen,
111 | | )
112 | | from jobintel.aws_runs import (
113 | |     BaselineInfo,
114 | |     download_baseline_ranked,
115 | |     get_most_recent_successful_run_id_before,
116 | |     parse_pointer,
117 | |     read_last_success_state,
118 | |     read_provider_last_success_state,
119 | |     s3_enabled,
120 | | )
121 | | from jobintel.delta import compute_delta
122 | | from jobintel.discord_notify import build_run_summary_message, post_discord, resolve_webhook
    | |____________________________________________________________________________________________^
123 |
124 |   try:
    |
help: Organize imports

Found 1 error.
[*] 1 fixable with the `--fix` option.
==> ruff
.venv/bin/python -m ruff check src scripts tests
I001 [*] Import block is un-sorted or un-formatted
   --> src/ji_engine/pipeline/runner.py:13:1
    |
 11 |   """
 12 |
 13 | / from __future__ import annotations
 14 | |
 15 | | import argparse
 16 | | import atexit
 17 | | import importlib
 18 | | import json
 19 | | import logging
 20 | | import os
 21 | | import platform
 22 | | import runpy
 23 | | import shutil
 24 | | import subprocess
 25 | | import sys
 26 | | import tempfile
 27 | | import time
 28 | | import urllib.error
 29 | | import urllib.request
 30 | | from dataclasses import dataclass
 31 | | from datetime import datetime, timezone
 32 | | from pathlib import Path
 33 | | from typing import Any, Callable, Dict, List, Literal, Optional, Tuple
 34 | |
 35 | | from ji_engine.config import (
 36 | |     DEFAULT_CANDIDATE_ID,
 37 | |     ENRICHED_JOBS_JSON,
 38 | |     LABELED_JOBS_JSON,
 39 | |     LOCK_PATH,
 40 | |     RAW_JOBS_JSON,
 41 | |     REPO_ROOT,
 42 | |     candidate_last_run_pointer_path,
 43 | |     candidate_last_run_read_paths,
 44 | |     candidate_last_success_pointer_path,
 45 | |     candidate_last_success_read_paths,
 46 | |     candidate_profile_path,
 47 | |     candidate_state_paths,
 48 | |     ensure_dirs,
 49 | |     ranked_families_json,
 50 | |     ranked_jobs_csv,
 51 | |     ranked_jobs_json,
 52 | |     sanitize_candidate_id,
 53 | | )
 54 | | from ji_engine.config import (
 55 | |     shortlist_md as shortlist_md_path,
 56 | | )
 57 | | from ji_engine.history_retention import update_history_retention, write_history_run_artifacts
 58 | | from ji_engine.pipeline.stages import (
 59 | |     build_ai_augment_command,
 60 | |     build_ai_insights_command,
 61 | |     build_ai_job_briefs_command,
 62 | |     build_classify_command,
 63 | |     build_enrich_command,
 64 | |     build_score_command,
 65 | |     build_scrape_command,
 66 | | )
 67 | | from ji_engine.pipeline.run_pathing import (
 68 | |     resolve_summary_path as _resolve_summary_path_impl,
 69 | |     sanitize_run_id as _sanitize_run_id,
 70 | |     summary_path_text as _summary_path_text_impl,
 71 | | )
 72 | | from ji_engine.providers.registry import (
 73 | |     load_providers_config,
 74 | |     provider_registry_provenance,
 75 | |     provider_tombstone_provenance,
 76 | | )
 77 | | from ji_engine.providers.retry import evaluate_allowlist_policy
 78 | | from ji_engine.providers.selection import DEFAULTS_CONFIG_PATH, select_provider_ids
 79 | | from ji_engine.run_repository import FileSystemRunRepository, RunRepository
 80 | | from ji_engine.scoring import (
 81 | |     ScoringConfig,
 82 | |     ScoringConfigError,
 83 | |     build_scoring_model_metadata,
 84 | |     load_scoring_config,
 85 | | )
 86 | | from ji_engine.semantic.core import DEFAULT_SEMANTIC_MODEL_ID, EMBEDDING_BACKEND_VERSION
 87 | | from ji_engine.semantic.step import finalize_semantic_artifacts, semantic_score_artifact_path
 88 | | from ji_engine.state.run_index import (
 89 | |     append_run_record as append_run_index_record,
 90 | | )
 91 | | from ji_engine.utils.atomic_write import atomic_write_text
 92 | | from ji_engine.utils.content_fingerprint import content_fingerprint
 93 | | from ji_engine.utils.diff_report import build_diff_markdown, build_diff_report
 94 | | from ji_engine.utils.dotenv import load_dotenv
 95 | | from ji_engine.utils.job_identity import job_identity
 96 | | from ji_engine.utils.redaction import scan_json_for_secrets, scan_text_for_secrets
 97 | | from ji_engine.utils.time import utc_now_naive, utc_now_z
 98 | | from ji_engine.utils.user_state import load_user_state_checked, normalize_user_status
 99 | | from ji_engine.utils.verification import (
100 | |     build_verifiable_artifacts,
101 | |     compute_sha256_bytes,
102 | |     compute_sha256_file,
103 | | )
104 | | from jobintel.alerts import (
105 | |     build_last_seen,
106 | |     compute_alerts,
107 | |     load_last_seen,
108 | |     resolve_score_delta,
109 | |     write_alerts,
110 | |     write_last_seen,
111 | | )
112 | | from jobintel.aws_runs import (
113 | |     BaselineInfo,
114 | |     download_baseline_ranked,
115 | |     get_most_recent_successful_run_id_before,
116 | |     parse_pointer,
117 | |     read_last_success_state,
118 | |     read_provider_last_success_state,
119 | |     s3_enabled,
120 | | )
121 | | from jobintel.delta import compute_delta
122 | | from jobintel.discord_notify import build_run_summary_message, post_discord, resolve_webhook
    | |____________________________________________________________________________________________^
123 |
124 |   try:
    |
help: Organize imports

Found 1 error.
[*] 1 fixable with the `--fix` option.
==> pytest
.venv/bin/python -m pytest -q
........................................................................ [ 10%]
...............ssss..................................................... [ 20%]
........................................................................ [ 31%]
.........................................................ss............. [ 41%]
........................................................................ [ 51%]
........................ss.....................sss......s............... [ 62%]
........................................................................ [ 72%]
........................................................................ [ 82%]
........................................................................ [ 93%]
.....................................s....s....                          [100%]
681 passed, 16 skipped in 41.72s
==> snapshot immutability
PYTHONPATH=src .venv/bin/python scripts/verify_snapshots_immutable.py
data/anthropic_snapshots/index.html: sha256=3c2f5fcfa255fe7115675c6cc0fb4d3f3db5b8442aac2ad63fb96cf93f18c250 bytes=818
data/cohere_snapshots/index.html: sha256=3539f09a4c0e695b0950fb8187ff6e6db2cb0463d6fd28b2a7052c6bcc19b35d bytes=1590
data/huggingface_snapshots/index.html: sha256=e707d5492b081c43e87dc660fd4134983c3b2caca1a43890282da7b7bc17c238 bytes=1940
data/mistral_snapshots/index.html: sha256=8bbedb1626e75074b72cd529345a1cd2764688b63a53a220208cb0f0a5c7525e bytes=1590
data/openai_snapshots/index.html: sha256=db859f209b7e1eeeaa385d9dab87d02f9ee72217e5afa57edebc21932b586ffc bytes=504376
data/perplexity_snapshots/index.html: sha256=d551252792f03d7aa864fc08d7c9455a4e0811a1388b09911014c8781b66a3ab bytes=1528
data/replit_snapshots/index.html: sha256=f5026bb25896c19492a2cf9db0389bed4f03af93e0cc7cccc4b00b89b25f9fcd bytes=914
data/scaleai_snapshots/index.html: sha256=a3cef755cd17abd623be630eaf863b0a2b1c83ee3bf391b80a33e619f152f88a bytes=924
==> replay smoke
CAREERS_MODE=SNAPSHOT PYTHONPATH=src .venv/bin/python scripts/replay_smoke_fixture.py
PASS: all artifacts match run report hashes
REPLAY REPORT
input:enriched_jobs_json: expected=a5e52c08fe2123372d176a0b4acd2f75d4a638a934a4cbb1eb86ef13ea41d5ea actual=a5e52c08fe2123372d176a0b4acd2f75d4a638a934a4cbb1eb86ef13ea41d5ea match=True
scoring_input:cs: expected=a5e52c08fe2123372d176a0b4acd2f75d4a638a934a4cbb1eb86ef13ea41d5ea actual=a5e52c08fe2123372d176a0b4acd2f75d4a638a934a4cbb1eb86ef13ea41d5ea match=True
output:ranked_csv: expected=94728d55148effda31db88be62d29d947375b55cba92ad61b1cef4cfe2846ecf actual=94728d55148effda31db88be62d29d947375b55cba92ad61b1cef4cfe2846ecf match=True
output:ranked_families_json: expected=d707459c036035d9a716924d2aa50f7b1c7ff66987d243aaef7629c8a679ce3f actual=d707459c036035d9a716924d2aa50f7b1c7ff66987d243aaef7629c8a679ce3f match=True
output:ranked_json: expected=f6100fed8446ca9609c8a1fe78384b6e87037b2e0f47838db9a198b91f00f8c0 actual=f6100fed8446ca9609c8a1fe78384b6e87037b2e0f47838db9a198b91f00f8c0 match=True
output:shortlist_md: expected=4a1a468e12aaf654de0928db760555a31c8ce721d1c23ce126e6d42f2a23fc38 actual=4a1a468e12aaf654de0928db760555a31c8ce721d1c23ce126e6d42f2a23fc38 match=True
SUMMARY: checked=6 matched=6 mismatched=0 missing=0
