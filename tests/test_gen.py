import copy as copy_mod
import json
import shutil
from pathlib import Path

import pytest
import yaml

from mini_amc.gen.generate import (
    compile_copy,
    compile_root,
    export_positions,
    load_bank,
    plan_copies,
)

BANK = Path("src/mini_amc/examples/bank.example.yml")
TEMPLATE = Path("src/mini_amc/template")


def test_plan_copies_reproducible():
    bank = load_bank(BANK)
    a = plan_copies(bank, ["0001", "0002", "0003"], 42)
    b = plan_copies(bank, ["0001", "0002", "0003"], 42)
    assert a == b
    assert [c["copy_id"] for c in a] == ["0001", "0002", "0003"]


def test_plan_copies_validity():
    bank = load_bank(BANK)
    copies = plan_copies(bank, ["0001", "0002", "0003", "0004", "0005"], 7)
    qids = {q["id"] for q in bank["questions"]}
    for c in copies:
        assert {q["id"] for q in c["questions"]} == qids
        for q in c["questions"]:
            if q["type"] == "open":
                assert c["answers"][q["id"]] == "open"
                continue
            keys = [ch["key"] for ch in q["choices"]]
            assert keys == list("ABC"[: len(keys)])
            corrects = [ch for ch in q["choices"] if ch["correct"]]
            assert len(corrects) >= 1
            assert c["answers"][q["id"]] == sorted(ch["key"] for ch in corrects)


def test_plan_copies_seed_changes_order():
    bank = load_bank(BANK)
    a = plan_copies(bank, ["0001", "0002", "0003"], 42)
    b = plan_copies(bank, ["0001", "0002", "0003"], 43)
    assert a != b


def test_plan_copies_does_not_mutate_bank():
    bank = load_bank(BANK)
    snapshot = copy_mod.deepcopy(bank)
    plan_copies(bank, ["0001", "0002", "0003"], 1)
    assert bank == snapshot


@pytest.mark.skipif(shutil.which("typst") is None, reason="typst binary required")
def test_compile_and_positions(tmp_path):
    bank = load_bank(BANK)
    copies = plan_copies(bank, ["0001", "0002"], 42)
    for c in copies:
        cid = c["copy_id"]
        copy_json = {k: v for k, v in c.items() if k != "answers"}
        pdf = tmp_path / f"copy_{cid}.pdf"
        build = compile_copy(TEMPLATE, BANK, copy_json, pdf)
        assert pdf.stat().st_size > 0
        pos = export_positions(build, cid, compile_root(BANK, build))
        n_choices = sum(len(q.get("choices", [])) for q in c["questions"])
        n_gradeboxes = sum(
            q.get("max_points", 0) + 1
            for q in c["questions"]
            if q.get("type") == "open"
        )
        assert pos["copy_id"] == cid
        assert len(pos["questions"]) == len(c["questions"])
        assert len(pos["bubbles"]) == n_choices
        assert len(pos["gradeboxes"]) == n_gradeboxes
        assert pos["page"]["w_pt"] == pytest.approx(595.28, abs=0.01)
        assert pos["page"]["h_pt"] == pytest.approx(841.89, abs=0.01)
        for b in pos["bubbles"] + pos["gradeboxes"]:
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
    config = json.loads((tmp_path / "config.json").read_text(encoding="utf-8"))
    assert config == {"bareme": "v1"}
    for cid, ans in answers.items():
        assert set(ans) == {"q1", "q2", "q3", "q4", "q5"}
        assert ans["q5"] == "open"
        assert all(all(x in "ABC" for x in v) for k, v in ans.items() if k != "q5")
        copy_json = json.loads((tmp_path / f"copy_{cid}.json").read_text())
        for q in copy_json["questions"]:
            if q["type"] == "open":
                continue
            assert ans[q["id"]] == sorted(
                c["key"] for c in q["choices"] if c["correct"]
            )


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
    with pytest.raises(ValueError, match="'text' required"):
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

    def flaky(template_dir, bank_path, copy, out_pdf):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real_compile(template_dir, bank_path, copy, out_pdf)

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


def test_load_students_simple_format(tmp_path):
    from mini_amc.gen.generate import load_students

    p = tmp_path / "students.csv"
    p.write_text("copy_id,name\n0001,Alice\n0002,Bob\n", encoding="utf-8")
    assert load_students(p) == {"0001": "Alice", "0002": "Bob"}


def test_load_students_moodle_format(tmp_path):
    from mini_amc.gen.generate import load_students

    p = tmp_path / "moodle.csv"
    header = (
        'Prénom;Nom;"Adresse de courriel";"Numéro étudiant";'
        '"Dernier téléchargement depuis ce cours"\n'
    )
    p.write_text(
        header
        + "Alice;Martin;alice.martin@example.org;21800001;12/11/2026 10:00\n"
        + "Bob;Durand;bob.durand@example.org;21800002;\n",
        encoding="utf-8",
    )
    s = load_students(p, id_column="Numéro étudiant", name_columns=["Prénom", "Nom"])
    assert s == {"21800001": "Alice Martin", "21800002": "Bob Durand"}


def test_load_students_explicit_delimiter_and_bom(tmp_path):
    from mini_amc.gen.generate import load_students

    p = tmp_path / "bom.csv"
    p.write_bytes("﻿id;label\nA1;Alice\n".encode())
    assert load_students(p, id_column="id", name_columns=["label"], delimiter=";") == {
        "A1": "Alice"
    }


def test_load_students_errors(tmp_path):
    from mini_amc.gen.generate import load_students

    bad = tmp_path / "bad.csv"
    bad.write_text("id,name\n0001,A\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing column"):
        load_students(bad)
    dup = tmp_path / "dup.csv"
    dup.write_text("copy_id,name\n0001,A\n0001,B\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate copy id"):
        load_students(dup)
    invalid = tmp_path / "inv.csv"
    invalid.write_text("copy_id,name\n00 1,A\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid copy id"):
        load_students(invalid)
    empty_name = tmp_path / "empty.csv"
    empty_name.write_text("copy_id,name\n0001,\n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty name"):
        load_students(empty_name)
    empty_file = tmp_path / "none.csv"
    empty_file.write_text("copy_id,name\n", encoding="utf-8")
    with pytest.raises(ValueError, match="no student rows"):
        load_students(empty_file)


def test_plan_copies_rejects_bad_ids():
    bank = load_bank(BANK)
    with pytest.raises(ValueError, match="no copy ids"):
        plan_copies(bank, [], 42)
    with pytest.raises(ValueError, match="duplicate copy ids"):
        plan_copies(bank, ["0001", "0001"], 42)


def test_main_with_students_moodle(tmp_path, monkeypatch):
    from mini_amc.gen.generate import main

    students = tmp_path / "students.csv"
    students.write_text(
        "Numéro étudiant;Nom;Prénom\n21800001;Martin;Alice\n21800002;Durand;Bob\n",
        encoding="utf-8",
    )
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
            "--students",
            str(students),
            "--students-id-column",
            "Numéro étudiant",
            "--students-name-columns",
            "Prénom,Nom",
            "--out",
            str(tmp_path / "out"),
        ],
    )
    main()
    out = tmp_path / "out"
    assert json.loads((out / "students.json").read_text()) == {
        "21800001": "Alice Martin",
        "21800002": "Bob Durand",
    }
    assert (out / "copy_21800001.pdf").exists()
    assert (
        json.loads((out / "copy_21800001.json").read_text())["student"]
        == "Alice Martin"
    )
    assert set(json.loads((out / "positions.json").read_text())) == {
        "21800001",
        "21800002",
    }


def test_main_students_count_mismatch(tmp_path, monkeypatch):
    from mini_amc.gen.generate import main

    students = tmp_path / "students.csv"
    students.write_text("copy_id,name\n0001,Alice\n", encoding="utf-8")
    monkeypatch.setattr(
        "sys.argv",
        [
            "mini-amc-gen",
            "--bank",
            str(BANK),
            "--copies",
            "3",
            "--students",
            str(students),
            "--out",
            str(tmp_path / "out"),
        ],
    )
    with pytest.raises(SystemExit):
        main()


def test_load_bank_open_question(tmp_path):
    good = tmp_path / "good.json"
    good.write_text(
        json.dumps(
            {
                "questions": [
                    {
                        "id": "q1",
                        "text": "t",
                        "type": "open",
                        "max_points": 3,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    bank = load_bank(good)
    assert bank["questions"][0]["type"] == "open"
    for bad_q, match in [
        ({"id": "q1", "text": "t", "type": "open"}, "max_points"),
        ({"id": "q1", "text": "t", "type": "open", "max_points": 0}, "max_points"),
        (
            {"id": "q1", "text": "t", "type": "open", "max_points": 21},
            "max_points <= 20",
        ),
        (
            {
                "id": "q1",
                "text": "t",
                "type": "open",
                "max_points": 2,
                "choices": [{"text": "a", "correct": True}],
            },
            "must not have choices",
        ),
        ({"id": "q1", "text": "t"}, "'choices' required"),
    ]:
        p = tmp_path / "bad.json"
        p.write_text(json.dumps({"questions": [bad_q]}), encoding="utf-8")
        with pytest.raises(ValueError, match=match):
            load_bank(p)


def test_plan_copies_open_question():
    bank = load_bank(BANK)
    copies = plan_copies(bank, ["0001"], 42)
    q5 = next(q for q in copies[0]["questions"] if q["id"] == "q5")
    assert q5["type"] == "open" and q5["max_points"] == 2 and "choices" not in q5
    assert copies[0]["answers"]["q5"] == "open"
    q1 = next(q for q in copies[0]["questions"] if q["id"] == "q1")
    assert q1["type"] == "mcq" and "choices" in q1


def test_load_bank_multi_answer(tmp_path):
    multi = {
        "questions": [
            {
                "id": "q1",
                "text": "t",
                "choices": [
                    {"text": "a", "correct": True},
                    {"text": "b"},
                    {"text": "c", "correct": True},
                ],
            }
        ]
    }
    p = tmp_path / "multi.yml"
    p.write_text(yaml.dump(multi), encoding="utf-8")
    bank = load_bank(p)
    copies = plan_copies(bank, ["0001"], 1)
    q = copies[0]["questions"][0]
    assert q["multi"] is True
    assert copies[0]["answers"]["q1"] == sorted(
        c["key"] for c in q["choices"] if c["correct"]
    )
    assert len(copies[0]["answers"]["q1"]) == 2

    zero = {
        "questions": [
            {"id": "q1", "text": "t", "choices": [{"text": "a"}, {"text": "b"}]}
        ]
    }
    p2 = tmp_path / "zero.yml"
    p2.write_text(yaml.dump(zero), encoding="utf-8")
    with pytest.raises(ValueError, match="at least 1 correct"):
        load_bank(p2)
