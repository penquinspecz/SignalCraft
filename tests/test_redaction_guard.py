from __future__ import annotations

import pytest

from ji_engine.proof.bundle import assert_no_secrets, find_secret_matches, redact_text


def test_find_secret_matches_detects_known_patterns() -> None:
    text = "\n".join(
        [
            "AWS_ACCESS_KEY_ID=AKIA_TEST_NOT_A_REAL_KEY_0000",
            "Authorization: Bearer token_abcdefghijklmnopqrstuvwxyz12345",
            "https://discord.invalid/webhook/__REDACTED__",
        ]
    )
    matches = find_secret_matches(text)
    names = sorted({m.pattern for m in matches})
    assert names == ["aws_access_key_id", "bearer_token", "discord_webhook"]


def test_assert_no_secrets_fails_closed() -> None:
    with pytest.raises(ValueError):
        assert_no_secrets(path=__file__, text="AKIA_TEST_NOT_A_REAL_KEY_0000", allow_secrets=False)


def test_assert_no_secrets_allows_override() -> None:
    assert_no_secrets(path=__file__, text="AKIA_TEST_NOT_A_REAL_KEY_0000", allow_secrets=True)


def test_redact_text_replaces_secrets() -> None:
    redacted = redact_text("Bearer abcdefghijklmnopqrstuvwxyz12345")
    assert "REDACTED" in redacted
    assert "abcdefghijklmnopqrstuvwxyz" not in redacted
