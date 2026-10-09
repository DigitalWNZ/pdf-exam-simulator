import pytest
from fastapi.testclient import TestClient

from exam_sim.server.app import MAX_PROGRESS_BYTES, create_app


@pytest.fixture
def client(dirs):
    banks, data, web = dirs
    return TestClient(create_app(banks, data, web))


def test_list_and_get_bank(client):
    assert client.get("/api/banks").json() == [{"id": "demo", "title": "Demo Bank", "question_count": 1}]
    assert client.get("/api/banks/demo").json()["bank"]["title"] == "Demo Bank"


def test_unknown_and_invalid_bank(client):
    assert client.get("/api/banks/nope").status_code == 404
    assert client.get("/api/banks/Not_Valid").status_code == 400
    assert client.get("/api/banks/nope/progress").status_code == 404
    assert client.put("/api/banks/nope/progress", json={"version": 1, "bank_id": "nope"}).status_code == 404


def test_progress_roundtrip(client, dirs):
    _, data, _ = dirs
    doc = client.get("/api/banks/demo/progress").json()
    assert doc == {"version": 1, "bank_id": "demo", "updated_at": None, "questions": {}, "exams": [],
                   "active_exam": None, "practice": None}
    doc["questions"]["1"] = {"attempts": 1, "correct": 1, "wrong": 0, "last_result": "correct",
                             "last_answer": ["A"], "last_at": "2026-01-01T00:00:00Z", "in_mistakes": False}
    res = client.put("/api/banks/demo/progress", json=doc)
    assert res.status_code == 200 and res.json()["ok"] is True and res.json()["updated_at"]
    again = client.get("/api/banks/demo/progress").json()
    assert again["questions"]["1"]["attempts"] == 1 and again["updated_at"] == res.json()["updated_at"]
    assert not list((data / "progress").glob("*.tmp"))


def test_put_rejects_bad_documents(client):
    assert client.put("/api/banks/demo/progress", json={"version": 2, "bank_id": "demo"}).status_code == 400
    assert client.put("/api/banks/demo/progress", json={"version": 1, "bank_id": "other"}).status_code == 400
    assert client.put("/api/banks/demo/progress", json=[1, 2]).status_code == 400
    r = client.put("/api/banks/demo/progress", content=b"not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_put_rejects_oversize_body(client):
    big = b'{"version":1,"bank_id":"demo","pad":"' + b"x" * MAX_PROGRESS_BYTES + b'"}'
    r = client.put("/api/banks/demo/progress", content=big, headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_corrupt_progress_is_backed_up(client, dirs):
    _, data, _ = dirs
    path = data / "progress" / "demo.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken")
    assert client.get("/api/banks/demo/progress").json()["questions"] == {}
    assert not path.exists() and list(path.parent.glob("demo.json.corrupt-*"))


def test_images_and_static(client):
    assert client.get("/banks/demo/images/q001_1.png").status_code == 200
    assert client.get("/banks/demo/images/missing.png").status_code == 404
    assert client.get("/banks/demo/images/..%2Fquestions.json").status_code in (400, 404)
    r = client.get("/")
    assert r.status_code == 200 and "ok" in r.text


def test_app_without_web_dir_still_serves_api(dirs, tmp_path):
    banks, data, _ = dirs
    c = TestClient(create_app(banks, data, tmp_path / "nowhere"))
    assert c.get("/api/banks").status_code == 200
