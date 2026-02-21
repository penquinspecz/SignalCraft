from __future__ import annotations

import json

from scripts import dashboard_offline_sanity


def test_dashboard_offline_sanity_run_checks_passes() -> None:
    summary = dashboard_offline_sanity.run_checks()

    assert summary["status"] == "ok"
    assert summary["artifacts_checked"] == 4
    assert summary["category_checks_passed"] == 4
    assert summary["artifact_model_checks_passed"] == 4
    assert summary["schema_checks_passed"] == 4
    assert summary["forbidden_field_checks_passed"] == 4
    assert summary["errors"] == []


def test_dashboard_offline_sanity_json_output_is_stable(capsys) -> None:
    exit_code = dashboard_offline_sanity.main(["--json"])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert payload["artifacts_checked"] == 4
    assert payload["errors"] == []
