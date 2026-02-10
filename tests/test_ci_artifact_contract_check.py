from __future__ import annotations

from pathlib import Path

import pytest

from scripts import ci_artifact_contract_check


def test_ci_artifact_contract_check_pass_fixture() -> None:
    artifacts = Path("tests/fixtures/ci_artifacts/pass")
    assert ci_artifact_contract_check.main([str(artifacts)]) == 0


def test_ci_artifact_contract_check_fail_fixture_has_deterministic_message() -> None:
    artifacts = Path("tests/fixtures/ci_artifacts/fail_missing_ranked_csv")
    with pytest.raises(RuntimeError) as exc:
        ci_artifact_contract_check.main([str(artifacts)])

    msg = str(exc.value)
    assert "artifact_contract_check failed" in msg
    assert "required_providers=openai" in msg
    assert "required_profiles=cs" in msg
    assert "missing=openai_ranked_jobs.cs.csv" in msg
