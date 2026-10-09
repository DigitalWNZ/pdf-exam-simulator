"""RawQuestion → Question: joins wrapped text, writes images, resolves the answer key."""
from __future__ import annotations

from typing import Callable

from .blocks import RawQuestion, join_lines
from .extract import Image, Item, Line
from .key import resolve_key
from .model import Block, Option, Question, TextBlock


def assemble_blocks(parts: list[Item], write_image: Callable[[Image], Block]) -> list[Block]:
    blocks: list[Block] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            text = join_lines(buf)
            buf.clear()
            if text:
                blocks.append(TextBlock(text=text))

    for part in parts:
        if isinstance(part, Line):
            buf.append(part.text)
        else:
            flush()
            blocks.append(write_image(part))
    flush()
    return blocks


def build_question(raw: RawQuestion, write_image: Callable[[Image], Block]) -> Question:
    pdf_answer = sorted(raw.pdf_answer or [])
    key = resolve_key(pdf_answer, raw.votes)
    return Question(
        number=raw.number,
        topic=raw.topic,
        stem=assemble_blocks(raw.stem_parts, write_image),
        options=[Option(letter=o.letter, content=assemble_blocks(o.parts, write_image)) for o in raw.options],
        answer=key.answer,
        select_count=len(key.answer),
        pdf_answer=pdf_answer,
        votes=list(raw.votes),
        answer_source=key.source,
        disputed=key.disputed,
    )
