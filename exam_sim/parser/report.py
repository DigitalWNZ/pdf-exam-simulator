"""Validation report for a parsed bank. --strict turns errors() into a non-zero exit."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .blocks import RawQuestion
from .extract import Line
from .model import ImageBlock, Question, TextBlock

CHOOSE_RE = re.compile(r"\((?:Choose|Select)\s+(two|three|four|\d)\)", re.I)
WORDS = {"two": 2, "three": 3, "four": 4}


@dataclass
class Report:
    question_count: int = 0
    first_number: int | None = None
    last_number: int | None = None
    missing_numbers: list[int] = field(default_factory=list)
    duplicate_numbers: list[int] = field(default_factory=list)
    option_histogram: dict[int, int] = field(default_factory=dict)
    image_blocks: int = 0
    no_votes: int = 0
    no_options: list[int] = field(default_factory=list)
    no_answer: list[int] = field(default_factory=list)
    answer_not_in_options: list[int] = field(default_factory=list)
    choose_hint_mismatch: list[tuple[int, int, int]] = field(default_factory=list)   # (number, hint, select_count)
    most_voted_mismatch: list[tuple[int, str, str]] = field(default_factory=list)    # (number, most_voted, key)
    disputed: list[tuple[int, str, str, str]] = field(default_factory=list)          # (number, key, pdf, source)
    stray: list[tuple[int, int, str]] = field(default_factory=list)                  # (number, page, text)
    warnings: list[str] = field(default_factory=list)

    def errors(self) -> list[str]:
        out = []
        if self.no_options:
            out.append(f"questions with no options: {self.no_options}")
        if self.no_answer:
            out.append(f"questions with no answer: {self.no_answer}")
        if self.answer_not_in_options:
            out.append(f"answer letters missing from options: {self.answer_not_in_options}")
        return out


def _stem_text(q: Question) -> str:
    return " ".join(b.text for b in q.stem if isinstance(b, TextBlock))


def build_report(questions: list[Question], raws: list[RawQuestion], warnings: list[str] | None = None) -> Report:
    r = Report(question_count=len(questions), warnings=list(warnings or []))
    numbers = [q.number for q in questions]
    if numbers:
        r.first_number, r.last_number = min(numbers), max(numbers)
        r.missing_numbers = sorted(set(range(r.first_number, r.last_number + 1)) - set(numbers))
        r.duplicate_numbers = sorted(n for n, c in Counter(numbers).items() if c > 1)
    r.option_histogram = dict(sorted(Counter(len(q.options) for q in questions).items()))
    raw_by_number = {raw.number: raw for raw in raws}
    for q in questions:
        letters = {o.letter for o in q.options}
        r.image_blocks += sum(isinstance(b, ImageBlock) for b in q.stem)
        r.image_blocks += sum(isinstance(b, ImageBlock) for o in q.options for b in o.content)
        if not q.votes:
            r.no_votes += 1
        if not q.options:
            r.no_options.append(q.number)
        if not q.answer:
            r.no_answer.append(q.number)
        elif not set(q.answer) <= letters:
            r.answer_not_in_options.append(q.number)
        m = CHOOSE_RE.search(_stem_text(q))
        if m:
            hint = WORDS.get(m.group(1).lower()) or int(m.group(1))
            if hint != q.select_count:
                r.choose_hint_mismatch.append((q.number, hint, q.select_count))
        if q.disputed:
            r.disputed.append((q.number, "".join(q.answer), "".join(q.pdf_answer), q.answer_source))
        raw = raw_by_number.get(q.number)
        if raw is not None:
            mv = "".join(sorted(o.letter for o in raw.options if o.most_voted))
            if mv and mv != "".join(q.answer):
                r.most_voted_mismatch.append((q.number, mv, "".join(q.answer)))
            for s in raw.stray:
                r.stray.append((q.number, s.page, s.text if isinstance(s, Line) else "<image>"))
    return r


def format_report(r: Report) -> str:
    lines = [
        f"questions: {r.question_count} (#{r.first_number}–#{r.last_number})",
        f"missing numbers: {r.missing_numbers or 'none'} | duplicates: {r.duplicate_numbers or 'none'}",
        f"options per question: {r.option_histogram}",
        f"image blocks: {r.image_blocks}",
        f"questions without vote data: {r.no_votes}",
        f"disputed ({len(r.disputed)}): " + (", ".join(f"Q{n} key={k} pdf={p} [{s}]" for n, k, p, s in r.disputed) or "none"),
        f"choose-N hint mismatches: {r.choose_hint_mismatch or 'none'}",
        f"'Most Voted' marker != key: {r.most_voted_mismatch or 'none'}",
        f"stray lines after 'Correct Answer' ({len(r.stray)}): "
        + ("; ".join(f"Q{n} p{p}: {t!r}" for n, p, t in r.stray[:20]) or "none"),
    ]
    lines += [f"warning: {w}" for w in r.warnings]
    errs = r.errors()
    lines.append("errors: " + ("; ".join(errs) if errs else "none"))
    return "\n".join(lines)
