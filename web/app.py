import json
from pathlib import Path

from fastapi import FastAPI

app = FastAPI(title="mini-amc review")

DATA = Path(__file__).resolve().parent.parent / "data"


def load_json(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


@app.get("/copies")
def list_copies():
    raise NotImplementedError("D7 : liste des copies + statut (ok / a_verifier / non lu)")


@app.get("/copy/{copy_id}")
def copy_detail(copy_id: str):
    raise NotImplementedError("D7 : scan annoté + cases détectées + corrections en cours")


@app.post("/copy/{copy_id}/correction")
def post_correction(copy_id: str, payload: dict):
    raise NotImplementedError("D7 : enregistre la correction manuelle, recalcule la note")
