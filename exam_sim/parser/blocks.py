"""Item stream → raw question blocks. A small state machine; pure (no IO)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .extract import QUESTION_HEADER, Image, Item, Line
from .model import Vote

TOPIC_RE = re.compile(r"^Topic (\d+)$")
OPTION_RE = re.compile(r"^([A-Z])\.(?:\s+(.*))?$")
CORRECT_RE = re.compile(r"^Correct Answer:\s*([A-Z]+)\s*$")
VOTE_RE = re.compile(r"([A-Z]+)\s*\((\d+)%\)")
VOTE_LINE_RE = re.compile(r"^(?:\s*[A-Z]+\s*\(\d+%\)\s*)+$")   # one or more entries, e.g. "BC (7%) BE (3%)"
STEP_RE = re.compile(r"^\d+\.\s")
MOST_VOTED = "Most Voted"
VOTES_HEADER = "Community vote distribution"


@dataclass
class RawOption:
    letter: str
    parts: list[Item] = field(default_factory=list)
    most_voted: bool = False


@dataclass
class RawQuestion:
    number: int
    page: int
    topic: str | None = None
    stem_parts: list[Item] = field(default_factory=list)
    options: list[RawOption] = field(default_factory=list)
    pdf_answer: list[str] | None = None
    votes: list[Vote] = field(default_factory=list)
    stray: list[Item] = field(default_factory=list)
    relabeled: dict[str, str] = field(default_factory=dict)   # PDF option letter → assigned letter (e.g. {"G": "C"})


def join_lines(lines: list[str]) -> str:
    """Join wrapped PDF lines with spaces; keep a newline before numbered steps ('1. ...')."""
    out = ""
    for raw in lines:
        ln = raw.strip()
        if not ln:
            continue
        if not out:
            out = ln
        elif STEP_RE.match(ln):
            out += "\n" + ln
        else:
            out += " " + ln
    return out


def _letters(s: str, relabeled: dict[str, str] | None = None) -> list[str]:
    return sorted({(relabeled or {}).get(c, c) for c in s})


def _is_mislabeled_option(items: list[Item], i: int, letter: str, expected: str) -> bool:
    """An option line whose letter is *ahead* of the sequence (e.g. 'G.' where 'C.' is due) is a mislabeled
    option — not wrapped text — when the expected letter never starts a line later in the same question.
    (Real case: Q224 of pde_349.pdf prints option C, its key and its votes as 'G'.)"""
    if letter <= expected:          # earlier letters are already used: wrapped text such as '…region B.'
        return False
    for nxt in items[i + 1:]:
        if isinstance(nxt, Image):
            continue
        if QUESTION_HEADER.match(nxt.text) or CORRECT_RE.match(nxt.text):
            break
        m = OPTION_RE.match(nxt.text)
        if m and m.group(1) == expected:
            return False
    return True


def parse_questions(items: list[Item]) -> list[RawQuestion]:
    questions: list[RawQuestion] = []
    cur: RawQuestion | None = None
    state = "stem"          # stem | options | answer | votes
    expected = "A"          # next option letter we will accept

    for i, it in enumerate(items):
        if isinstance(it, Image):
            if cur is None:
                continue
            if state == "stem":
                cur.stem_parts.append(it)
            elif state == "options":
                cur.options[-1].parts.append(it)
            else:
                cur.stray.append(it)
            continue

        text = it.text
        m = QUESTION_HEADER.match(text)
        if m:
            if cur is not None:
                questions.append(cur)
            cur = RawQuestion(number=int(m.group(1)), page=it.page)
            state, expected = "stem", "A"
            continue
        if cur is None:
            continue

        if state == "stem" and cur.topic is None and not cur.stem_parts:
            m = TOPIC_RE.match(text)
            if m:
                cur.topic = m.group(1)
                continue

        if state in ("stem", "options"):
            if text == MOST_VOTED:
                if cur.options:
                    cur.options[-1].most_voted = True
                continue
            tagged = False
            if text.endswith(" " + MOST_VOTED):
                text = text[: -len(MOST_VOTED)].rstrip()
                tagged = True
            m = CORRECT_RE.match(text)
            if m:
                cur.pdf_answer = _letters(m.group(1), cur.relabeled)
                state = "answer"
                continue
            m = OPTION_RE.match(text)
            if m and (m.group(1) == expected
                      or (state == "options" and _is_mislabeled_option(items, i, m.group(1), expected))):
                if m.group(1) != expected:
                    cur.relabeled[m.group(1)] = expected
                opt = RawOption(letter=expected, most_voted=tagged)
                if m.group(2):
                    opt.parts.append(Line(m.group(2).strip(), it.page))
                cur.options.append(opt)
                expected = chr(ord(expected) + 1)
                state = "options"
                continue
            target = cur.options[-1].parts if state == "options" else cur.stem_parts
            target.append(Line(text, it.page))
            if tagged and cur.options:
                cur.options[-1].most_voted = True
            continue

        if state == "answer":
            if text == VOTES_HEADER:
                state = "votes"
            else:
                cur.stray.append(it)
            continue

        if VOTE_LINE_RE.match(text):     # state == "votes"; a line may hold several entries
            for m in VOTE_RE.finditer(text):
                cur.votes.append(Vote(letters=_letters(m.group(1), cur.relabeled), pct=int(m.group(2))))
        else:
            cur.stray.append(it)

    if cur is not None:
        questions.append(cur)
    return questions
