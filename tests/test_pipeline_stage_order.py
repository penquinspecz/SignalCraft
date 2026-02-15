from __future__ import annotations

from ji_engine.pipeline.runner import resolve_stage_order


def test_resolve_stage_order_is_explicit_and_deterministic() -> None:
    providers = ["alpha", "beta"]
    profiles = ["cs", "tam"]

    first = resolve_stage_order(
        providers=providers,
        profiles=profiles,
        scrape_only=False,
        no_enrich=False,
        ai=True,
    )
    second = resolve_stage_order(
        providers=providers,
        profiles=profiles,
        scrape_only=False,
        no_enrich=False,
        ai=True,
    )

    assert first == second
    assert first == [
        "scrape",
        "classify:alpha",
        "enrich:alpha",
        "ai_augment:alpha",
        "score:alpha:cs",
        "score:alpha:tam",
        "classify:beta",
        "enrich:beta",
        "ai_augment:beta",
        "score:beta:cs",
        "score:beta:tam",
    ]


def test_resolve_stage_order_scrape_only() -> None:
    assert resolve_stage_order(
        providers=["openai"],
        profiles=["cs"],
        scrape_only=True,
        no_enrich=False,
        ai=False,
    ) == ["scrape"]
