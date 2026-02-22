from __future__ import annotations

from ji_engine.utils.redaction import scan_json_for_secrets, scan_text_for_secrets


def test_scan_text_for_secrets_detects_known_patterns() -> None:
    text = "\n".join(
        [
            "AWS_ACCESS_KEY_ID=AKIA_TEST_NOT_A_REAL_KEY_0000",
            "Authorization: Bearer token_abcdefghijklmnopqrstuvwxyz12345",
            "https://discord.invalid/webhook/__REDACTED__",
            "GITHUB_PAT_TEST_PLACEHOLDER",
            "GITHUB_TOKEN_TEST_PLACEHOLDER",
            "OPENAI_API_KEY=OPENAI_TEST_KEY_PLACEHOLDER",
            "aws_secret_access_key = AWS_SECRET_TEST_PLACEHOLDER",
        ]
    )
    findings = scan_text_for_secrets(text)
    patterns = sorted({item.pattern for item in findings})
    assert patterns == [
        "aws_access_key_id",
        "aws_secret_access_key_pair",
        "bearer_token",
        "discord_webhook",
        "github_pat",
        "github_token",
        "openai_api_key",
    ]


def test_scan_text_for_secrets_does_not_flag_random_strings() -> None:
    text = "hash=0123456789abcdef0123456789abcdef01234567 and tokenish value abcdefghijklmnopqrs"
    assert scan_text_for_secrets(text) == []


def test_aws_secret_heuristic_requires_access_key_pairing() -> None:
    text = "aws_secret_access_key=AWS_SECRET_TEST_PLACEHOLDER"
    assert scan_text_for_secrets(text) == []


def test_scan_json_for_secrets_reports_deterministic_locations() -> None:
    payload = {
        "provenance": {
            "token": "Bearer token_abcdefghijklmnopqrstuvwxyz12345",
        },
        "items": [
            {"url": "https://discord.invalid/webhook/__REDACTED__"},
            {"note": "safe"},
        ],
    }
    findings = scan_json_for_secrets(payload)
    assert [(item.pattern, item.location) for item in findings] == [
        ("discord_webhook", "items[0].url"),
        ("bearer_token", "provenance.token"),
    ]
