import json

import pytest

from presentation_support import REPO, load_script

rec = load_script("record_demo")
DEMO = (REPO / "docs" / "demo.md").read_text(encoding="utf-8")


def make_cast(*events, header=None):
    head = header or {"version": 2, "width": 100, "height": 30}
    return "\n".join([json.dumps(head)] + [json.dumps(e) for e in events]) + "\n"


def test_every_step_command_is_documented_in_the_demo():
    assert rec.step_commands()
    for command in rec.step_commands():
        assert rec.documented(command, DEMO), command


def test_an_undocumented_command_is_detected():
    assert not rec.documented("PYTHONPATH=src .venv/bin/python -m codegen_eval.experiment_cli run", DEMO)


def test_steps_run_no_paid_or_credentialed_command():
    for command in rec.step_commands():
        assert "experiment_cli" not in command and "openrouter" not in command.lower().replace("openrouter'", "")
        assert "OPENROUTER_API_KEY" not in command and "--i-accept-cost" not in command


def test_committed_cast_is_valid_and_clean():
    text = (REPO / rec.CAST).read_text(encoding="utf-8")
    assert rec.check_cast(text, DEMO, REPO) == []
    header, events = rec.parse_cast(text)
    assert header["version"] == 2 and all(e[1] == "o" for e in events)
    transcript = "".join(e[2] for e in events)
    assert "regrades" in transcript.lower() or "REGRADES" in transcript
    assert "not a fresh agent trial" in transcript


def test_cast_validation_rejects_bad_input(tmp_path):
    ok = make_cast([0.1, "o", "hello\r\n"], [0.2, "o", "$ " + rec.step_commands()[0] + "\r\n"])
    assert rec.check_cast(ok, DEMO) == []
    assert rec.check_cast("not json\n")
    assert rec.check_cast(make_cast([0.1, "o", "x"], header={"version": 1}))
    assert any("backwards" in p for p in rec.check_cast(make_cast([0.5, "o", "a"], [0.1, "o", "b"])))
    assert any("expected" in p for p in rec.check_cast(make_cast([0.1, "i", "a"])))
    assert any("/Users/" in p for p in rec.check_cast(make_cast([0.1, "o", "see /Users/x/y\r\n"])))
    assert any("secret" in p for p in rec.check_cast(make_cast([0.1, "o", "Bearer abcdefghijklmnopqrst\r\n"])))
    assert any("not in" in p for p in rec.check_cast(make_cast([0.1, "o", "$ rm -rf /\r\n"]), DEMO))


def test_scrubber_replaces_root_home_and_temp(tmp_path):
    scrub = rec.scrubber(tmp_path / "repo")
    home = str(rec.Path.home())
    assert scrub(f"{tmp_path}/repo/src and {home}/x and /tmp/y") == "./src and ~/x and <tmp>/y" \
        or "<tmp>" in scrub(f"{tmp_path}/repo/src")
    assert str(tmp_path / "repo") not in scrub(f"error in {tmp_path}/repo/src/a.py")


def test_record_refuses_a_non_empty_bundles_directory(tmp_path):
    (tmp_path / "run_bundles" / "20261101T000000Z-aaaaaa").mkdir(parents=True)
    with pytest.raises(rec.RecordError, match="not empty"):
        rec.record(tmp_path)


def fake_runner(outputs, calls):
    def run(command, root):
        calls.append(command)
        for needle, result in outputs.items():
            if needle in command:
                return result
        return 0, "ok\n"
    return run


def test_record_types_commands_with_the_run_id_and_is_deterministic(tmp_path, monkeypatch):
    run_id = "20261113T120000Z-abc123"
    outputs = {"run_recording": (0, f"bundle: run_bundles/{run_id}\nrecorded 2 of 2\n"),
               "grep -c": (1, "0\n")}
    calls = []
    monkeypatch.setattr(rec, "run_step", fake_runner(outputs, calls))
    first = rec.record(tmp_path).render()
    again = rec.record(tmp_path).render()
    assert first == again
    assert any(f"trace_inspect verify {run_id}" in c for c in calls)
    text = "".join(e[2] for e in rec.parse_cast(first)[1]).replace("\r\n", "\n")
    assert f"$ PYTHONPATH=src .venv/bin/python -m codegen_eval.replay {run_id}" in text
    assert rec.check_cast(first, DEMO) == []


def test_record_caps_long_output_with_an_explicit_marker(tmp_path, monkeypatch):
    long = "\n".join(f"line {i}" for i in range(100)) + "\n"
    outputs = {"run_recording": (0, "bundle: run_bundles/20261113T120000Z-abc123\n"), "show": (0, long)}
    monkeypatch.setattr(rec, "run_step", fake_runner(outputs, []))
    text = "".join(e[2] for e in rec.parse_cast(rec.record(tmp_path).render())[1])
    assert "[... 40 more lines not recorded]" in text and "line 59" in text and "line 60" not in text


def test_record_aborts_on_a_secret_or_a_failed_step(tmp_path, monkeypatch):
    base = {"run_recording": (0, "bundle: run_bundles/20261113T120000Z-abc123\n")}
    monkeypatch.setattr(rec, "run_step", fake_runner({**base, "list": (0, "sk-abcdefghijklmnopqrstuvwx\n")}, []))
    with pytest.raises(rec.RecordError, match="secret"):
        rec.record(tmp_path)
    monkeypatch.setattr(rec, "run_step", fake_runner({**base, "replay": (2, "boom\n")}, []))
    with pytest.raises(rec.RecordError, match="exit code 2"):
        rec.record(tmp_path)
    monkeypatch.setattr(rec, "run_step", fake_runner({"run_recording": (0, "no id here\n")}, []))
    with pytest.raises(rec.RecordError, match="run id"):
        rec.record(tmp_path)


def test_commands_run_with_a_clean_environment(monkeypatch, tmp_path):
    seen = {}

    def fake(argv, **kwargs):
        seen["argv"] = argv
        return type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})()
    monkeypatch.setattr(rec.subprocess, "run", fake)
    rec.run_step("true", tmp_path)
    assert seen["argv"][:2] == ["env", "-i"] and not any("KEY" in a for a in seen["argv"])
    assert seen["argv"][3] == f"PATH={rec.CLEAN_PATH}"


def test_player_embeds_the_cast_and_a_static_transcript():
    template = (REPO / rec.TEMPLATE).read_text(encoding="utf-8")
    cast = make_cast([0.1, "o", "a <b> &\r\n"], [0.2, "o", "</script>\r\n"])
    page = rec.build_player(cast, template)
    assert "a &lt;b&gt; &amp;" in page and "</script>\\n" not in page
    assert page.count("</script>") == 2 and "<!--CAST-->" not in page and "<!--TRANSCRIPT-->" not in page
    assert '<script type="application/json" id="cast">' in page


def test_player_template_needs_no_network_or_library():
    template = (REPO / rec.TEMPLATE).read_text(encoding="utf-8")
    assert "http://" not in template and "https://" not in template
    assert " src=" not in template and "@import" not in template and "<link" not in template
    assert "<noscript>" in template and "full transcript" in template.lower()
    assert 'lang="en"' in template and "prefers-color-scheme" in template and "@media print" in template


def test_cli_check_and_player_build(tmp_path, capsys):
    root = tmp_path / "repo"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "demo.md").write_text(DEMO, encoding="utf-8")
    (root / "presentation" / "recording").mkdir(parents=True)
    (root / rec.TEMPLATE).write_text((REPO / rec.TEMPLATE).read_text(encoding="utf-8"), encoding="utf-8")
    (root / rec.CAST).write_text(make_cast([0.1, "o", "hi\r\n"]), encoding="utf-8")
    assert rec.main(["--root", str(root), "check"]) == 0
    assert rec.main(["--root", str(root), "build-player"]) == 0
    assert (root / rec.PLAYER_OUT).is_file()
    (root / rec.CAST).write_text(make_cast([0.1, "o", "see /Users/x\r\n"]), encoding="utf-8")
    assert rec.main(["--root", str(root), "check"]) == 1
