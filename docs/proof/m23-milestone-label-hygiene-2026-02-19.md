# M23 Milestone Label Hygiene (2026-02-19)

## Goal
Eliminate accidental use of placeholder milestone labels and enforce a numeric milestone label pattern.

## GitHub Label Taxonomy Actions

Commands run:
```bash
gh label list --limit 200 | rg -n "milestone:"
gh pr list --state all --label "milestone:Mxx" --limit 200 --json number,url,state,title
gh issue list --state all --label "milestone:Mxx" --limit 200 --json number,url,state,title
gh label delete "milestone:Mxx" --yes
gh label list --limit 200 | rg -n "milestone:"
```

Observed outputs:
- Before: `milestone:Mxx` and `milestone:M23` existed.
- Usage checks: `[]` for PRs and `[]` for issues on `milestone:Mxx`.
- After deletion: only `milestone:M23` remains.

Current milestone labels snippet:
```text
milestone:M23    Milestone 23 tracking    #FBCA04
```

## Open PR Label Audit

Commands run:
```bash
gh pr view 184 --json number,url,labels
gh pr view 185 --json number,url,labels
```

Result:
- PR #184 has `from-codex` + `milestone:M23`
- PR #185 has `from-codex` + `milestone:M23`

## Policy Hardening Changes

Files changed:
- `scripts/check_pr_label_policy.py`
- `tests/test_check_pr_label_policy.py`

Policy additions:
- Milestone labels must match regex: `^milestone:M\d+$`
- Placeholder/non-numeric milestone labels (for example `milestone:Mxx`) are flagged as policy issues.
- Existing provenance branch-prefix checks remain unchanged.
- CI fast job already executes this script (`PR label policy (warn-only)` step).

## Global Invalid-Milestone Audit

Commands run:
```bash
gh pr list --state all --limit 200 --json number,url,labels | python3 -c 'import json,re,sys; data=json.load(sys.stdin); bad=[]; pat=re.compile(r"^milestone:M\d+$");
for pr in data:
  for l in pr.get("labels",[]):
    n=l.get("name","")
    if n.startswith("milestone:") and not pat.fullmatch(n):
      bad.append((pr["number"],n,pr["url"]))
print("INVALID_PR_MILESTONE_LABELS=0" if not bad else "INVALID_PR_MILESTONE_LABELS="+str(len(bad))); [print(f"PR#{n} {lab} {u}") for n,lab,u in bad]'

gh issue list --state all --limit 200 --json number,url,labels | python3 -c 'import json,re,sys; data=json.load(sys.stdin); bad=[]; pat=re.compile(r"^milestone:M\d+$");
for it in data:
  for l in it.get("labels",[]):
    n=l.get("name","")
    if n.startswith("milestone:") and not pat.fullmatch(n):
      bad.append((it["number"],n,it["url"]))
print("INVALID_ISSUE_MILESTONE_LABELS=0" if not bad else "INVALID_ISSUE_MILESTONE_LABELS="+str(len(bad))); [print(f"Issue#{n} {lab} {u}") for n,lab,u in bad]'
```

Outputs:
```text
INVALID_PR_MILESTONE_LABELS=0
INVALID_ISSUE_MILESTONE_LABELS=0
```

## Validation

Commands:
```bash
PY=/Users/chris.menendez/Projects/signalcraft/.venv/bin/python make lint
PY=/Users/chris.menendez/Projects/signalcraft/.venv/bin/python make ci-fast
PY=/Users/chris.menendez/Projects/signalcraft/.venv/bin/python make gate
```

Results:
- `make lint`: pass
- `make ci-fast`: pass (`696 passed, 16 skipped`)
- `make gate`: pass (`696 passed, 16 skipped` + snapshot immutability pass + replay smoke pass)
