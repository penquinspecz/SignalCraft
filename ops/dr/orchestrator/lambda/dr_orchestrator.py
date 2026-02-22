#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import re
import time
from typing import Any, Dict, List, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

DEFAULT_BACKUP_KEYS = ["metadata.json", "state.tar.zst", "manifests.tar.zst"]
TERMINAL_SSM_STATUSES = {"Success", "Cancelled", "Failed", "TimedOut", "Cancelling"}


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _json_dumps(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, indent=2) + "\n"


def _safe_execution_id(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_") or "unknown_execution"


def _client(service: str, region: str):
    session = boto3.session.Session(region_name=region)
    return session.client(service)


def _ensure_account(region: str, expected_account_id: str) -> str:
    if not expected_account_id:
        raise RuntimeError("expected_account_id is required")
    sts = _client("sts", region)
    actual = sts.get_caller_identity()["Account"]
    if actual != expected_account_id:
        raise RuntimeError(f"AWS account mismatch: expected={expected_account_id} actual={actual}")
    return actual


def _parse_iso8601(value: str) -> Optional[dt.datetime]:
    txt = (value or "").strip()
    if not txt:
        return None
    try:
        normalized = txt.replace("Z", "+00:00")
        parsed = dt.datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=dt.timezone.utc)
        return parsed.astimezone(dt.timezone.utc)
    except ValueError:
        return None


def _tail(text: str, limit: int = 4000) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _s3_put_json(region: str, bucket: str, key: str, payload: Dict[str, Any]) -> None:
    s3 = _client("s3", region)
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=_json_dumps(payload).encode("utf-8"),
        ContentType="application/json",
    )


def _write_receipt(
    *,
    region: str,
    bucket: str,
    prefix: str,
    execution_id: str,
    phase: str,
    status: str,
    payload: Dict[str, Any],
) -> str:
    clean_prefix = prefix.strip("/")
    key = f"{clean_prefix}/{_safe_execution_id(execution_id)}/{phase}.json".strip("/")
    envelope = {
        "schema_version": 1,
        "timestamp_utc": _utc_now(),
        "phase": phase,
        "status": status,
        "payload": payload,
    }
    _s3_put_json(region, bucket, key, envelope)
    return f"s3://{bucket}/{key}"


def _required(event: Dict[str, Any], key: str) -> Any:
    value = event.get(key)
    if value in (None, ""):
        raise RuntimeError(f"missing required input: {key}")
    return value


def _check_health(event: Dict[str, Any], region: str) -> Dict[str, Any]:
    bucket = _required(event, "publish_bucket")
    prefix = str(_required(event, "publish_prefix")).strip("/")
    provider = str(event.get("provider", "openai")).strip()
    profile = str(event.get("profile", "cs")).strip()
    marker_file = str(event.get("expected_marker_file", f"{provider}_top.{profile}.md")).strip()
    max_freshness_hours = float(event.get("max_freshness_hours", 6))
    metric_namespace = str(event.get("metric_namespace", "SignalCraft/DR")).strip()
    force_run = bool(event.get("force_run", False))
    project = str(event.get("project", "signalcraft")).strip()

    s3 = _client("s3", region)
    cloudwatch = _client("cloudwatch", region)

    global_pointer_key = f"{prefix}/state/last_success.json".strip("/")
    provider_pointer_key = f"{prefix}/state/{provider}/{profile}/last_success.json".strip("/")
    marker_key = f"{prefix}/latest/{provider}/{profile}/{marker_file}".strip("/")

    reasons: List[str] = []
    provider_pointer: Dict[str, Any] = {}
    ended_at_raw = ""
    run_id = ""

    try:
        resp = s3.get_object(Bucket=bucket, Key=global_pointer_key)
        global_pointer = json.loads(resp["Body"].read().decode("utf-8"))
        run_id = str(global_pointer.get("run_id", "")).strip()
        ended_at_raw = str(global_pointer.get("ended_at", "")).strip()
        pointer_last_modified = resp["LastModified"].astimezone(dt.timezone.utc)
    except ClientError as exc:
        reasons.append(f"global_last_success_unreadable:{exc.response.get('Error', {}).get('Code', 'Unknown')}")
        pointer_last_modified = None

    ended_at = _parse_iso8601(ended_at_raw)
    reference_time = ended_at or pointer_last_modified
    if reference_time is None:
        age_hours = 1e9
        reasons.append("freshness_reference_missing")
    else:
        age_hours = (dt.datetime.now(dt.timezone.utc) - reference_time).total_seconds() / 3600.0

    freshness_ok = age_hours <= max_freshness_hours
    if not freshness_ok:
        reasons.append(f"stale_pipeline:{age_hours:.2f}h>{max_freshness_hours:.2f}h")

    try:
        resp = s3.get_object(Bucket=bucket, Key=provider_pointer_key)
        provider_pointer = json.loads(resp["Body"].read().decode("utf-8"))
    except ClientError as exc:
        reasons.append(f"provider_last_success_unreadable:{exc.response.get('Error', {}).get('Code', 'Unknown')}")

    if provider_pointer:
        provider_run_id = str(provider_pointer.get("run_id", "")).strip()
        if run_id and provider_run_id and provider_run_id != run_id:
            reasons.append(f"pointer_run_id_mismatch:global={run_id}:provider={provider_run_id}")

    try:
        s3.head_object(Bucket=bucket, Key=marker_key)
    except ClientError as exc:
        reasons.append(f"missing_expected_marker:{marker_key}:{exc.response.get('Error', {}).get('Code', 'Unknown')}")

    publish_correct = not any(
        reason.startswith("provider_last_success_unreadable")
        or reason.startswith("pointer_run_id_mismatch")
        or reason.startswith("missing_expected_marker")
        or reason.startswith("global_last_success_unreadable")
        for reason in reasons
    )

    needs_dr = force_run or (not freshness_ok) or (not publish_correct)

    dimensions = [
        {"Name": "Project", "Value": project},
        {"Name": "Provider", "Value": provider},
        {"Name": "Profile", "Value": profile},
    ]
    cloudwatch.put_metric_data(
        Namespace=metric_namespace,
        MetricData=[
            {
                "MetricName": "PipelineFreshnessHours",
                "Dimensions": dimensions,
                "Timestamp": dt.datetime.now(dt.timezone.utc),
                "Value": age_hours,
                "Unit": "None",
            },
            {
                "MetricName": "PublishCorrectness",
                "Dimensions": dimensions,
                "Timestamp": dt.datetime.now(dt.timezone.utc),
                "Value": 0 if publish_correct else 1,
                "Unit": "Count",
            },
            {
                "MetricName": "NeedsDR",
                "Dimensions": dimensions,
                "Timestamp": dt.datetime.now(dt.timezone.utc),
                "Value": 1 if needs_dr else 0,
                "Unit": "Count",
            },
        ],
    )

    return {
        "needs_dr": needs_dr,
        "pipeline_freshness_hours": round(age_hours, 3),
        "pipeline_freshness_ok": freshness_ok,
        "publish_correctness_ok": publish_correct,
        "run_id": run_id,
        "global_pointer_key": global_pointer_key,
        "provider_pointer_key": provider_pointer_key,
        "expected_marker_key": marker_key,
        "reasons": reasons,
    }


def _flatten_instances(response: Dict[str, Any]) -> List[Dict[str, Any]]:
    instances: List[Dict[str, Any]] = []
    for reservation in response.get("Reservations", []):
        instances.extend(reservation.get("Instances", []))
    return instances


def _resolve_runner(event: Dict[str, Any], region: str) -> Dict[str, Any]:
    ec2 = _client("ec2", region)
    runner_name = str(event.get("dr_runner_name", "jobintel-dr-runner")).strip()
    response = ec2.describe_instances(
        Filters=[
            {"Name": "tag:Name", "Values": [runner_name]},
            {"Name": "tag:Purpose", "Values": ["jobintel-dr"]},
            {"Name": "tag:ManagedBy", "Values": ["terraform"]},
            {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped"]},
        ]
    )
    instances = _flatten_instances(response)
    if len(instances) != 1:
        raise RuntimeError(
            f"expected exactly one DR runner instance (Name={runner_name}, Purpose=jobintel-dr, ManagedBy=terraform), found={len(instances)}"
        )

    instance = instances[0]
    security_groups = instance.get("SecurityGroups", [])
    return {
        "instance_id": instance["InstanceId"],
        "instance_state": instance["State"]["Name"],
        "public_ip": instance.get("PublicIpAddress", ""),
        "private_ip": instance.get("PrivateIpAddress", ""),
        "key_name": instance.get("KeyName", ""),
        "security_group_id": security_groups[0]["GroupId"] if security_groups else "",
    }


def _parse_backup_input(event: Dict[str, Any]) -> Tuple[str, str, str]:
    backup_uri = str(event.get("backup_uri", "")).strip()
    if backup_uri:
        match = re.match(r"^s3://([^/]+)/(.+)$", backup_uri)
        if not match:
            raise RuntimeError(f"invalid backup_uri: {backup_uri}")
        bucket, key_prefix = match.group(1), match.group(2).strip("/")
        return bucket, key_prefix, backup_uri

    bucket = str(event.get("backup_bucket", "")).strip()
    prefix = str(event.get("backup_prefix", "")).strip("/")
    backup_id = str(event.get("backup_id", "")).strip()
    if not bucket or not prefix or not backup_id:
        raise RuntimeError("backup input missing: provide backup_uri or backup_bucket+backup_prefix+backup_id")
    key_prefix = f"{prefix}/backups/{backup_id}".strip("/")
    return bucket, key_prefix, f"s3://{bucket}/{key_prefix}"


def _restore(event: Dict[str, Any], region: str) -> Dict[str, Any]:
    bucket, backup_key_prefix, backup_uri = _parse_backup_input(event)
    required_keys = event.get("backup_required_keys") or DEFAULT_BACKUP_KEYS
    if not isinstance(required_keys, list) or not required_keys:
        raise RuntimeError("backup_required_keys must be a non-empty list")

    s3 = _client("s3", region)
    checked: List[Dict[str, Any]] = []
    missing: List[str] = []
    for rel in required_keys:
        key = f"{backup_key_prefix}/{str(rel).strip('/')}".strip("/")
        try:
            head = s3.head_object(Bucket=bucket, Key=key)
            checked.append(
                {
                    "key": key,
                    "content_length": int(head.get("ContentLength", 0)),
                    "etag": str(head.get("ETag", "")).strip('"'),
                }
            )
        except ClientError:
            missing.append(key)

    if missing:
        raise RuntimeError(f"backup contract failed, missing keys: {missing}")

    return {
        "backup_uri": backup_uri,
        "checked_keys": checked,
    }


def _poll_ssm_command(region: str, command_id: str, instance_id: str, timeout_seconds: int) -> Dict[str, Any]:
    ssm = _client("ssm", region)
    deadline = time.time() + timeout_seconds
    last_status = "Pending"
    while time.time() < deadline:
        inv = ssm.get_command_invocation(CommandId=command_id, InstanceId=instance_id)
        status = inv.get("Status", "Unknown")
        last_status = status
        if status in TERMINAL_SSM_STATUSES:
            return inv
        time.sleep(5)
    raise RuntimeError(f"ssm command timeout after {timeout_seconds}s (last_status={last_status})")


def _validate(event: Dict[str, Any], region: str) -> Dict[str, Any]:
    instance_id = str(event.get("instance_id", "")).strip()
    namespace = str(event.get("namespace", "jobintel")).strip()
    timeout_seconds = int(event.get("validate_timeout_seconds", 900))
    if not instance_id:
        raise RuntimeError("instance_id is required for validate action")

    commands = [
        "set -euo pipefail",
        "sudo test -s /etc/rancher/k3s/k3s.yaml",
        "sudo k3s kubectl get nodes -o wide",
        f"sudo k3s kubectl get ns {namespace}",
    ]
    ssm = _client("ssm", region)
    send = ssm.send_command(
        InstanceIds=[instance_id],
        DocumentName="AWS-RunShellScript",
        Parameters={"commands": commands},
        TimeoutSeconds=timeout_seconds,
    )

    command_id = send["Command"]["CommandId"]
    invocation = _poll_ssm_command(region, command_id, instance_id, timeout_seconds)
    status = invocation.get("Status", "Unknown")
    stdout = invocation.get("StandardOutputContent", "")
    stderr = invocation.get("StandardErrorContent", "")

    result = {
        "command_id": command_id,
        "status": status,
        "stdout_tail": _tail(stdout),
        "stderr_tail": _tail(stderr),
    }
    if status != "Success":
        raise RuntimeError(f"validate failed: status={status} stderr_tail={_tail(stderr, 800)}")
    return result


def _notify(event: Dict[str, Any], region: str) -> Dict[str, Any]:
    topic_arn = str(event.get("notification_topic_arn", "")).strip()
    summary = event.get("summary") if isinstance(event.get("summary"), dict) else {}
    message = {
        "kind": "dr_orchestrator_status",
        "timestamp_utc": _utc_now(),
        "status": str(event.get("status", "completed")).strip(),
        "execution_id": str(event.get("execution_id", "")).strip(),
        "details": summary,
    }
    if not topic_arn:
        return {"published": False, "reason": "notification_topic_arn not set", "message": message}

    sns = _client("sns", region)
    publish = sns.publish(
        TopicArn=topic_arn,
        Subject="SignalCraft DR Orchestrator Status",
        Message=_json_dumps(message),
    )
    return {"published": True, "message_id": publish.get("MessageId", ""), "message": message}


def _request_manual_approval(event: Dict[str, Any], region: str) -> Dict[str, Any]:
    topic_arn = str(_required(event, "notification_topic_arn")).strip()
    task_token = str(_required(event, "task_token")).strip()
    execution_id = str(event.get("execution_id", "")).strip()
    summary = event.get("summary") if isinstance(event.get("summary"), dict) else {}

    message = {
        "kind": "dr_orchestrator_manual_approval_required",
        "timestamp_utc": _utc_now(),
        "execution_id": execution_id,
        "summary": summary,
        "instructions": {
            "approve": 'aws stepfunctions send-task-success --task-token \'<TASK_TOKEN>\' --task-output \'{"approved":true,"approver":"<name>","ticket":"<id>"}\'',
            "reject": 'aws stepfunctions send-task-success --task-token \'<TASK_TOKEN>\' --task-output \'{"approved":false,"approver":"<name>","reason":"<reason>"}\'',
            "task_token": task_token,
        },
        "note": "Auto-promote is disabled; approval only records decision and readiness state.",
    }
    sns = _client("sns", region)
    publish = sns.publish(
        TopicArn=topic_arn,
        Subject="SignalCraft DR Manual Approval Required",
        Message=_json_dumps(message),
    )
    return {
        "published": True,
        "message_id": publish.get("MessageId", ""),
        "task_token_hint": f"{task_token[:10]}...{task_token[-6:]}" if len(task_token) > 20 else "short-token",
    }


def _promote(event: Dict[str, Any], region: str) -> Dict[str, Any]:
    del region
    approved = bool(event.get("approved", False))
    approver = str(event.get("approver", "")).strip()
    reason = str(event.get("reason", "")).strip()
    ticket = str(event.get("ticket", "")).strip()
    execution_id = str(event.get("execution_id", "")).strip()
    return {
        "approved": approved,
        "approver": approver,
        "reason": reason,
        "ticket": ticket,
        "execution_id": execution_id,
        "idempotency_key": f"promote:{execution_id}:{approved}:{approver}:{ticket}",
        "promotion_status": "approved_but_auto_promote_disabled" if approved else "manual_promotion_rejected",
    }


def _phase_response(
    *,
    phase_name: str,
    phase_inputs: Dict[str, Any],
    phase_outputs: Dict[str, Any],
    receipt_uri: str,
    failure_reason: str,
) -> Dict[str, Any]:
    return {
        "ok": failure_reason == "",
        "phase_name": phase_name,
        "phase_inputs": phase_inputs,
        "phase_outputs": phase_outputs,
        "receipt_uri": receipt_uri,
        "failure_reason": failure_reason,
    }


def handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    action = str(event.get("action", "")).strip()
    if not action:
        raise RuntimeError("action is required")

    region = str(event.get("region") or os.environ.get("AWS_REGION") or "us-east-1").strip()
    expected_account_id = str(event.get("expected_account_id", "")).strip()
    execution_id = str(event.get("execution_id") or getattr(context, "aws_request_id", "unknown")).strip()
    receipt_bucket = str(event.get("receipt_bucket", "")).strip()
    receipt_prefix = str(event.get("receipt_prefix", "")).strip()

    account_id = _ensure_account(region, expected_account_id)

    actions = {
        "check_health": _check_health,
        "resolve_runner": _resolve_runner,
        "restore": _restore,
        "validate": _validate,
        "notify": _notify,
        "request_manual_approval": _request_manual_approval,
        "promote": _promote,
    }
    if action not in actions:
        raise RuntimeError(f"unsupported action: {action}")

    receipt_uri = ""
    try:
        result = actions[action](event, region)
        result["account_id"] = account_id
        result["region"] = region
        if receipt_bucket and receipt_prefix:
            receipt_uri = _write_receipt(
                region=region,
                bucket=receipt_bucket,
                prefix=receipt_prefix,
                execution_id=execution_id,
                phase=action,
                status="ok",
                payload={"input": event, "result": result},
            )
        return _phase_response(
            phase_name=action,
            phase_inputs=event,
            phase_outputs=result,
            receipt_uri=receipt_uri,
            failure_reason="",
        )
    except Exception as exc:
        reason = str(exc)
        if receipt_bucket and receipt_prefix:
            receipt_uri = _write_receipt(
                region=region,
                bucket=receipt_bucket,
                prefix=receipt_prefix,
                execution_id=execution_id,
                phase=action,
                status="error",
                payload={"input": event, "error": reason},
            )
        raise RuntimeError(f"{action} failed: {reason}; receipt={receipt_uri}")
