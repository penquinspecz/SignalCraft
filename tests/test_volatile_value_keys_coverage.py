"""
Tests that VOLATILE_VALUE_KEYS in compare_run_artifacts.py covers all
timestamp/duration fields defined in artifact schemas.

Phase2-C12: ensures new timestamp fields cannot silently break comparisons.
"""

from __future__ import annotations

import json
import pathlib
import re

import pytest

from scripts.compare_run_artifacts import VOLATILE_VALUE_KEYS

SCHEMA_DIR = pathlib.Path(__file__).resolve().parent.parent / "schemas"

# Patterns that identify timestamp or duration fields in JSON schemas.
TIMESTAMP_FIELD_PATTERNS = re.compile(
    r"(created_at|ended_at|fetched_at|generated_at|run_started_at|"
    r"scored_at|scraped_at|started_at|^timestamp$|updated_at|"
    r"duration_sec|captured_at|completed_at|began_at|finished_at|"
    r"processed_at|published_at|_at_utc|_at$|_timestamp(?:_utc)?$|_duration)",
    re.IGNORECASE,
)


def _extract_field_names_from_schema(schema_path: pathlib.Path) -> set[str]:
    """Extract all property names from a JSON schema file."""
    text = schema_path.read_text(encoding="utf-8")
    data = json.loads(text)
    fields: set[str] = set()

    def _walk(obj: dict | list, depth: int = 0) -> None:
        if depth > 20:
            return
        if isinstance(obj, dict):
            properties = obj.get("properties")
            if isinstance(properties, dict):
                fields.update(str(key) for key in properties.keys())
            for value in obj.values():
                _walk(value, depth + 1)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item, depth + 1)

    _walk(data)
    return fields


class TestVolatileValueKeysCoverage:
    """Ensure all timestamp/duration fields in schemas are in VOLATILE_VALUE_KEYS."""

    def test_all_schemas_have_timestamp_fields_covered(self) -> None:
        """Every timestamp-like field in every schema must be in VOLATILE_VALUE_KEYS."""
        schemas = sorted(SCHEMA_DIR.glob("*.json"))
        assert schemas, "No schemas found"

        uncovered: list[tuple[str, str]] = []
        for schema_path in schemas:
            fields = _extract_field_names_from_schema(schema_path)
            for field in fields:
                if TIMESTAMP_FIELD_PATTERNS.search(field) and field not in VOLATILE_VALUE_KEYS:
                    uncovered.append((schema_path.name, field))

        if uncovered:
            msg_lines = ["Timestamp/duration fields not in VOLATILE_VALUE_KEYS:"]
            for schema_name, field in sorted(uncovered):
                msg_lines.append(f"  {schema_name}: {field}")
            msg_lines.append(
                "\nAdd these fields to VOLATILE_VALUE_KEYS in "
                "scripts/compare_run_artifacts.py"
            )
            pytest.fail("\n".join(msg_lines))

    def test_generated_at_is_covered(self) -> None:
        """Explicit check that 'generated_at' is in VOLATILE_VALUE_KEYS."""
        assert "generated_at" in VOLATILE_VALUE_KEYS, (
            "'generated_at' must be in VOLATILE_VALUE_KEYS "
            "(AI insights uses this field)"
        )

    def test_generated_at_utc_is_covered(self) -> None:
        """Explicit check that 'generated_at_utc' is in VOLATILE_VALUE_KEYS."""
        assert "generated_at_utc" in VOLATILE_VALUE_KEYS
