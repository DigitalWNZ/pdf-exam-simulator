import json

import pytest


@pytest.fixture
def bank_doc():
    return {
        "schema_version": 1,
        "bank": {"id": "demo", "title": "Demo Bank", "source_pdf": "demo.pdf",
                 "parsed_at": "2026-01-01T00:00:00+00:00", "question_count": 1},
        "questions": [{
            "number": 1, "topic": "1",
            "stem": [{"type": "text", "text": "2 + 2 = ?"}],
            "options": [{"letter": "A", "content": [{"type": "text", "text": "4"}]},
                        {"letter": "B", "content": [{"type": "text", "text": "5"}]}],
            "answer": ["A"], "select_count": 1, "pdf_answer": ["A"],
            "votes": [{"letters": ["A"], "pct": 100}], "answer_source": "votes", "disputed": False,
        }],
    }


@pytest.fixture
def dirs(tmp_path, bank_doc):
    banks, data, web = tmp_path / "banks", tmp_path / "data", tmp_path / "web"
    (banks / "demo" / "images").mkdir(parents=True)
    (banks / "demo" / "questions.json").write_text(json.dumps(bank_doc), encoding="utf-8")
    (banks / "demo" / "images" / "q001_1.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    web.mkdir()
    (web / "index.html").write_text("<!doctype html><title>t</title>ok", encoding="utf-8")
    return banks, data, web
