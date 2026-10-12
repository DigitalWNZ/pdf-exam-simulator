"""Bilingual (Chinese + English) Markdown-export PDFs → raw question blocks, English text only.

Layout (e.g. pmle.pdf):
    问题 N / 题⽬ / <Chinese stem> / <English stem> / 选项 /
    A. <Chinese option> / <English option> / B. ... /
    正确答案：C. <English text of the correct option(s)> / 解析： <Chinese explanation (ignored)>

Within each stem/option the English text is the maximal trailing run of lines containing no CJK characters.
The answer letters are recovered by matching "L. <English option text>" inside the 正确答案 text (handles
multi-answer keys such as "D. … E. …"); a leading letter is the fallback. Pure (no IO) apart from `read_lines`.
"""
from __future__ import annotations

import re
from pathlib import Path

from .blocks import RawOption, RawQuestion
from .extract import Line, read_items

HEADER_RE = re.compile(r"^问题\s*(\d+)$")
STEM_MARK = re.compile(r"^题\s*[目⽬]$")
OPTIONS_MARK = "选项"
OPTION_RE = re.compile(r"^([A-H])\.\s*(.*)$")
ANSWER_RE = re.compile(r"^正确答案\s*[：:]\s*(.*)$")
EXPLAIN_RE = re.compile(r"^解析\s*[：:]?")
FOOTER_RE = (re.compile(r"^\S+\.md$"), re.compile(r"^\d{4}-\d{2}-\d{2}$"), re.compile(r"^\d*\s*/\s*\d*$"))
# CJK ideographs, Kangxi/CJK radicals (this PDF prints e.g. '⼀' U+2F00), CJK punctuation, full-width forms.
CJK_RE = re.compile(r"[\u2e80-\u2fdf\u3000-\u303f\u3400-\u9fff\uf900-\ufaff\uff00-\uffef]")


def has_cjk(text: str) -> bool:
    return bool(CJK_RE.search(text))


def is_bilingual(lines: list[Line]) -> bool:
    headers = sum(1 for ln in lines if HEADER_RE.match(ln.text))
    answers = sum(1 for ln in lines if ANSWER_RE.match(ln.text))
    return headers > 0 and answers > 0


def english_tail(lines: list[Line]) -> list[Line]:
    """The trailing run of lines without CJK characters (the English half of a bilingual block)."""
    i = len(lines)
    while i > 0 and not has_cjk(lines[i - 1].text):
        i -= 1
    return lines[i:]


def _norm(s: str) -> str:
    return " ".join(s.split()).lower()


def answer_letters(answer_text: str, options: list[tuple[str, str]]) -> list[str]:
    """options: (letter, English text). Match 'L. text' (prefix of the text, in case of truncation)."""
    ans = _norm(answer_text)
    found = []
    for letter, text in options:
        t = _norm(text)
        probe = f"{letter.lower()}. {t[:60]}" if t else None
        if probe and probe in ans:
            found.append(letter)
    if found:
        return sorted(found)
    m = re.match(r"^([A-H])(?:[.\s,，、]|$)", answer_text.strip())
    return [m.group(1)] if m else []


def read_lines(pdf_path: Path) -> list[Line]:
    items, _ = read_items(pdf_path)
    return [it for it in items if isinstance(it, Line) and not any(p.match(it.text) for p in FOOTER_RE)]


def parse_bilingual(lines: list[Line]) -> list[RawQuestion]:
    questions: list[RawQuestion] = []
    cur: RawQuestion | None = None
    state = "pre"                    # pre | stem | options | answer | explain
    stem: list[Line] = []
    opts: list[tuple[str, list[Line]]] = []
    answer: list[str] = []

    def finish() -> None:
        if cur is None:
            return
        cur.stem_parts = list(english_tail(stem))
        english = []
        for letter, parts in opts:
            tail = english_tail(parts)
            cur.options.append(RawOption(letter=letter, parts=list(tail)))
            english.append((letter, " ".join(p.text for p in tail)))
        if answer:
            cur.pdf_answer = answer_letters(" ".join(answer), english) or None
        questions.append(cur)

    for ln in lines:
        text = ln.text
        m = HEADER_RE.match(text)
        if m:
            finish()
            cur = RawQuestion(number=int(m.group(1)), page=ln.page)
            state, stem, opts, answer = "stem", [], [], []
            continue
        if cur is None:
            continue
        if state in ("stem", "options", "answer"):
            m = ANSWER_RE.match(text)
            if m and state != "answer":
                state = "answer"
                answer = [m.group(1)] if m.group(1) else []
                continue
            if EXPLAIN_RE.match(text):
                state = "explain"
                continue
        if state == "stem":
            if STEM_MARK.match(text) and not stem:
                continue
            if text == OPTIONS_MARK:
                state = "options"
                continue
            stem.append(ln)
        elif state == "options":
            m = OPTION_RE.match(text)
            expected = chr(ord("A") + len(opts))
            if m and m.group(1) == expected:
                opts.append((expected, [Line(m.group(2), ln.page)] if m.group(2) else []))
            elif opts:
                opts[-1][1].append(ln)
        elif state == "answer":
            answer.append(text)
    finish()
    return questions
