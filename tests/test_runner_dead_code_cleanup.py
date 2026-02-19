from __future__ import annotations

import importlib


def test_removed_dead_runner_helpers_not_present() -> None:
    import ji_engine.pipeline.runner as runner

    runner = importlib.reload(runner)
    assert not hasattr(runner, "_unavailable_summary")
    assert not hasattr(runner, "_redaction_enforce_enabled")
