"""Answer-key rule: top community vote; PDF 'Correct Answer' as tie-breaker and fallback."""
from __future__ import annotations

from dataclasses import dataclass

from .model import Vote

SOURCE_PDF = "pdf"
SOURCE_VOTES = "votes"
SOURCE_TIEBREAK = "votes_tiebreak_pdf"
SOURCE_TIE_FIRST = "votes_tie_first"


@dataclass
class KeyResult:
    answer: list[str]
    source: str
    disputed: bool


def resolve_key(pdf_answer: list[str], votes: list[Vote]) -> KeyResult:
    pdf = sorted(pdf_answer)
    if not votes:
        return KeyResult(answer=pdf, source=SOURCE_PDF, disputed=False)
    top = max(v.pct for v in votes)
    tied = [sorted(v.letters) for v in votes if v.pct == top]
    if len(tied) == 1:
        return KeyResult(answer=tied[0], source=SOURCE_VOTES, disputed=tied[0] != pdf)
    if pdf in tied:
        return KeyResult(answer=pdf, source=SOURCE_TIEBREAK, disputed=True)
    return KeyResult(answer=tied[0], source=SOURCE_TIE_FIRST, disputed=True)
