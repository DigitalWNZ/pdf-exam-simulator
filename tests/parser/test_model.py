from exam_sim.parser.model import (
    BankMeta, ImageBlock, Option, Question, TextBlock, Vote, bank_to_dict,
)


def test_bank_to_dict_matches_schema():
    q = Question(
        number=9, topic="1",
        stem=[TextBlock(text="Error:"), ImageBlock(src="images/q009_1.png", w=709, h=208), TextBlock(text="Which?")],
        options=[Option(letter="A", content=[TextBlock(text="a")]), Option(letter="B", content=[TextBlock(text="b")])],
        answer=["B"], select_count=1, pdf_answer=["B"],
        votes=[Vote(letters=["B"], pct=63), Vote(letters=["A"], pct=38)],
        answer_source="votes", disputed=False,
    )
    meta = BankMeta(id="demo", title="Demo", source_pdf="demo.pdf", parsed_at="2026-10-09T00:00:00+00:00", question_count=1)
    doc = bank_to_dict(meta, [q])
    assert doc["schema_version"] == 1
    assert doc["bank"] == {"id": "demo", "title": "Demo", "source_pdf": "demo.pdf", "parsed_at": "2026-10-09T00:00:00+00:00", "question_count": 1}
    assert doc["questions"][0]["stem"][1] == {"type": "image", "src": "images/q009_1.png", "w": 709, "h": 208}
    assert doc["questions"][0]["stem"][0] == {"type": "text", "text": "Error:"}
    assert doc["questions"][0]["options"][0] == {"letter": "A", "content": [{"type": "text", "text": "a"}]}
    assert doc["questions"][0]["votes"] == [{"letters": ["B"], "pct": 63}, {"letters": ["A"], "pct": 38}]
    assert set(doc["questions"][0]) == {"number", "topic", "stem", "options", "answer", "select_count", "pdf_answer", "votes", "answer_source", "disputed"}
