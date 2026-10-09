import pytest

from exam_sim.parser.key import resolve_key
from exam_sim.parser.model import Vote


def V(letters: str, pct: int) -> Vote:
    return Vote(letters=sorted(letters), pct=pct)


@pytest.mark.parametrize("pdf, votes, answer, source, disputed", [
    (["C"], [V("C", 100)], ["C"], "votes", False),
    (["B"], [V("C", 100)], ["C"], "votes", True),                                     # Q340: community wins
    (["B", "D", "E"], [V("BDE", 90), V("BCD", 10)], ["B", "D", "E"], "votes", False),
    (["A"], [V("A", 50), V("B", 50)], ["A"], "votes_tiebreak_pdf", True),             # Q328: tie → PDF
    (["C", "E"], [V("DE", 45), V("CE", 45), V("CD", 9)], ["C", "E"], "votes_tiebreak_pdf", True),  # Q109
    (["X"], [V("A", 50), V("B", 50)], ["A"], "votes_tie_first", True),
    (["B"], [], ["B"], "pdf", False),                                                  # Q321+: no votes
    ([], [], [], "pdf", False),
    (["B", "D"], [V("D", 100)], ["D"], "votes", True),                                # Q320
])
def test_resolve_key(pdf, votes, answer, source, disputed):
    r = resolve_key(pdf, votes)
    assert (r.answer, r.source, r.disputed) == (answer, source, disputed)


def test_top_is_by_percentage_not_list_order():
    r = resolve_key(["A"], [V("B", 40), V("A", 60)])
    assert (r.answer, r.source, r.disputed) == (["A"], "votes", False)


def test_answer_is_sorted_even_when_pdf_answer_is_not():
    assert resolve_key(["D", "B"], []).answer == ["B", "D"]
