from __future__ import annotations

from ji_engine.proof.politeness_proof import (
    ScriptedStatusSequence,
    provider_payload,
    required_politeness_issues,
)


def test_scripted_status_sequence_is_deterministic_and_saturates() -> None:
    sequence = ScriptedStatusSequence.parse("503,429,200")
    assert sequence.status_for_request(0) == 503
    assert sequence.status_for_request(1) == 429
    assert sequence.status_for_request(2) == 200
    assert sequence.status_for_request(9) == 200


def test_required_politeness_issues_passes_for_provider_scoped_payload() -> None:
    log_text = "\n".join(
        [
            "2026-02-07 00:00:00 INFO [provider_retry][robots] provider=proof_ashby host=127.0.0.1",
            "2026-02-07 00:00:00 INFO [provider_retry][backoff] provider=proof_ashby attempt=1 sleep_s=0.100 reason=network_error status=503",
            "2026-02-07 00:00:00 WARNING [provider_retry][circuit_breaker] provider=proof_ashby failures=1 cooldown_s=600.000",
            (
                "2026-02-07 00:00:00 INFO [run_scrape][provenance] "
                '{"proof_ashby":{"attempts_made":3,"live_attempted":true,"mode":"LIVE","policy_snapshot":{"x":1},"robots_final_allowed":true}}'
            ),
        ]
    )
    issues = required_politeness_issues(log_text=log_text, provider_id="proof_ashby")
    assert issues == []


def test_provider_payload_handles_nested_provider_shape() -> None:
    payload = provider_payload({"proof_ashby": {"mode": "LIVE"}}, "proof_ashby")
    assert payload == {"mode": "LIVE"}
