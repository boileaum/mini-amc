import json
from pathlib import Path

from mini_amc.gen.generate import compile_root
from mini_amc.preview import build_preview, main, render_pngs, write_copy_json

SUBJECT = Path("src/mini_amc/examples/subject.typ")
TEMPLATE = Path("src/mini_amc/template")


def test_build_preview_creates_pdf(tmp_path):
    out = tmp_path / "preview"
    pdf = build_preview(SUBJECT, out, 42, TEMPLATE)
    assert pdf.exists() and pdf.stat().st_size > 1000
    build = out / "build" / "0001"
    assert (build / "main.typ").exists()
    assert (build / "copy.json").exists()
    assert list(build.glob("qr-*.png"))
    copy = json.loads((build / "copy.json").read_text(encoding="utf-8"))
    assert copy["copy_id"] == "0001"


def test_render_pngs(tmp_path):
    out = tmp_path / "preview"
    build_preview(SUBJECT, out, 42, TEMPLATE)
    build = out / "build" / "0001"
    pngs = render_pngs(build, out, compile_root(SUBJECT, build))
    assert pngs and pngs[0].stat().st_size > 10000


def test_write_copy_json_regenerates(tmp_path):
    out = tmp_path / "preview"
    build_preview(SUBJECT, out, 42, TEMPLATE)
    build = out / "build" / "0001"
    before = (build / "copy.json").read_text(encoding="utf-8")
    write_copy_json(build, SUBJECT, 7)
    after = (build / "copy.json").read_text(encoding="utf-8")
    assert before != after  # different seed -> different shuffle


def test_preview_main(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(
        "sys.argv",
        [
            "mini-amc-preview",
            "--bank",
            str(SUBJECT),
            "--out",
            str(tmp_path / "pv"),
            "--png",
        ],
    )
    main()
    out = capsys.readouterr().out
    assert "preview PDF" in out and "preview PNGs" in out
    assert (tmp_path / "pv" / "copy_0001.pdf").exists()
    assert list((tmp_path / "pv").glob("page-*.png"))
