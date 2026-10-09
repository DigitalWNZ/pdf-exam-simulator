"""Integration test against the real PDF. Skipped when source/pde_349.pdf is absent."""
import json

import pytest

from exam_sim.parser.cli import main, parse_pdf, slugify


@pytest.fixture(scope="module")
def bank(real_pdf, tmp_path_factory):
    out = tmp_path_factory.mktemp("banks")
    doc, report = parse_pdf(real_pdf, out, "pde-test", "PDE test")
    return doc, report, out / "pde-test"


def by_number(doc):
    return {q["number"]: q for q in doc["questions"]}


def test_counts_and_numbering(bank):
    doc, report, _ = bank
    assert doc["bank"]["question_count"] == 349 and len(doc["questions"]) == 349
    assert [q["number"] for q in doc["questions"]] == list(range(1, 350))
    assert report.errors() == []
    assert report.missing_numbers == [] and report.duplicate_numbers == []
    assert report.option_histogram == {4: 324, 5: 20, 6: 5}
    assert report.stray == []


def test_keys_and_sources(bank):
    q = by_number(bank[0])
    assert q[1]["answer"] == ["C"] and q[1]["answer_source"] == "votes" and q[1]["disputed"] is False
    assert q[10]["answer"] == ["B", "D", "E"] and q[10]["select_count"] == 3
    assert q[340]["answer"] == ["C"] and q[340]["pdf_answer"] == ["B"] and q[340]["disputed"] is True
    assert q[328]["answer"] == ["A"] and q[328]["answer_source"] == "votes_tiebreak_pdf"
    assert q[321]["answer_source"] == "pdf" and q[321]["votes"] == [] and q[321]["answer"] == ["B"]
    assert q[320]["answer"] == ["D"] and q[320]["pdf_answer"] == ["B", "D"] and q[320]["disputed"] is True
    assert q[9]["votes"] == [{"letters": ["D"], "pct": 63}, {"letters": ["B"], "pct": 38}]


def test_images(bank):
    doc, report, bank_dir = bank
    q = by_number(doc)
    assert [b["type"] for b in q[9]["stem"]] == ["text", "image", "text"]
    assert (bank_dir / q[9]["stem"][1]["src"]).is_file()
    assert len(q[243]["options"]) == 4
    for o in q[243]["options"]:
        assert len(o["content"]) == 1 and o["content"][0]["type"] == "image"
        assert (bank_dir / o["content"][0]["src"]).is_file()
    assert report.image_blocks >= 13 and report.warnings == []


def test_no_noise_and_sequential_letters(bank):
    doc = bank[0]
    text = json.dumps(doc, ensure_ascii=False)
    assert "zhangxuetu" not in text and "[202610]" not in text and "Most Voted" not in text
    for q in doc["questions"]:
        letters = [o["letter"] for o in q["options"]]
        assert letters == [chr(65 + i) for i in range(len(letters))], q["number"]
        assert set(q["answer"]) <= set(letters), q["number"]
        assert q["options"] and q["stem"], q["number"]
        assert q["topic"] == "1"


def test_wrapped_lines_and_numbered_steps(bank):
    q = by_number(bank[0])
    assert len(q[236]["options"]) == 4
    assert q[236]["options"][0]["content"][0]["text"].endswith("when Region A is down.")
    first = q[321]["options"][0]["content"][0]["text"]
    assert first.startswith("1. Export metadata") and "\n2. Implement Dataproc Metastore" in first


def test_mislabeled_option_letter_q224(bank):
    # p.183: the PDF prints option C as "G." and says "Correct Answer: G" / "G (89%)"; the parser renumbers it.
    doc, report, _ = bank
    q = by_number(doc)[224]
    assert [o["letter"] for o in q["options"]] == ["A", "B", "C", "D"]
    assert q["options"][2]["content"][0]["text"].startswith("Messages in your Dataflow job are processed in less than 30 seconds")
    assert q["answer"] == ["C"] and q["pdf_answer"] == ["C"] and q["answer_source"] == "votes" and q["disputed"] is False
    assert q["votes"] == [{"letters": ["C"], "pct": 89}, {"letters": ["B"], "pct": 11}]
    assert report.relabeled == [(224, "G", "C")]


def test_cli_writes_bank_and_reports(real_pdf, tmp_path, capsys):
    code = main([str(real_pdf), "--id", "pde-cli", "--title", "T", "--out", str(tmp_path), "--strict"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "questions: 349" in out and "errors: none" in out
    doc = json.loads((tmp_path / "pde-cli" / "questions.json").read_text(encoding="utf-8"))
    assert doc["bank"] == {**doc["bank"], "id": "pde-cli", "title": "T", "source_pdf": real_pdf.name, "question_count": 349}
    assert (tmp_path / "pde-cli" / "images").is_dir()


def test_slugify():
    # The brief's slugify keeps [a-z0-9], so the leading question count survives ("349题_" → "349-").
    assert slugify("349题_PROFESSIONAL-DATA-ENGINEER_202610_without_discussion_en") == "349-professional-data-engineer-202610-without-discussion-en"
    assert slugify("###") == "bank"
