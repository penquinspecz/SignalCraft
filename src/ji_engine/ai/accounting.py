from __future__ import annotations

import os
from decimal import ROUND_HALF_UP, Decimal
from typing import Dict


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def _env_decimal(name: str, default: str = "0") -> Decimal:
    raw = (os.environ.get(name) or "").strip()
    value = raw if raw else default
    try:
        dec = Decimal(value)
    except Exception:
        return Decimal(default)
    return max(dec, Decimal("0"))


def _parse_decimal(value: str, default: str = "0") -> Decimal:
    try:
        dec = Decimal(value)
    except Exception:
        return Decimal(default)
    return max(dec, Decimal("0"))


def resolve_model_rates(model: str) -> Dict[str, str]:
    key = "".join(ch if ch.isalnum() else "_" for ch in model.upper())
    in_rate = _env_decimal(f"AI_COST_INPUT_PER_1K_{key}", os.environ.get("AI_COST_INPUT_PER_1K", "0"))
    out_rate = _env_decimal(f"AI_COST_OUTPUT_PER_1K_{key}", os.environ.get("AI_COST_OUTPUT_PER_1K", "0"))
    return {
        "input_per_1k": str(in_rate),
        "output_per_1k": str(out_rate),
    }


def estimate_cost_usd(tokens_in: int, tokens_out: int, *, input_per_1k: str, output_per_1k: str) -> str:
    in_rate = _parse_decimal(input_per_1k, "0")
    out_rate = _parse_decimal(output_per_1k, "0")
    total = (Decimal(max(tokens_in, 0)) / Decimal(1000)) * in_rate
    total += (Decimal(max(tokens_out, 0)) / Decimal(1000)) * out_rate
    rounded = total.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    return format(rounded, "f")
