# Repo Truth Sync (2026-03-01)

## Main Sync Status
- origin/main SHA: bc4d45dba9db2fc7733a8bd1e70b3ad54adaee0f
- local main SHA (after sync): bc4d45dba9db2fc7733a8bd1e70b3ad54adaee0f
- main ahead/behind vs origin/main: 0/0
- local main reset required: no (already aligned)
- working tree clean before report write: yes

## Tag Sync
- fetch tags executed: yes
- local unique tags: 14
- origin unique tags: 14
- tag sets identical: yes

## Local Branch Actions
- Deleted local branches:
  - codex/job-timeline-v1
  - codex/digest-change-insights
  - codex/ui-v0-changes-view
  - codex/role-drift-analytics-v1
- Left local branches (not deleted in this sync):
  - chore/add-rollup-receipt-20260222T211218Z (upstream: origin/chore/add-rollup-receipt-20260222T211218Z, state: tracks-missing, unique commits vs origin/main: 2)
  - chore/cleanup-receipt-20260222T211723Z (upstream: origin/chore/cleanup-receipt-20260222T211723Z, state: tracks-missing, unique commits vs origin/main: 2)
  - chore/docs-v020-release-policy-20260222T203548Z (upstream: origin/chore/docs-v020-release-policy-20260222T203548Z, state: tracks-missing, unique commits vs origin/main: 3)
  - chore/docs-versioning-release-template-20260222T202545Z (upstream: origin/chore/docs-versioning-release-template-20260222T202545Z, state: tracks-missing, unique commits vs origin/main: 5)
  - chore/dr-cost-discipline-validate-skip-20260222T170610Z (upstream: origin/main, state: tracks-existing, unique commits vs origin/main: 0)
  - chore/dr-land-local-script-fixes-20260222T201310Z (upstream: origin/chore/dr-land-local-script-fixes-20260222T201310Z, state: tracks-missing, unique commits vs origin/main: 1)
  - chore/governance-branch-auto-delete-20260222T210603Z (upstream: origin/chore/governance-branch-auto-delete-20260222T210603Z, state: tracks-missing, unique commits vs origin/main: 1)
  - chore/governance-provenance-always-20260222T211953Z (upstream: origin/chore/governance-provenance-always-20260222T211953Z, state: tracks-missing, unique commits vs origin/main: 2)
  - chore/governance-relax-area-multi-20260222T205618Z (upstream: origin/chore/governance-relax-area-multi-20260222T205618Z, state: tracks-missing, unique commits vs origin/main: 4)
  - chore/governance-relax-area-multi-v2 (upstream: origin/chore/governance-relax-area-multi-v2, state: tracks-missing, unique commits vs origin/main: 1)
  - chore/m19a-digest-pinning-release-proof-20260222 (upstream: origin/chore/m19a-digest-pinning-release-proof-20260222, state: tracks-missing, unique commits vs origin/main: 6)
  - chore/m19b-orchestrator-receipts-20260222T214638Z (upstream: origin/chore/m19b-orchestrator-receipts-20260222T214638Z, state: tracks-missing, unique commits vs origin/main: 2)
  - chore/pr-governance-enforcement (upstream: origin/chore/pr-governance-enforcement, state: tracks-missing, unique commits vs origin/main: 3)
  - chore/pr-governance-milestoneB-20260222T204028Z (upstream: origin/chore/pr-governance-milestoneB-20260222T204028Z, state: tracks-missing, unique commits vs origin/main: 1)
  - chore/release-notes-style-milestone-product-20260222 (upstream: origin/chore/release-notes-style-milestone-product-20260222, state: tracks-missing, unique commits vs origin/main: 2)
  - chore/release-render-release-notes-20260222T202643Z (upstream: origin/chore/release-render-release-notes-20260222T202643Z, state: tracks-missing, unique commits vs origin/main: 4)
  - codex/docs-roadmap-phase2-hardening (upstream: origin/codex/docs-roadmap-phase2-hardening, state: tracks-existing, unique commits vs origin/main: 1)
  - codex/m25-provider-availability-always-on (upstream: origin/codex/m25-provider-availability-always-on, sta- \==> pytest
.venv/bin/python -m pytest -q
........................................................s............... [  9%]
.............................ssss....................................... [ 18%]
........................................................................ [ 28%]
........................................................................ [ 37%]
...........................ss........................................... [ 46%]
.......................................................................s [ 56%]
s........................sss..........s................................. [ 65%]
........................................................................ [ 74%]
........................................................................ [ 84%]
........................................................................ [ 93%]
.......................................s....s....                        [100%]
754 passed, 17 skipped in 22.55s
==> snapshot immutability
PYTHONPATH=src .venv/bin/python scripts/verify_snapshots_immutable.py
data/anthropic_snapshots/index.html: sha256=3c2f5fcfa255fe7115675c6cc0fb4d3f3db5b8442aac2ad63fb96cf93f18c250 bytes=818
data/cohere_snapshots/index.html: sha256=3539f09a4c0e695b0950fb8187ff6e6db2cb0463d6fd28b2a7052c6bcc19b35d bytes=1590
data/huggingface_snapshots/index.html: sha256=e707d5492b081c43e87dc660fd4134983c3b2caca1a43890282da7b7bc17c238 bytes=1940
data/mistral_snapshots/index.html: sha256=8bbedb1626e75074b72cd529345a1cd2764688b63a53a220208cb0f0a5c7525e bytes=1590
data/openai_snapshots/index.html: sha256=db859f209b7e1eeeaa385d9dab87d02f9ee72217e5afa57edebc21932b586ffc bytes=504376
data/perplexity_snapshots/index.html: sha256=d551252792f03d7aa864fc08d7c9455a4e0811a1388b09911014c8781b66a3ab bytes=1528
data/replit_snapshots/index.html: sha256=f5026bb25896c19492a2cf9db0389bed4f03af93e0cc7cccc4b00b89b25f9fcd bytes=914
data/scaleai_snapshots/index.html: sha256=a3cef755cd17abd623be630eaf863b0a2b1c83ee3bf391b80a33e619f152f88a bytes=924
==> replay smoke
CAREERS_MODE=SNAPSHOT PYTHONPATH=src .venv/bin/python scripts/replay_smoke_fixture.py
PASS: all artifacts match run report hashes
REPLAY REPORT
input:enriched_jobs_json: expected=a5e52c08fe2123372d176a0b4acd2f75d4a638a934a4cbb1eb86ef13ea41d5ea actual=a5e52c08fe2123372d176a0b4acd2f75d4a638a934a4cbb1eb86ef13ea41d5ea match=True
scoring_input:cs: expected=a5e52c08fe2123372d176a0b4acd2f75d4a638a934a4cbb1eb86ef13ea41d5ea actual=a5e52c08fe2123372d176a0b4acd2f75d4a638a934a4cbb1eb86ef13ea41d5ea match=True
output:ranked_csv: expected=94728d55148effda31db88be62d29d947375b55cba92ad61b1cef4cfe2846ecf actual=94728d55148effda31db88be62d29d947375b55cba92ad61b1cef4cfe2846ecf match=True
output:ranked_families_json: expected=d707459c036035d9a716924d2aa50f7b1c7ff66987d243aaef7629c8a679ce3f actual=d707459c036035d9a716924d2aa50f7b1c7ff66987d243aaef7629c8a679ce3f match=True
output:ranked_json: expected=f6100fed8446ca9609c8a1fe78384b6e87037b2e0f47838db9a198b91f00f8c0 actual=f6100fed8446ca9609c8a1fe78384b6e87037b2e0f47838db9a198b91f00f8c0 match=True
output:shortlist_md: expected=4a1a468e12aaf654de0928db760555a31c8ce721d1c23ce126e6d42f2a23fc38 actual=4a1a468e12aaf654de0928db760555a31c8ce721d1c23ce126e6d42f2a23fc38 match=True
SUMMARY: checked=6 matched=6 mismatched=0 missing=0: PASS
