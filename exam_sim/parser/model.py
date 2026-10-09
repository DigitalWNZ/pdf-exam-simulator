"""Output data model for a parsed question bank (banks/<id>/questions.json)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Union

SCHEMA_VERSION = 1


@dataclass
class TextBlock:
    text: str
    type: str = field(default="text", init=False)


@dataclass
class ImageBlock:
    src: str
    w: int
    h: int
    type: str = field(default="image", init=False)


Block = Union[TextBlock, ImageBlock]


@dataclass
class Option:
    letter: str
    content: list[Block]


@dataclass
class Vote:
    letters: list[str]
    pct: int


@dataclass
class Question:
    number: int
    topic: str | None
    stem: list[Block]
    options: list[Option]
    answer: list[str]
    select_count: int
    pdf_answer: list[str]
    votes: list[Vote]
    answer_source: str
    disputed: bool


@dataclass
class BankMeta:
    id: str
    title: str
    source_pdf: str
    parsed_at: str
    question_count: int


def bank_to_dict(meta: BankMeta, questions: list[Question]) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "bank": asdict(meta),
        "questions": [asdict(q) for q in questions],
    }
