from pathlib import Path

import pytest

pytest.importorskip("httpx")
from starlette.testclient import TestClient  # noqa: E402

from crossword.server import create_app  # noqa: E402


@pytest.fixture()
def client(tmp_path: Path):
    words = tmp_path / "words.tsv"
    words.write_text("\n".join(f"{w}\t50" for w in ["NÄT", "ORO", "SAK", "NOS", "ÄRA", "TOK", "KATT"]), encoding="utf-8")
    app = create_app(wordlist_path=words, auto_fetch=False, env={})
    return TestClient(app)


def test_status(client):
    st = client.get("/api/status").json()
    assert st["wordlist"]["count"] == 7
    assert st["ai"]["enabled"] is False


def test_words(client):
    data = client.get("/api/words", params={"pattern": "k?tt"}).json()
    assert data["total"] == 1 and data["words"][0]["word"] == "KATT"


def test_fill_and_check(client):
    res = client.post("/api/fill", json={"grid": [[""] * 3 for _ in range(3)], "seed": 1}).json()
    assert res["ok"], res["message"]
    check = client.post("/api/check", json={"grid": res["grid"]}).json()
    assert all(s["known"] for s in check["slots"])


def test_clues_without_ai(client):
    r = client.post("/api/clues", json={"answer": "KATT"})
    assert r.status_code == 503


def test_index_page(client):
    r = client.get("/")
    assert r.status_code == 200 and "Korsordsmakaren" in r.text
