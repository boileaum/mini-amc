import copy as copy_mod
import json
import shutil
from pathlib import Path

import pytest

from mini_amc.gen.generate import (
    compile_copy,
    export_positions,
    load_bank,
    plan_copies,
)

BANK = Path("bank.example.yml")
TEMPLATE = Path("template")


def test_plan_copies_reproducible():
    bank = load_bank(BANK)
    a = plan_copies(bank, 3, 42)
    b = plan_copies(bank, 3, 42)
    assert a == b
    assert [c["copy_id"] for c in a] == ["0001", "0002", "0003"]


def test_plan_copies_validity():
    bank = load_bank(BANK)
    copies = plan_copies(bank, 5, 7)
    qids = {q["id"] for q in bank["questions"]}
    for c in copies:
        assert {q["id"] for q in c["questions"]} == qids
        for q in c["questions"]:
            keys = [ch["key"] for ch in q["choices"]]
            assert keys == list("ABC"[: len(keys)])
            corrects = [ch for ch in q["choices"] if ch["correct"]]
            assert len(corrects) == 1
            assert c["answers"][q["id"]] == corrects[0]["key"]


def test_plan_copies_seed_changes_order():
    bank = load_bank(BANK)
    a = plan_copies(bank, 3, 42)
    b = plan_copies(bank, 3, 43)
    assert a != b


def test_plan_copies_does_not_mutate_bank():
    bank = load_bank(BANK)
    snapshot = copy_mod.deepcopy(bank)
    plan_copies(bank, 3, 1)
    assert bank == snapshot


@pytest.mark.skipif(shutil.which("typst") is None, reason="typst binary required")
def test_compile_and_positions(tmp_path):
    bank = load_bank(BANK)
    copies = plan_copies(bank, 2, 42)
    for c in copies:
        cid = c["copy_id"]
        copy_json = {k: v for k, v in c.items() if k != "answers"}
        pdf = tmp_path / f"copy_{cid}.pdf"
        build = compile_copy(TEMPLATE, copy_json, pdf)
        assert pdf.stat().st_size > 0
        pos = export_positions(build, cid)
        n_choices = sum(len(q["choices"]) for q in c["questions"])
        assert pos["copy_id"] == cid
        assert len(pos["questions"]) == len(c["questions"])
        assert len(pos["bubbles"]) == n_choices
        assert pos["page"]["w_pt"] == pytest.approx(595.28, abs=0.01)
        assert pos["page"]["h_pt"] == pytest.approx(841.89, abs=0.01)
        for b in pos["bubbles"]:
            assert 0 < b["x_pt"] < pos["page"]["w_pt"]
            assert 0 < b["y_pt"] < pos["page"]["h_pt"]


@pytest.mark.skipif(shutil.which("typst") is None, reason="typst binary required")
def test_main_end_to_end(tmp_path, monkeypatch):
    from mini_amc.gen.generate import main

    monkeypatch.setattr(
        "sys.argv",
        [
            "mini-amc-gen",
            "--bank",
            str(BANK),
            "--copies",
            "2",
            "--seed",
            "42",
            "--template",
            str(TEMPLATE),
            "--out",
            str(tmp_path),
        ],
    )
    main()
    for cid in ("0001", "0002"):
        assert (tmp_path / f"copy_{cid}.pdf").stat().st_size > 0
        assert json.loads((tmp_path / f"copy_{cid}.json").read_text())["copy_id"] == cid
    positions = json.loads((tmp_path / "positions.json").read_text())
    answers = json.loads((tmp_path / "answers.json").read_text())
    assert set(positions) == {"0001", "0002"}
    assert set(answers) == {"0001", "0002"}
    for cid, ans in answers.items():
        assert set(ans) == {"q1", "q2", "q3", "q4"}
        assert all(k in "ABC" for k in ans.values())
        copy_json = json.loads((tmp_path / f"copy_{cid}.json").read_text())
        for q in copy_json["questions"]:
            assert ans[q["id"]] == next(c["key"] for c in q["choices"] if c["correct"])


def test_load_bank_rejects_invalid_questions(tmp_path):
    base_q = {
        "id": "q1",
        "text": "t?",
        "choices": [{"text": "a", "correct": True}, {"text": "b"}],
    }
    dup = tmp_path / "dup.json"
    dup.write_text(json.dumps({"questions": [base_q, dict(base_q)]}), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate question ids"):
        load_bank(dup)
    noid = tmp_path / "noid.json"
    noid.write_text(
        json.dumps({"questions": [{k: v for k, v in base_q.items() if k != "id"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="needs an id"):
        load_bank(noid)
    notext = tmp_path / "notext.json"
    notext.write_text(
        json.dumps({"questions": [{k: v for k, v in base_q.items() if k != "text"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="'text' and 'choices' required"):
        load_bank(notext)


def test_main_rejects_zero_copies(tmp_path, monkeypatch):
    from mini_amc.gen.generate import main

    monkeypatch.setattr(
        "sys.argv",
        ["mini-amc-gen", "--bank", str(BANK), "--copies", "0", "--out", str(tmp_path)],
    )
    with pytest.raises(SystemExit):
        main()


def test_main_failure_leaves_out_untouched(tmp_path, monkeypatch):
    import mini_amc.gen.generate as gen
    from mini_amc.gen.generate import main

    real_compile = gen.compile_copy
    calls = {"n": 0}

    def flaky(template_dir, copy, out_pdf):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real_compile(template_dir, copy, out_pdf)

    monkeypatch.setattr(gen, "compile_copy", flaky)
    monkeypatch.setattr(
        "sys.argv",
        [
            "mini-amc-gen",
            "--bank",
            str(BANK),
            "--copies",
            "3",
            "--seed",
            "42",
            "--template",
            str(TEMPLATE),
            "--out",
            str(tmp_path / "out"),
        ],
    )
    with pytest.raises(RuntimeError, match="boom"):
        main()
    out = tmp_path / "out"
    assert not (out / "positions.json").exists()
    assert not list(out.glob("copy_*.pdf"))
    assert not (out / ".staging").exists()
