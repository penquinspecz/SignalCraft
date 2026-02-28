#!/usr/bin/env bash
set -euo pipefail

workdir="$(mktemp -d)"
trap 'rm -rf "${workdir}"' EXIT

in_json="${workdir}/in.json"
out_json="${workdir}/out.json"
out2_json="${workdir}/out2.json"

cat > "${in_json}" <<'JSON'
{
  "events": [
    {"message": "ok", "timestamp": 1}
  ],
  "nextForwardToken": "f/abc123/s",
  "nextBackwardToken": "b/def456/s",
  "nested": {
    "nextToken": "ghi789",
    "keep": "value"
  }
}
JSON

python3 scripts/ops/redact_cloudwatch_tokens.py --input "${in_json}" --output "${out_json}"
python3 scripts/ops/redact_cloudwatch_tokens.py --input "${out_json}" --output "${out2_json}"

python3 - <<'PY' "${out_json}"
import json
import sys

doc = json.load(open(sys.argv[1], "r", encoding="utf-8"))
assert doc["nextForwardToken"] == "<REDACTED>"
assert doc["nextBackwardToken"] == "<REDACTED>"
assert doc["nested"]["nextToken"] == "<REDACTED>"
assert doc["nested"]["keep"] == "value"
print("PASS: token keys redacted, non-token keys preserved")
PY

cmp -s "${out_json}" "${out2_json}"
echo "PASS: idempotent redaction"
