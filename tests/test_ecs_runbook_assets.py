from __future__ import annotations

from pathlib import Path


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_ecs_runbook_and_templates_exist() -> None:
    runbook = Path("docs/ECS_RUNBOOK.md")
    taskdef = Path("ops/aws/ecs/taskdef.template.json")
    rule = Path("ops/aws/ecs/eventbridge-rule.template.json")
    policy = Path("ops/aws/ecs/iam_policy_minimal.json")
    guide = Path("ops/aws/ecs/README.md")

    for path in (runbook, taskdef, rule, policy, guide):
        assert path.exists(), f"missing {path}"

    runbook_text = _read(runbook)
    assert "Prerequisites" in runbook_text
    assert "One-time Proof Checklist" in runbook_text
    assert "Rollback Steps" in runbook_text
    assert "Rotate Secrets" in runbook_text

    guide_text = _read(guide)
    assert "Substitution guide" in guide_text
    assert "templates only" in guide_text.lower()

    taskdef_text = _read(taskdef)
    assert "<IMAGE_URI>" in taskdef_text
    assert "--snapshot-only" in taskdef_text

    rule_text = _read(rule)
    assert "ScheduleExpression" in rule_text

    policy_text = _read(policy)
    assert "s3:PutObject" in policy_text
    assert "CloudWatchLogs" in policy_text
