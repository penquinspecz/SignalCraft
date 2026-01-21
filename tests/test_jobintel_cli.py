import types

from jobintel import cli


def test_cli_run_forwards_flags(monkeypatch):
    captured = {}

    def fake_run(cmd, env=None, check=False):
        captured["cmd"] = cmd
        captured["env"] = env
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    rc = cli.main(
        [
            "run",
            "--offline",
            "--role",
            "cs",
            "--providers",
            "openai",
            "--no_post",
            "--no_enrich",
        ]
    )

    assert rc == 0
    cmd = captured["cmd"]
    assert "--profiles" in cmd
    assert "cs" in cmd
    assert "--providers" in cmd
    assert "openai" in cmd
    assert "--offline" in cmd
    assert "--no_post" in cmd
    assert "--no_enrich" in cmd


def test_cli_run_accepts_hyphen_aliases(monkeypatch):
    captured = {}

    def fake_run(cmd, env=None, check=False):
        captured["cmd"] = cmd
        return types.SimpleNamespace(returncode=0)

    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    rc = cli.main(
        [
            "run",
            "--offline",
            "--role",
            "cs",
            "--providers",
            "openai",
            "--no-post",
            "--no-enrich",
        ]
    )

    assert rc == 0
    cmd = captured["cmd"]
    assert "--no_post" in cmd
    assert "--no_enrich" in cmd
