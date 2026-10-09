import json

import pytest

from exam_sim.server.storage import BankNotFound, InvalidBankId, Storage, default_progress


def test_list_banks_sorted_by_title_and_skips_broken(dirs):
    banks, data, _ = dirs
    (banks / "zzz").mkdir()
    (banks / "zzz" / "questions.json").write_text("{not json")
    (banks / "aaa").mkdir()
    (banks / "aaa" / "questions.json").write_text(json.dumps({"bank": {"id": "aaa", "title": "Alpha", "question_count": 2}}))
    s = Storage(banks, data)
    assert s.list_banks() == [{"id": "aaa", "title": "Alpha", "question_count": 2},
                              {"id": "demo", "title": "Demo Bank", "question_count": 1}]


def test_list_banks_empty_when_dir_missing(tmp_path):
    assert Storage(tmp_path / "none", tmp_path / "d").list_banks() == []


def test_bank_ids_and_missing_banks(dirs):
    s = Storage(*dirs[:2])
    for bad in ("Demo", "", "a b", "-x", "x" * 65, "a/b"):
        with pytest.raises(InvalidBankId):
            s.load_bank(bad)
    with pytest.raises(BankNotFound):
        s.load_bank("ghost")
    assert s.load_bank("demo")["bank"]["id"] == "demo"


def test_image_path(dirs):
    s = Storage(*dirs[:2])
    assert s.image_path("demo", "q001_1.png").is_file()
    for bad in ("missing.png", "../questions.json", "", "a/b.png"):
        with pytest.raises(BankNotFound):
            s.image_path("demo", bad)


def test_progress_default_save_load(dirs):
    s = Storage(*dirs[:2])
    assert s.load_progress("demo") == default_progress("demo")
    doc = default_progress("demo")
    doc["exams"] = [{"id": "x"}]
    saved = s.save_progress("demo", doc)
    assert saved["updated_at"] and saved["exams"] == [{"id": "x"}]
    assert s.load_progress("demo") == saved
    assert not list(s.progress_dir.glob("*.tmp"))


def test_save_validates(dirs):
    s = Storage(*dirs[:2])
    with pytest.raises(ValueError):
        s.save_progress("demo", {"version": 1, "bank_id": "nope"})
    with pytest.raises(ValueError):
        s.save_progress("demo", {"version": 0, "bank_id": "demo"})
    with pytest.raises(ValueError):
        s.save_progress("demo", ["not", "a", "dict"])
    with pytest.raises(BankNotFound):
        s.save_progress("ghost", default_progress("ghost"))
    with pytest.raises(BankNotFound):
        s.load_progress("ghost")


def test_corrupt_progress_is_backed_up_not_overwritten(dirs):
    s = Storage(*dirs[:2])
    path = s.progress_path("demo")
    path.parent.mkdir(parents=True)
    path.write_text("[1, 2")
    assert s.load_progress("demo") == default_progress("demo")
    assert not path.exists()
    [backup] = list(path.parent.glob("demo.json.corrupt-*"))
    assert backup.read_text() == "[1, 2"


def test_non_object_progress_counts_as_corrupt(dirs):
    s = Storage(*dirs[:2])
    path = s.progress_path("demo")
    path.parent.mkdir(parents=True)
    path.write_text("[]")
    assert s.load_progress("demo") == default_progress("demo")
    assert list(path.parent.glob("demo.json.corrupt-*"))
