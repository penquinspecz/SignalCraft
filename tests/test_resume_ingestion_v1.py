from __future__ import annotations

import importlib
import json
from pathlib import Path

from scripts.schema_validate import resolve_named_schema_path, validate_payload


def _reload_modules():
    import ji_engine.candidates.registry as candidate_registry
    import ji_engine.config as config
    import scripts.candidates as candidates_cli

    importlib.reload(config)
    importlib.reload(candidate_registry)
    candidates_cli = importlib.reload(candidates_cli)
    return config, candidate_registry, candidates_cli


def _schema_errors(payload: dict) -> list[str]:
    schema = json.loads(resolve_named_schema_path("resume", 1).read_text(encoding="utf-8"))
    return validate_payload(payload, schema)


def test_resume_ingestion_structured_only_no_raw_leak(tmp_path: Path, monkeypatch, capsys) -> None:
    marker = "M30_RESUME_SECRET_DO_NOT_LEAK"
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    config, _candidate_registry, candidates_cli = _reload_modules()

    assert candidates_cli.main(["bootstrap", "alice"]) == 0
    capsys.readouterr()
    resume_path = tmp_path / "resume.txt"
    resume_path.write_text(
        f"{marker}\nSenior software engineer with 10 years experience in Python and Kubernetes.\n",
        encoding="utf-8",
    )

    assert candidates_cli.main(["ingest-resume", "alice", "--resume-file", str(resume_path), "--json"]) == 0
    out = capsys.readouterr()
    payload = json.loads(out.out)

    serialized = json.dumps(payload, sort_keys=True)
    assert marker not in serialized
    assert marker not in out.err
    assert payload["resume_structured"]["source_format"] == "text"
    assert payload["resume_structured"]["resume_hash"]
    assert _schema_errors(payload["resume_structured"]) == []

    artifact_rel = payload["resume_structured_artifact"]["artifact_path"]
    artifact_abs = config.STATE_DIR / artifact_rel
    artifact_text = artifact_abs.read_text(encoding="utf-8")
    assert marker not in artifact_text
    assert "resume_text" not in artifact_text
    assert "text" not in json.loads(artifact_text)

    profile_text = config.candidate_profile_path("alice").read_text(encoding="utf-8")
    assert marker not in profile_text
    profile_payload = json.loads(profile_text)
    assert profile_payload["text_inputs"]["resume_text"] is None


def test_resume_hash_stability_and_change_detection(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    _config, _candidate_registry, candidates_cli = _reload_modules()

    assert candidates_cli.main(["bootstrap", "alice"]) == 0
    capsys.readouterr()
    resume_a = tmp_path / "resume_a.txt"
    resume_b = tmp_path / "resume_b.txt"
    resume_c = tmp_path / "resume_c.txt"
    resume_a.write_text("Senior engineer with 8 years in Python and AWS.", encoding="utf-8")
    resume_b.write_text("  Senior engineer   with 8 years in Python and AWS.  ", encoding="utf-8")
    resume_c.write_text("Principal engineer with 12 years in Go and Kubernetes.", encoding="utf-8")

    assert candidates_cli.main(["ingest-resume", "alice", "--resume-file", str(resume_a), "--json"]) == 0
    payload_a = json.loads(capsys.readouterr().out)
    hash_a = payload_a["resume_structured"]["resume_hash"]
    profile_hash_a = payload_a["profile_hash"]

    assert candidates_cli.main(["ingest-resume", "alice", "--resume-file", str(resume_b), "--json"]) == 0
    payload_b = json.loads(capsys.readouterr().out)
    assert payload_b["resume_structured"]["resume_hash"] == hash_a
    assert payload_b["profile_hash"] == profile_hash_a

    assert candidates_cli.main(["ingest-resume", "alice", "--resume-file", str(resume_c), "--json"]) == 0
    payload_c = json.loads(capsys.readouterr().out)
    assert payload_c["resume_structured"]["resume_hash"] != hash_a
    assert payload_c["profile_hash"] != profile_hash_a


def test_resume_ingestion_candidate_isolation(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    config, candidate_registry, candidates_cli = _reload_modules()

    assert candidates_cli.main(["bootstrap", "alice"]) == 0
    capsys.readouterr()
    assert candidates_cli.main(["bootstrap", "bob"]) == 0
    capsys.readouterr()
    alice_resume = tmp_path / "alice_resume.txt"
    bob_resume = tmp_path / "bob_resume.txt"
    alice_resume.write_text("Staff engineer, Python, remote.", encoding="utf-8")
    bob_resume.write_text("Customer success manager, Salesforce, New York.", encoding="utf-8")

    assert candidates_cli.main(["ingest-resume", "alice", "--resume-file", str(alice_resume), "--json"]) == 0
    alice_payload = json.loads(capsys.readouterr().out)
    assert candidates_cli.main(["ingest-resume", "bob", "--resume-file", str(bob_resume), "--json"]) == 0
    bob_payload = json.loads(capsys.readouterr().out)

    assert (
        "/candidates/alice/"
        in (config.STATE_DIR / alice_payload["resume_structured_artifact"]["artifact_path"]).as_posix()
    )
    assert (
        "/candidates/bob/" in (config.STATE_DIR / bob_payload["resume_structured_artifact"]["artifact_path"]).as_posix()
    )
    assert candidate_registry.profile_hash("alice") != candidate_registry.profile_hash("bob")


def test_resume_ingestion_pdf_supported(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setenv("JOBINTEL_STATE_DIR", str(tmp_path / "state"))
    _config, _candidate_registry, candidates_cli = _reload_modules()

    assert candidates_cli.main(["bootstrap", "alice"]) == 0
    capsys.readouterr()
    pdf_path = tmp_path / "resume.pdf"
    pdf_path.write_bytes(
        b"%PDF-1.4\n1 0 obj\n<< /Type /Page >>\nstream\n(Bachelor degree, 7 years Python) Tj\nendstream\nendobj\n"
    )

    assert candidates_cli.main(["ingest-resume", "alice", "--resume-file", str(pdf_path), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["resume_structured"]["source_format"] == "pdf"
    assert payload["resume_structured"]["resume_hash"]
