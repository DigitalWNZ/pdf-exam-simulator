# PDF Exam Simulator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A local, single-user exam simulator: a Python CLI parses ExamTopics-style PDFs into `banks/<id>/questions.json`, a FastAPI server persists progress to `data/progress/<id>.json`, and a vanilla-JS browser UI offers Exam, Practice and Review-mistakes modes.

**Architecture:** Three units joined by the question JSON schema. `exam_sim/parser` (PyMuPDF → reading-order item stream → state machine → key rule → JSON + PNGs). `exam_sim/server` (FastAPI: 4 JSON endpoints, bank images, static `web/`; atomic whole-document progress writes). `web/` (hash-routed SPA, ES modules, no build; pure logic in DOM-free modules tested with `node --test`).

**Tech Stack:** Python 3.12 via `uv` (pymupdf, fastapi, uvicorn, pytest, httpx); Node 22 for `node --test` only; browser ES modules; no npm packages.

**Spec:** `docs/superpowers/specs/2026-10-09-pdf-exam-simulator-design.md` (read it first; §2 lists every product decision).

## Global Constraints

- Python `>=3.11`; the repo pins `.python-version` = `3.12.6` (this is where `uv` is installed on this machine — run `uv` from the repo root).
- Node 22 is only used to run `node --test tests/web/*.test.js`; `web/` must not need a build step or any npm package.
- Answer key rule (verbatim from spec §4.3): no votes → `pdf_answer`; one top vote → that; tie → `pdf_answer` if among the tied, else the first tied; `select_count = len(answer)`; `disputed` when key ≠ `pdf_answer` or a tie occurred.
- Multi-select grading is all-or-nothing; UI caps picks at `select_count`; Practice/Review **Check** requires exactly `select_count` picks.
- Options are shuffled in Exam mode only; Practice, Review and post-exam review use the PDF's original order.
- Mistakes pool: every question ever answered wrong, in any mode; removed only by explicit per-question or clear-all actions.
- Unanswered exam questions count as wrong and enter the mistakes pool. Pass line `PASS_PCT = 70`.
- Progress is written atomically (`.tmp` + `os.replace`); corrupt files are renamed `*.corrupt-<ts>`, never overwritten.
- `source/`, `banks/`, `data/`, `scratch/` are gitignored; never commit PDF content or generated banks.
- Commit after every task with the message given in the task.

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml`, `.python-version`, `package.json`, `README.md` | Project config, scripts (`parse-pdf`, `serve`), test runners |
| `exam_sim/parser/model.py` | Output dataclasses (`TextBlock`, `ImageBlock`, `Option`, `Vote`, `Question`, `BankMeta`) + `bank_to_dict` |
| `exam_sim/parser/extract.py` | `Line`/`Image` items; `read_items` (PyMuPDF), `filter_items` (noise), `to_png`, `extract_items` |
| `exam_sim/parser/blocks.py` | `RawOption`/`RawQuestion`; `parse_questions` state machine; `join_lines` |
| `exam_sim/parser/key.py` | `resolve_key(pdf_answer, votes) -> KeyResult` |
| `exam_sim/parser/images.py` | `ImageWriter` — numbered PNGs per question, placeholder on failure |
| `exam_sim/parser/assemble.py` | `assemble_blocks`, `build_question` (Raw → `Question`) |
| `exam_sim/parser/report.py` | `Report`, `build_report`, `format_report` |
| `exam_sim/parser/cli.py` | `parse_pdf(...)`, `main(argv)` for `parse-pdf` |
| `exam_sim/server/storage.py` | `Storage` (banks, images, progress), `atomic_write_json`, `default_progress` |
| `exam_sim/server/app.py` | `create_app(banks_dir, data_dir, web_dir)` |
| `exam_sim/server/cli.py` | `main(argv)` for `serve` (uvicorn + open browser) |
| `web/index.html`, `web/app.css` | Shell + styles |
| `web/js/config.js` | Constants (`PASS_PCT`, defaults, timings) |
| `web/js/grading.js`, `shuffle.js`, `timer.js`, `progress.js` | Pure, DOM-free logic (node-tested) |
| `web/js/dom.js`, `toast.js`, `keys.js`, `api.js`, `store.js`, `main.js` | DOM helper, toasts, keyboard, fetch, state + debounced save, router |
| `web/js/components/questionCard.js`, `feedback.js`, `drill.js`, `navigator.js` | Reusable UI pieces (`drill.js` = shared pick → Check → feedback → Next loop for Practice and Review) |
| `web/js/views/home.js`, `examSetup.js`, `exam.js`, `examResult.js`, `practiceSetup.js`, `practice.js`, `review.js` | Screens |
| `tests/parser/*`, `tests/server/*`, `tests/web/*` | pytest + node tests |

---

### Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`, `package.json`, `README.md`, `exam_sim/__init__.py`, `exam_sim/parser/__init__.py`, `exam_sim/server/__init__.py`, `tests/__init__.py`, `tests/parser/__init__.py`, `tests/server/__init__.py`, `tests/test_smoke.py`
- Already present: `.gitignore`, `.python-version` (`3.12.6`)

**Interfaces:**
- Produces: importable packages `exam_sim.parser`, `exam_sim.server`; commands `uv run pytest`, `uv run parse-pdf`, `uv run serve` (entry points wired now, modules filled in later tasks); `npm test` → `node --test tests/web/*.test.js`.

- [ ] **Step 1: Write the failing smoke test**

`tests/test_smoke.py`:
```python
import importlib


def test_packages_import():
    assert importlib.import_module("exam_sim.parser")
    assert importlib.import_module("exam_sim.server")
```

- [ ] **Step 2: Create config files**

`pyproject.toml`:
```toml
[project]
name = "exam-sim"
version = "0.1.0"
description = "Local web-based exam simulator fed by ExamTopics-style PDF dumps"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "pymupdf>=1.24",
    "fastapi>=0.110",
    "uvicorn[standard]>=0.29",
]

[project.scripts]
parse-pdf = "exam_sim.parser.cli:main"
serve = "exam_sim.server.cli:main"

[dependency-groups]
dev = [
    "pytest>=8",
    "httpx>=0.27",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["exam_sim"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
addopts = "-q"
```

`package.json`:
```json
{
  "name": "exam-sim-web",
  "private": true,
  "type": "module",
  "scripts": {
    "test": "node --test tests/web/*.test.js"
  }
}
```

`README.md` (stub; completed in Task 18):
```markdown
# PDF Exam Simulator

Local exam simulator fed by ExamTopics-style PDF dumps. See `docs/superpowers/specs/2026-10-09-pdf-exam-simulator-design.md`.
```

Empty `__init__.py` files: `exam_sim/__init__.py`, `exam_sim/parser/__init__.py`, `exam_sim/server/__init__.py`, `tests/__init__.py`, `tests/parser/__init__.py`, `tests/server/__init__.py`.

- [ ] **Step 3: Install and run**

Run: `uv sync && uv run pytest`
Expected: dependencies resolve (pymupdf, fastapi, uvicorn, pytest, httpx) and `1 passed`.

Run: `uv run parse-pdf --help`
Expected: fails with `ModuleNotFoundError`/`AttributeError` for `exam_sim.parser.cli` — correct for now (filled in Task 8).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml package.json README.md .python-version uv.lock exam_sim tests
git commit -m "chore: project scaffold (uv, pytest, node --test)"
```

---

### Task 2: Parser output model

**Files:**
- Create: `exam_sim/parser/model.py`
- Test: `tests/parser/test_model.py`

**Interfaces:**
- Produces: `TextBlock(text)`, `ImageBlock(src, w, h)` (both carry a fixed `type` field), `Block = TextBlock | ImageBlock`, `Option(letter, content: list[Block])`, `Vote(letters: list[str], pct: int)`, `Question(number, topic, stem, options, answer, select_count, pdf_answer, votes, answer_source, disputed)`, `BankMeta(id, title, source_pdf, parsed_at, question_count)`, `bank_to_dict(meta, questions) -> dict`, `SCHEMA_VERSION = 1`.

- [ ] **Step 1: Write the failing test**

`tests/parser/test_model.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/parser/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'exam_sim.parser.model'`

- [ ] **Step 3: Write the model**

`exam_sim/parser/model.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/parser/test_model.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add exam_sim/parser/model.py tests/parser/test_model.py
git commit -m "feat(parser): question bank output model"
```

---

### Task 3: PDF extraction and noise filters

**Files:**
- Create: `exam_sim/parser/extract.py`, `tests/parser/helpers.py`, `tests/parser/conftest.py`
- Test: `tests/parser/test_extract.py`

**Interfaces:**
- Produces: `Line(text: str, page: int)`, `Image(data: bytes, ext: str, width: int, height: int, page: int)` with cached `digest` property, `Item = Line | Image`, `QUESTION_HEADER` regex (`^Question #(\d+)$`), `read_items(pdf_path) -> tuple[list[Item], int]`, `filter_items(items, page_count) -> list[Item]`, `to_png(data, ext) -> bytes`, `extract_items(pdf_path) -> list[Item]`.
- Test helpers: `lines(*texts, page=1) -> list[Line]`, `image(w=40, h=30, page=1, fmt="png") -> Image`, `image_bytes(w, h, fmt) -> bytes`; fixture `real_pdf` (session-scoped, skips when `source/pde_349.pdf` is absent).

- [ ] **Step 1: Write helpers and the failing tests**

`tests/parser/helpers.py`:
```python
"""Synthetic item builders for parser tests (no PDF required)."""
import pymupdf

from exam_sim.parser.extract import Image, Line


def lines(*texts: str, page: int = 1) -> list[Line]:
    return [Line(text=t, page=page) for t in texts]


def image_bytes(w: int = 40, h: int = 30, fmt: str = "png") -> bytes:
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, w, h), False)
    pix.clear_with(128)
    return pix.tobytes(fmt)


def image(w: int = 40, h: int = 30, page: int = 1, fmt: str = "png") -> Image:
    return Image(data=image_bytes(w, h, fmt), ext=fmt, width=w, height=h, page=page)
```

`tests/parser/conftest.py`:
```python
from pathlib import Path

import pytest

REAL_PDF = Path(__file__).resolve().parents[2] / "source" / "pde_349.pdf"


@pytest.fixture(scope="session")
def real_pdf() -> Path:
    if not REAL_PDF.is_file():
        pytest.skip(f"real PDF not present at {REAL_PDF}")
    return REAL_PDF
```

`tests/parser/test_extract.py`:
```python
from exam_sim.parser.extract import Image, Line, filter_items, to_png
from tests.parser.helpers import image, image_bytes, lines


def test_filter_drops_footer_lines_and_preamble():
    items = lines("Professional Data Engineer Questions", "[202610]", "Question #1", "Topic 1",
                  "Stem", "https://zhangxuetu.online", "A. x")
    out = filter_items(items, page_count=1)
    assert [i.text for i in out] == ["Question #1", "Topic 1", "Stem", "A. x"]


def test_filter_drops_watermark_present_on_most_pages_but_keeps_content_images():
    wm = image_bytes(30, 30)
    items: list = [Line("Question #1", 1)]
    for p in range(1, 11):
        items.append(Image(data=wm, ext="png", width=30, height=30, page=p))
    content = image(50, 50, page=3)
    items.append(content)
    imgs = [i for i in filter_items(items, page_count=10) if isinstance(i, Image)]
    assert imgs == [content]


def test_filter_keeps_repeated_image_when_pdf_is_short():
    data = image_bytes(30, 30)
    items = [Line("Question #1", 1), Image(data, "png", 30, 30, 1), Image(data, "png", 30, 30, 2)]
    assert len([i for i in filter_items(items, page_count=2) if isinstance(i, Image)]) == 2


def test_filter_drops_tiny_images():
    items = [Line("Question #1", 1), image(9, 6), image(40, 40)]
    imgs = [i for i in filter_items(items, page_count=1) if isinstance(i, Image)]
    assert len(imgs) == 1 and imgs[0].width == 40


def test_to_png_passthrough_and_conversion():
    png = image_bytes(20, 10, "png")
    assert to_png(png, "png") is png
    jpg = image_bytes(20, 10, "jpeg")
    assert to_png(jpg, "jpeg")[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_digest_is_stable_per_content():
    a, b = image(20, 20), image(20, 20)
    assert a.digest == b.digest
    assert a.digest != image(21, 20).digest
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/parser/test_extract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'exam_sim.parser.extract'`

- [ ] **Step 3: Write the extractor**

`exam_sim/parser/extract.py`:
```python
"""PDF → ordered stream of text lines and images (PyMuPDF), with generic noise filters."""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
from typing import Union

import pymupdf

QUESTION_HEADER = re.compile(r"^Question #(\d+)$")
FOOTER_PATTERNS = (re.compile(r"^\[\d{6}\]$"), re.compile(r"^https?://\S+$"))
MIN_IMAGE_SIDE = 20
WATERMARK_PAGE_FRACTION = 0.5
WATERMARK_MIN_PAGES = 3


@dataclass
class Line:
    text: str
    page: int


@dataclass(eq=False)
class Image:
    data: bytes
    ext: str
    width: int
    height: int
    page: int

    @cached_property
    def digest(self) -> str:
        return hashlib.sha1(self.data).hexdigest()


Item = Union[Line, Image]


def read_items(pdf_path: Path) -> tuple[list[Item], int]:
    """Return (items in reading order across all pages, page_count). No filtering."""
    items: list[Item] = []
    with pymupdf.open(pdf_path) as doc:
        for page in doc:
            pno = page.number + 1
            for block in page.get_text("dict", sort=True)["blocks"]:
                if block["type"] == 1:
                    items.append(Image(data=block["image"], ext=block["ext"],
                                       width=int(block["width"]), height=int(block["height"]), page=pno))
                    continue
                for line in block["lines"]:
                    text = " ".join("".join(span["text"] for span in line["spans"]).split())
                    if text:
                        items.append(Line(text=text, page=pno))
        return items, doc.page_count


def filter_items(items: list[Item], page_count: int) -> list[Item]:
    """Drop watermark images, tiny images, footer lines and everything before the first question."""
    pages_by_digest: dict[str, set[int]] = {}
    for it in items:
        if isinstance(it, Image):
            pages_by_digest.setdefault(it.digest, set()).add(it.page)
    threshold = max(1, page_count) * WATERMARK_PAGE_FRACTION
    watermarks = {d for d, pages in pages_by_digest.items()
                  if len(pages) >= WATERMARK_MIN_PAGES and len(pages) > threshold}

    out: list[Item] = []
    seen_question = False
    for it in items:
        if isinstance(it, Image):
            if it.digest in watermarks or it.width < MIN_IMAGE_SIDE or it.height < MIN_IMAGE_SIDE:
                continue
        else:
            if any(p.match(it.text) for p in FOOTER_PATTERNS):
                continue
            if QUESTION_HEADER.match(it.text):
                seen_question = True
        if seen_question:
            out.append(it)
    return out


def to_png(data: bytes, ext: str) -> bytes:
    if ext.lower() == "png":
        return data
    return pymupdf.Pixmap(data).tobytes("png")


def extract_items(pdf_path: Path) -> list[Item]:
    items, page_count = read_items(pdf_path)
    return filter_items(items, page_count)
```

Note `Image` uses `eq=False` (identity equality) so large byte payloads are never compared; tests compare identity (`imgs == [content]` works because it is the same object).

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/parser/test_extract.py -v`
Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add exam_sim/parser/extract.py tests/parser/helpers.py tests/parser/conftest.py tests/parser/test_extract.py
git commit -m "feat(parser): PyMuPDF item extraction with watermark/footer filters"
```

---

### Task 4: Question block state machine

**Files:**
- Create: `exam_sim/parser/blocks.py`
- Test: `tests/parser/test_blocks.py`

**Interfaces:**
- Consumes: `Line`, `Image`, `Item`, `QUESTION_HEADER` from `extract.py`; `Vote` from `model.py`.
- Produces: `RawOption(letter: str, parts: list[Item] = [], most_voted: bool = False)`, `RawQuestion(number: int, page: int, topic: str | None = None, stem_parts: list[Item] = [], options: list[RawOption] = [], pdf_answer: list[str] | None = None, votes: list[Vote] = [], stray: list[Item] = [])`, `parse_questions(items) -> list[RawQuestion]`, `join_lines(lines: list[str]) -> str`.

- [ ] **Step 1: Write the failing tests**

`tests/parser/test_blocks.py`:
```python
from exam_sim.parser.blocks import join_lines, parse_questions
from exam_sim.parser.extract import Line
from tests.parser.helpers import image, lines


def q(*texts):
    return parse_questions(lines(*texts))


def test_join_lines_wraps_with_spaces_and_keeps_numbered_steps():
    assert join_lines(["You need to", "do X.", "1. First", "step continues", "2. Second"]) == \
        "You need to do X.\n1. First step continues\n2. Second"
    assert join_lines(["  ", "a", ""]) == "a"


def test_single_question_basic_shape():
    [raw] = q("Question #1", "Topic 1", "Stem line one", "continues here.",
              "A. Threading", "B. Serialization", "C. Dropout", "Most Voted", "D. Reduction",
              "Correct Answer: C", "Community vote distribution", "C (100%)")
    assert raw.number == 1 and raw.topic == "1" and raw.page == 1
    assert [l.text for l in raw.stem_parts] == ["Stem line one", "continues here."]
    assert [o.letter for o in raw.options] == ["A", "B", "C", "D"]
    assert [o.most_voted for o in raw.options] == [False, False, True, False]
    assert [l.text for l in raw.options[2].parts] == ["Dropout"]
    assert raw.pdf_answer == ["C"]
    assert [(v.letters, v.pct) for v in raw.votes] == [(["C"], 100)]
    assert raw.stray == []


def test_out_of_sequence_letter_is_continuation_text():
    [raw] = q("Question #2", "Stem", "A. First", "B. Second mentions", "D. not an option yet",
              "C. Third", "D. Fourth", "Correct Answer: A")
    assert [o.letter for o in raw.options] == ["A", "B", "C", "D"]
    assert [l.text for l in raw.options[1].parts] == ["Second mentions", "D. not an option yet"]


def test_multi_answer_and_multiple_most_voted():
    [raw] = q("Question #10", "Stem (Choose three)", "A. a", "B. b", "Most Voted", "C. c", "D. d",
              "Most Voted", "E. e", "Most Voted", "F. f", "Correct Answer: BDE",
              "Community vote distribution", "BDE (90%)", "BCD (10%)")
    assert raw.pdf_answer == ["B", "D", "E"]
    assert [o.letter for o in raw.options if o.most_voted] == ["B", "D", "E"]
    assert [(v.letters, v.pct) for v in raw.votes] == [(["B", "D", "E"], 90), (["B", "C", "D"], 10)]


def test_inline_most_voted_suffix():
    [raw] = q("Question #3", "Stem", "A. x Most Voted", "B. y", "wrapped Most Voted", "Correct Answer: A")
    assert raw.options[0].most_voted and [l.text for l in raw.options[0].parts] == ["x"]
    assert raw.options[1].most_voted and [l.text for l in raw.options[1].parts] == ["y", "wrapped"]


def test_images_attach_to_stem_or_open_option():
    img1, img2 = image(page=1), image(page=1)
    items = lines("Question #9", "Topic 1", "Error:") + [img1] + lines("Which?", "A.") + [img2] + \
        lines("B. text", "Correct Answer: A")
    [raw] = parse_questions(items)
    assert raw.stem_parts == [Line("Error:", 1), img1, Line("Which?", 1)]
    assert raw.options[0].parts == [img2]
    assert [l.text for l in raw.options[1].parts] == ["text"]


def test_image_after_answer_is_stray():
    img = image()
    [raw] = parse_questions(lines("Question #4", "Stem", "A. a", "Correct Answer: A") + [img])
    assert raw.stray == [img]


def test_no_vote_section_and_stray_lines():
    [raw] = q("Question #321", "Stem", "A. a", "B. b", "Correct Answer: B", "Some unexpected line")
    assert raw.votes == [] and [s.text for s in raw.stray] == ["Some unexpected line"]


def test_votes_continue_across_page_break_and_multiple_questions():
    items = lines("Question #243", "Stem", "A.", "B.", "Correct Answer: C", "Community vote distribution", page=201) + \
        lines("C (52%)", "A (48%)", "Question #244", "Stem2", "A. a", "Correct Answer: A", page=202)
    raws = parse_questions(items)
    assert [r.number for r in raws] == [243, 244]
    assert [(v.letters, v.pct) for v in raws[0].votes] == [(["C"], 52), (["A"], 48)]
    assert raws[1].page == 202


def test_several_vote_entries_on_one_line():
    [raw] = q("Question #18", "Stem", "A. a", "B. b", "Correct Answer: BDE", "Community vote distribution",
              "BDE (89%)", "BCE (5%)CDE (3%)ACD (3%)", "BC (7%) BE (3%)")
    assert [("".join(v.letters), v.pct) for v in raw.votes] == \
        [("BDE", 89), ("BCE", 5), ("CDE", 3), ("ACD", 3), ("BC", 7), ("BE", 3)]
    assert raw.stray == []


def test_option_text_with_numbered_steps_stays_in_option():
    [raw] = q("Question #5", "Stem", "A. 1. Export metadata.", "2. Implement metastore.", "B. 1. Use Dataplex.",
              "Correct Answer: B")
    assert [l.text for l in raw.options[0].parts] == ["1. Export metadata.", "2. Implement metastore."]
    assert [l.text for l in raw.options[1].parts] == ["1. Use Dataplex."]


def test_topic_is_optional_and_lines_before_first_question_are_ignored():
    [raw] = q("junk", "Question #7", "Stem only", "A. a", "Correct Answer: A")
    assert raw.topic is None and [l.text for l in raw.stem_parts] == ["Stem only"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/parser/test_blocks.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'exam_sim.parser.blocks'`

- [ ] **Step 3: Write the state machine**

`exam_sim/parser/blocks.py`:
```python
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


def _letters(s: str) -> list[str]:
    return sorted(set(s))


def parse_questions(items: list[Item]) -> list[RawQuestion]:
    questions: list[RawQuestion] = []
    cur: RawQuestion | None = None
    state = "stem"          # stem | options | answer | votes
    expected = "A"          # next option letter we will accept

    for it in items:
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
                cur.pdf_answer = _letters(m.group(1))
                state = "answer"
                continue
            m = OPTION_RE.match(text)
            if m and m.group(1) == expected:
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
                cur.votes.append(Vote(letters=_letters(m.group(1)), pct=int(m.group(2))))
        else:
            cur.stray.append(it)

    if cur is not None:
        questions.append(cur)
    return questions
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/parser/test_blocks.py -v`
Expected: 12 PASS

- [ ] **Step 5: Commit**

```bash
git add exam_sim/parser/blocks.py tests/parser/test_blocks.py
git commit -m "feat(parser): question block state machine"
```

---

### Task 5: Answer-key rule

**Files:**
- Create: `exam_sim/parser/key.py`
- Test: `tests/parser/test_key.py`

**Interfaces:**
- Consumes: `Vote` from `model.py`.
- Produces: `KeyResult(answer: list[str], source: str, disputed: bool)`, `resolve_key(pdf_answer: list[str], votes: list[Vote]) -> KeyResult`, constants `SOURCE_PDF = "pdf"`, `SOURCE_VOTES = "votes"`, `SOURCE_TIEBREAK = "votes_tiebreak_pdf"`, `SOURCE_TIE_FIRST = "votes_tie_first"`.

- [ ] **Step 1: Write the failing test**

`tests/parser/test_key.py`:
```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/parser/test_key.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'exam_sim.parser.key'`

- [ ] **Step 3: Write the rule**

`exam_sim/parser/key.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/parser/test_key.py -v`
Expected: 11 PASS

- [ ] **Step 5: Commit**

```bash
git add exam_sim/parser/key.py tests/parser/test_key.py
git commit -m "feat(parser): community-vote answer key rule"
```

---

### Task 6: Image writer and question assembly

**Files:**
- Create: `exam_sim/parser/images.py`, `exam_sim/parser/assemble.py`
- Test: `tests/parser/test_assemble.py`

**Interfaces:**
- Consumes: `RawQuestion`, `RawOption`, `join_lines` (Task 4); `resolve_key` (Task 5); `to_png`, `Image`, `Line`, `Item` (Task 3); model types (Task 2).
- Produces: `ImageWriter(bank_dir: Path)` with `.images_dir`, `.written: int`, `.warnings: list[str]`, `.reset_dir()`, `.writer_for(number) -> Callable[[Image], Block]`; `MISSING_IMAGE_TEXT = "[image missing]"`; `assemble_blocks(parts: list[Item], write_image) -> list[Block]`; `build_question(raw: RawQuestion, write_image) -> Question`.

- [ ] **Step 1: Write the failing tests**

`tests/parser/test_assemble.py`:
```python
from exam_sim.parser.assemble import assemble_blocks, build_question
from exam_sim.parser.blocks import RawOption, RawQuestion
from exam_sim.parser.extract import Image
from exam_sim.parser.images import MISSING_IMAGE_TEXT, ImageWriter
from exam_sim.parser.model import ImageBlock, TextBlock, Vote
from tests.parser.helpers import image, lines


def test_assemble_blocks_joins_text_and_places_images(tmp_path):
    writer = ImageWriter(tmp_path / "bank")
    img = image(50, 40)
    blocks = assemble_blocks(lines("Error", "follows:") + [img] + lines("Which?"), writer.writer_for(9))
    assert blocks == [TextBlock(text="Error follows:"), ImageBlock(src="images/q009_1.png", w=50, h=40), TextBlock(text="Which?")]
    assert (tmp_path / "bank" / "images" / "q009_1.png").is_file()


def test_assemble_blocks_drops_empty_text():
    assert assemble_blocks(lines("  ", ""), lambda img: None) == []


def test_image_writer_numbers_images_per_question(tmp_path):
    writer = ImageWriter(tmp_path / "b")
    write = writer.writer_for(243)
    assert [write(image()).src for _ in range(3)] == ["images/q243_1.png", "images/q243_2.png", "images/q243_3.png"]
    assert writer.writer_for(7)(image()).src == "images/q007_1.png"
    assert writer.written == 4


def test_image_writer_converts_jpeg_to_png(tmp_path):
    writer = ImageWriter(tmp_path / "b")
    block = writer.writer_for(1)(image(fmt="jpeg"))
    assert block.src.endswith(".png")
    assert (tmp_path / "b" / block.src).read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_image_writer_falls_back_to_placeholder_on_bad_bytes(tmp_path):
    writer = ImageWriter(tmp_path / "b")
    bad = Image(data=b"not an image", ext="jpeg", width=10, height=10, page=1)
    assert writer.writer_for(1)(bad) == TextBlock(text=MISSING_IMAGE_TEXT)
    assert writer.warnings and "Q1" in writer.warnings[0]


def test_reset_dir_clears_stale_images(tmp_path):
    writer = ImageWriter(tmp_path / "b")
    writer.writer_for(1)(image())
    writer.reset_dir()
    assert writer.images_dir.is_dir() and list(writer.images_dir.iterdir()) == []


def test_build_question_resolves_key_and_select_count(tmp_path):
    raw = RawQuestion(number=10, page=1, topic="1", stem_parts=lines("Pick (Choose three)"),
                      options=[RawOption(l, lines(l.lower())) for l in "ABCDEF"],
                      pdf_answer=["B", "D", "E"], votes=[Vote(["B", "D", "E"], 90)])
    q = build_question(raw, ImageWriter(tmp_path).writer_for(10))
    assert q.number == 10 and q.topic == "1"
    assert q.answer == ["B", "D", "E"] and q.select_count == 3
    assert q.answer_source == "votes" and q.disputed is False
    assert q.pdf_answer == ["B", "D", "E"] and q.votes == [Vote(["B", "D", "E"], 90)]
    assert q.stem == [TextBlock(text="Pick (Choose three)")]
    assert [o.letter for o in q.options] == list("ABCDEF") and q.options[0].content == [TextBlock(text="a")]


def test_build_question_without_pdf_answer(tmp_path):
    raw = RawQuestion(number=1, page=1, stem_parts=lines("S"), options=[RawOption("A", lines("a"))])
    q = build_question(raw, ImageWriter(tmp_path).writer_for(1))
    assert q.answer == [] and q.select_count == 0 and q.pdf_answer == [] and q.answer_source == "pdf"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/parser/test_assemble.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'exam_sim.parser.assemble'`

- [ ] **Step 3: Write images.py and assemble.py**

`exam_sim/parser/images.py`:
```python
"""Writes question images to <bank_dir>/images as numbered PNGs and returns content blocks."""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Callable

from .extract import Image, to_png
from .model import Block, ImageBlock, TextBlock

MISSING_IMAGE_TEXT = "[image missing]"


class ImageWriter:
    def __init__(self, bank_dir: Path):
        self.images_dir = bank_dir / "images"
        self.counts: dict[int, int] = {}
        self.written = 0
        self.warnings: list[str] = []

    def reset_dir(self) -> None:
        shutil.rmtree(self.images_dir, ignore_errors=True)
        self.images_dir.mkdir(parents=True, exist_ok=True)

    def writer_for(self, number: int) -> Callable[[Image], Block]:
        def write(img: Image) -> Block:
            k = self.counts.get(number, 0) + 1
            self.counts[number] = k
            name = f"q{number:03d}_{k}.png"
            try:
                data = to_png(img.data, img.ext)
            except Exception as exc:  # any decoder failure → placeholder, never abort the parse
                self.warnings.append(f"Q{number}: image {k} on page {img.page} could not be converted ({exc})")
                return TextBlock(text=MISSING_IMAGE_TEXT)
            self.images_dir.mkdir(parents=True, exist_ok=True)
            (self.images_dir / name).write_bytes(data)
            self.written += 1
            return ImageBlock(src=f"images/{name}", w=img.width, h=img.height)

        return write
```

`exam_sim/parser/assemble.py`:
```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/parser/test_assemble.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add exam_sim/parser/images.py exam_sim/parser/assemble.py tests/parser/test_assemble.py
git commit -m "feat(parser): image writer and question assembly"
```

---

### Task 7: Validation report

**Files:**
- Create: `exam_sim/parser/report.py`
- Test: `tests/parser/test_report.py`

**Interfaces:**
- Consumes: `Question`, `TextBlock`, `ImageBlock` (Task 2); `RawQuestion`, `RawOption` (Task 4); `Line` (Task 3).
- Produces: `Report` dataclass (fields below) with `.errors() -> list[str]`; `build_report(questions, raws, warnings=None) -> Report`; `format_report(report) -> str`.

- [ ] **Step 1: Write the failing test**

`tests/parser/test_report.py`:
```python
from exam_sim.parser.blocks import RawOption, RawQuestion
from exam_sim.parser.extract import Line
from exam_sim.parser.model import ImageBlock, Option, Question, TextBlock, Vote
from exam_sim.parser.report import build_report, format_report


def mk(number, options="ABCD", answer=("A",), pdf=None, votes=(), stem="Stem?", disputed=False, source="votes",
       stem_blocks=None):
    return Question(number=number, topic="1",
                    stem=stem_blocks or [TextBlock(text=stem)],
                    options=[Option(letter=l, content=[TextBlock(text=l)]) for l in options],
                    answer=list(answer), select_count=len(answer),
                    pdf_answer=list(pdf if pdf is not None else answer),
                    votes=list(votes), answer_source=source, disputed=disputed)


def test_report_counts_and_errors():
    qs = [mk(1), mk(2, options="", answer=()), mk(4, answer=("Z",)), mk(4),
          mk(5, stem="Pick two (Choose two)", answer=("A",)), mk(6, options="ABCDE", answer=("A", "B"))]
    r = build_report(qs, [])
    assert r.question_count == 6 and (r.first_number, r.last_number) == (1, 6)
    assert r.missing_numbers == [3] and r.duplicate_numbers == [4]
    assert r.option_histogram == {0: 1, 4: 4, 5: 1}
    assert r.no_options == [2] and r.no_answer == [2] and r.answer_not_in_options == [4]
    assert r.choose_hint_mismatch == [(5, 2, 1)]
    assert r.no_votes == 6
    assert len(r.errors()) == 3
    text = format_report(r)
    assert "questions: 6 (#1–#6)" in text and "missing numbers: [3]" in text and "errors:" in text


def test_report_images_disputed_most_voted_and_stray():
    raw = RawQuestion(number=7, page=3, options=[RawOption("A", most_voted=True), RawOption("B")],
                      stray=[Line("odd", 3)])
    q = mk(7, answer=("B",), pdf=("A",), disputed=True, votes=[Vote(["B"], 100)],
           stem_blocks=[TextBlock(text="S"), ImageBlock(src="images/q007_1.png", w=1, h=1)])
    r = build_report([q], [raw], warnings=["Q7: image 2 could not be converted"])
    assert r.image_blocks == 1 and r.no_votes == 0
    assert r.disputed == [(7, "B", "A", "votes")]
    assert r.most_voted_mismatch == [(7, "A", "B")]
    assert r.stray == [(7, 3, "odd")]
    assert r.errors() == []
    text = format_report(r)
    assert "Q7 key=B pdf=A [votes]" in text and "warning: Q7: image 2" in text and "errors: none" in text


def test_empty_report():
    r = build_report([], [])
    assert r.question_count == 0 and r.errors() == []
    assert "questions: 0" in format_report(r)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/parser/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'exam_sim.parser.report'`

- [ ] **Step 3: Write the report module**

`exam_sim/parser/report.py`:
```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/parser/test_report.py -v`
Expected: 3 PASS

- [ ] **Step 5: Commit**

```bash
git add exam_sim/parser/report.py tests/parser/test_report.py
git commit -m "feat(parser): validation report"
```

---

### Task 8: `parse-pdf` CLI + real-PDF integration test + generate the first bank

**Files:**
- Create: `exam_sim/parser/cli.py`
- Test: `tests/parser/test_real_pdf.py`

**Interfaces:**
- Consumes: everything from Tasks 2–7.
- Produces: `parse_pdf(pdf_path: Path, out_dir: Path, bank_id: str, title: str) -> tuple[dict, Report]`, `slugify(name) -> str`, `main(argv: list[str] | None = None) -> int`; console script `parse-pdf PDF [--id ID] [--title TITLE] [--out DIR] [--strict]`.
- Output on disk: `<out>/<id>/questions.json`, `<out>/<id>/images/q###_k.png`.

- [ ] **Step 1: Write the failing integration test**

`tests/parser/test_real_pdf.py`:
```python
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
    assert set(report.option_histogram) == {4, 5, 6} and sum(report.option_histogram.values()) == 349
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


def test_cli_writes_bank_and_reports(real_pdf, tmp_path, capsys):
    code = main([str(real_pdf), "--id", "pde-cli", "--title", "T", "--out", str(tmp_path), "--strict"])
    out = capsys.readouterr().out
    assert code == 0, out
    assert "questions: 349" in out and "errors: none" in out
    doc = json.loads((tmp_path / "pde-cli" / "questions.json").read_text(encoding="utf-8"))
    assert doc["bank"] == {**doc["bank"], "id": "pde-cli", "title": "T", "source_pdf": real_pdf.name, "question_count": 349}
    assert (tmp_path / "pde-cli" / "images").is_dir()


def test_slugify():
    assert slugify("349题_PROFESSIONAL-DATA-ENGINEER_202610_without_discussion_en") == "professional-data-engineer-202610-without-discussion-en"
    assert slugify("###") == "bank"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/parser/test_real_pdf.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'exam_sim.parser.cli'` (or SKIP if the PDF is missing — it is present at `source/pde_349.pdf`).

- [ ] **Step 3: Write the CLI**

`exam_sim/parser/cli.py`:
```python
"""parse-pdf: ExamTopics-style PDF → banks/<id>/questions.json (+ images/)."""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .assemble import build_question
from .blocks import parse_questions
from .extract import extract_items
from .images import ImageWriter
from .model import BankMeta, bank_to_dict
from .report import Report, build_report, format_report


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:64] or "bank"


def parse_pdf(pdf_path: Path, out_dir: Path, bank_id: str, title: str) -> tuple[dict, Report]:
    bank_dir = out_dir / bank_id
    bank_dir.mkdir(parents=True, exist_ok=True)
    writer = ImageWriter(bank_dir)
    writer.reset_dir()
    raws = parse_questions(extract_items(pdf_path))
    questions = [build_question(raw, writer.writer_for(raw.number)) for raw in raws]
    meta = BankMeta(id=bank_id, title=title, source_pdf=pdf_path.name,
                    parsed_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    question_count=len(questions))
    doc = bank_to_dict(meta, questions)
    (bank_dir / "questions.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    return doc, build_report(questions, raws, writer.warnings)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="parse-pdf", description=__doc__)
    ap.add_argument("pdf", type=Path)
    ap.add_argument("--id", dest="bank_id", help="bank id (default: slug of the PDF file name)")
    ap.add_argument("--title", help="bank title (default: PDF file name)")
    ap.add_argument("--out", type=Path, default=Path("banks"), help="output root (default: banks/)")
    ap.add_argument("--strict", action="store_true", help="exit 1 if the report contains errors")
    args = ap.parse_args(argv)
    if not args.pdf.is_file():
        ap.error(f"PDF not found: {args.pdf}")
    bank_id = args.bank_id or slugify(args.pdf.stem)
    title = args.title or args.pdf.stem
    doc, report = parse_pdf(args.pdf, args.out, bank_id, title)
    print(f"wrote {args.out / bank_id / 'questions.json'} ({doc['bank']['question_count']} questions)")
    print(format_report(report))
    if args.strict and report.errors():
        print("strict mode: errors present", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the integration test**

Run: `uv run pytest tests/parser/test_real_pdf.py -v`
Expected: 7 PASS. If an assertion about the real PDF fails, inspect with `uv run parse-pdf source/pde_349.pdf --id debug --out scratch/banks` and read the report; fix the parser (not the test) unless the test encodes a wrong assumption about the PDF — document any such change in the commit message.

- [ ] **Step 5: Run the whole suite, then generate the real bank**

Run: `uv run pytest`
Expected: all parser tests pass (model 1, extract 6, blocks 12, key 11, assemble 8, report 3, real_pdf 7, smoke 1).

Run: `uv run parse-pdf source/pde_349.pdf --id pde-2026-10 --title "Professional Data Engineer (2026-10)" --strict`
Expected: exit 0; `banks/pde-2026-10/questions.json` and `banks/pde-2026-10/images/` exist; report shows `questions: 349`, `errors: none`, `disputed (9)` listing Q109, 216, 217, 270, 320, 328, 340, 342, 347, and `questions without vote data: 13`.

Then pin the option histogram: copy the exact `options per question: {...}` dict from the report into `test_counts_and_numbering` as `assert report.option_histogram == {...}` (replacing the `set(...) == {4, 5, 6}` line) and re-run the test.

- [ ] **Step 6: Commit**

```bash
git add exam_sim/parser/cli.py tests/parser/test_real_pdf.py
git commit -m "feat(parser): parse-pdf CLI with strict validation; real-PDF integration test"
```

---

### Task 9: Storage — bank discovery and atomic progress files

**Files:**
- Create: `exam_sim/server/storage.py`, `tests/server/conftest.py`
- Test: `tests/server/test_storage.py`

**Interfaces:**
- Produces: `BANK_ID_RE`, `PROGRESS_VERSION = 1`, exceptions `InvalidBankId(ValueError)`, `BankNotFound(KeyError)`; `default_progress(bank_id) -> dict`; `utc_now() -> str`; `atomic_write_json(path, doc)`; class `Storage(banks_dir, data_dir)` with `.banks_dir`, `.progress_dir`, `check_id(id) -> str`, `bank_dir(id) -> Path`, `bank_file(id) -> Path`, `list_banks() -> list[dict]`, `load_bank(id) -> dict`, `image_path(id, filename) -> Path`, `progress_path(id) -> Path`, `load_progress(id) -> dict`, `save_progress(id, doc) -> dict`.
- Test fixtures: `bank_doc` (a one-question bank dict), `dirs` → `(banks, data, web)` temp paths with bank `demo`, image `q001_1.png`, and `web/index.html` containing `ok`.

- [ ] **Step 1: Write fixtures and the failing tests**

`tests/server/conftest.py`:
```python
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
```

`tests/server/test_storage.py`:
```python
import json

import pytest

from exam_sim.server.storage import BankNotFound, InvalidBankId, Storage, default_progress


def test_list_banks_sorted_by_title_and_skips_broken(dirs):
    banks, data, _ = dirs
    (banks / "zzz").mkdir()
    (banks / "zzz" / "questions.json").write_text("{not json")
    (banks / "aaa").mkdir()
    (banks / "aaa" / "questions.json").write_text(json.dumps({"bank": {"id": "aaa", "title": "Alpha", "question_count": 2}}))
    s = Storage(banks, data)
    assert s.list_banks() == [{"id": "aaa", "title": "Alpha", "question_count": 2},
                              {"id": "demo", "title": "Demo Bank", "question_count": 1}]


def test_list_banks_empty_when_dir_missing(tmp_path):
    assert Storage(tmp_path / "none", tmp_path / "d").list_banks() == []


def test_bank_ids_and_missing_banks(dirs):
    s = Storage(*dirs[:2])
    for bad in ("Demo", "", "a b", "-x", "x" * 65, "a/b"):
        with pytest.raises(InvalidBankId):
            s.load_bank(bad)
    with pytest.raises(BankNotFound):
        s.load_bank("ghost")
    assert s.load_bank("demo")["bank"]["id"] == "demo"


def test_image_path(dirs):
    s = Storage(*dirs[:2])
    assert s.image_path("demo", "q001_1.png").is_file()
    for bad in ("missing.png", "../questions.json", "", "a/b.png"):
        with pytest.raises(BankNotFound):
            s.image_path("demo", bad)


def test_progress_default_save_load(dirs):
    s = Storage(*dirs[:2])
    assert s.load_progress("demo") == default_progress("demo")
    doc = default_progress("demo")
    doc["exams"] = [{"id": "x"}]
    saved = s.save_progress("demo", doc)
    assert saved["updated_at"] and saved["exams"] == [{"id": "x"}]
    assert s.load_progress("demo") == saved
    assert not list(s.progress_dir.glob("*.tmp"))


def test_save_validates(dirs):
    s = Storage(*dirs[:2])
    with pytest.raises(ValueError):
        s.save_progress("demo", {"version": 1, "bank_id": "nope"})
    with pytest.raises(ValueError):
        s.save_progress("demo", {"version": 0, "bank_id": "demo"})
    with pytest.raises(ValueError):
        s.save_progress("demo", ["not", "a", "dict"])
    with pytest.raises(BankNotFound):
        s.save_progress("ghost", default_progress("ghost"))
    with pytest.raises(BankNotFound):
        s.load_progress("ghost")


def test_corrupt_progress_is_backed_up_not_overwritten(dirs):
    s = Storage(*dirs[:2])
    path = s.progress_path("demo")
    path.parent.mkdir(parents=True)
    path.write_text("[1, 2")
    assert s.load_progress("demo") == default_progress("demo")
    assert not path.exists()
    [backup] = list(path.parent.glob("demo.json.corrupt-*"))
    assert backup.read_text() == "[1, 2"


def test_non_object_progress_counts_as_corrupt(dirs):
    s = Storage(*dirs[:2])
    path = s.progress_path("demo")
    path.parent.mkdir(parents=True)
    path.write_text("[]")
    assert s.load_progress("demo") == default_progress("demo")
    assert list(path.parent.glob("demo.json.corrupt-*"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/server/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'exam_sim.server.storage'`

- [ ] **Step 3: Write storage.py**

`exam_sim/server/storage.py`:
```python
"""Bank discovery and atomic progress persistence (data/progress/<bank_id>.json)."""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)

BANK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
IMAGE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")
PROGRESS_VERSION = 1


class InvalidBankId(ValueError):
    pass


class BankNotFound(KeyError):
    pass


def default_progress(bank_id: str) -> dict:
    return {"version": PROGRESS_VERSION, "bank_id": bank_id, "updated_at": None,
            "questions": {}, "exams": [], "active_exam": None, "practice": None}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def atomic_write_json(path: Path, doc: dict) -> None:
    """Write to <name>.tmp in the same directory, fsync, then rename over the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(doc, f, ensure_ascii=False, indent=1)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise


class Storage:
    def __init__(self, banks_dir: Path, data_dir: Path):
        self.banks_dir = Path(banks_dir).resolve()
        self.progress_dir = (Path(data_dir) / "progress").resolve()

    # --- banks ---
    def check_id(self, bank_id: str) -> str:
        if not BANK_ID_RE.match(bank_id or ""):
            raise InvalidBankId(bank_id)
        return bank_id

    def bank_dir(self, bank_id: str) -> Path:
        path = (self.banks_dir / self.check_id(bank_id)).resolve()
        if path.parent != self.banks_dir:
            raise InvalidBankId(bank_id)
        return path

    def bank_file(self, bank_id: str) -> Path:
        path = self.bank_dir(bank_id) / "questions.json"
        if not path.is_file():
            raise BankNotFound(bank_id)
        return path

    def list_banks(self) -> list[dict]:
        banks = []
        if self.banks_dir.is_dir():
            for qfile in sorted(self.banks_dir.glob("*/questions.json")):
                try:
                    meta = json.loads(qfile.read_text(encoding="utf-8"))["bank"]
                    banks.append({"id": meta["id"], "title": meta["title"], "question_count": meta["question_count"]})
                except (OSError, ValueError, KeyError, TypeError) as exc:
                    log.warning("skipping unreadable bank %s: %s", qfile, exc)
        return sorted(banks, key=lambda b: str(b["title"]).lower())

    def load_bank(self, bank_id: str) -> dict:
        return json.loads(self.bank_file(bank_id).read_text(encoding="utf-8"))

    def image_path(self, bank_id: str, filename: str) -> Path:
        if not IMAGE_NAME_RE.match(filename or ""):
            raise BankNotFound(filename)
        path = self.bank_dir(bank_id) / "images" / filename
        if not path.is_file():
            raise BankNotFound(filename)
        return path

    # --- progress ---
    def progress_path(self, bank_id: str) -> Path:
        return self.progress_dir / f"{self.check_id(bank_id)}.json"

    def load_progress(self, bank_id: str) -> dict:
        self.bank_file(bank_id)                      # unknown bank → BankNotFound
        path = self.progress_path(bank_id)
        if not path.exists():
            return default_progress(bank_id)
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(doc, dict):
                raise ValueError("progress root is not an object")
            return doc
        except (ValueError, UnicodeDecodeError) as exc:
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            backup = path.with_name(f"{path.name}.corrupt-{stamp}")
            path.rename(backup)
            log.warning("corrupt progress for %s moved to %s (%s)", bank_id, backup.name, exc)
            return default_progress(bank_id)

    def save_progress(self, bank_id: str, doc: dict) -> dict:
        self.bank_file(bank_id)
        if not isinstance(doc, dict) or doc.get("version") != PROGRESS_VERSION or doc.get("bank_id") != bank_id:
            raise ValueError("progress document must be an object with version 1 and a matching bank_id")
        saved = dict(doc)
        saved["updated_at"] = utc_now()
        atomic_write_json(self.progress_path(bank_id), saved)
        return saved
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/server/test_storage.py -v`
Expected: 8 PASS

- [ ] **Step 5: Commit**

```bash
git add exam_sim/server/storage.py tests/server/conftest.py tests/server/test_storage.py
git commit -m "feat(server): bank discovery and atomic progress storage"
```

---

### Task 10: FastAPI app + `serve` CLI

**Files:**
- Create: `exam_sim/server/app.py`, `exam_sim/server/cli.py`
- Test: `tests/server/test_api.py`

**Interfaces:**
- Consumes: `Storage`, `InvalidBankId`, `BankNotFound` (Task 9).
- Produces: `create_app(banks_dir: Path, data_dir: Path, web_dir: Path = WEB_DIR) -> FastAPI`, `WEB_DIR` (repo `web/`), `MAX_PROGRESS_BYTES = 20 MiB`; routes `GET /api/banks`, `GET /api/banks/{id}`, `GET|PUT /api/banks/{id}/progress`, `GET /banks/{id}/images/{file}`, static `/`; console script `serve [--host 127.0.0.1] [--port 8000] [--banks banks] [--data data] [--web <repo>/web] [--no-browser]`.

- [ ] **Step 1: Write the failing tests**

`tests/server/test_api.py`:
```python
import pytest
from fastapi.testclient import TestClient

from exam_sim.server.app import MAX_PROGRESS_BYTES, create_app


@pytest.fixture
def client(dirs):
    banks, data, web = dirs
    return TestClient(create_app(banks, data, web))


def test_list_and_get_bank(client):
    assert client.get("/api/banks").json() == [{"id": "demo", "title": "Demo Bank", "question_count": 1}]
    assert client.get("/api/banks/demo").json()["bank"]["title"] == "Demo Bank"


def test_unknown_and_invalid_bank(client):
    assert client.get("/api/banks/nope").status_code == 404
    assert client.get("/api/banks/Not_Valid").status_code == 400
    assert client.get("/api/banks/nope/progress").status_code == 404
    assert client.put("/api/banks/nope/progress", json={"version": 1, "bank_id": "nope"}).status_code == 404


def test_progress_roundtrip(client, dirs):
    _, data, _ = dirs
    doc = client.get("/api/banks/demo/progress").json()
    assert doc == {"version": 1, "bank_id": "demo", "updated_at": None, "questions": {}, "exams": [],
                   "active_exam": None, "practice": None}
    doc["questions"]["1"] = {"attempts": 1, "correct": 1, "wrong": 0, "last_result": "correct",
                             "last_answer": ["A"], "last_at": "2026-01-01T00:00:00Z", "in_mistakes": False}
    res = client.put("/api/banks/demo/progress", json=doc)
    assert res.status_code == 200 and res.json()["ok"] is True and res.json()["updated_at"]
    again = client.get("/api/banks/demo/progress").json()
    assert again["questions"]["1"]["attempts"] == 1 and again["updated_at"] == res.json()["updated_at"]
    assert not list((data / "progress").glob("*.tmp"))


def test_put_rejects_bad_documents(client):
    assert client.put("/api/banks/demo/progress", json={"version": 2, "bank_id": "demo"}).status_code == 400
    assert client.put("/api/banks/demo/progress", json={"version": 1, "bank_id": "other"}).status_code == 400
    assert client.put("/api/banks/demo/progress", json=[1, 2]).status_code == 400
    r = client.put("/api/banks/demo/progress", content=b"not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 400


def test_put_rejects_oversize_body(client):
    big = b'{"version":1,"bank_id":"demo","pad":"' + b"x" * MAX_PROGRESS_BYTES + b'"}'
    r = client.put("/api/banks/demo/progress", content=big, headers={"Content-Type": "application/json"})
    assert r.status_code == 413


def test_corrupt_progress_is_backed_up(client, dirs):
    _, data, _ = dirs
    path = data / "progress" / "demo.json"
    path.parent.mkdir(parents=True)
    path.write_text("{broken")
    assert client.get("/api/banks/demo/progress").json()["questions"] == {}
    assert not path.exists() and list(path.parent.glob("demo.json.corrupt-*"))


def test_images_and_static(client):
    assert client.get("/banks/demo/images/q001_1.png").status_code == 200
    assert client.get("/banks/demo/images/missing.png").status_code == 404
    assert client.get("/banks/demo/images/..%2Fquestions.json").status_code in (400, 404)
    r = client.get("/")
    assert r.status_code == 200 and "ok" in r.text


def test_app_without_web_dir_still_serves_api(dirs, tmp_path):
    banks, data, _ = dirs
    c = TestClient(create_app(banks, data, tmp_path / "nowhere"))
    assert c.get("/api/banks").status_code == 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/server/test_api.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'exam_sim.server.app'`

- [ ] **Step 3: Write app.py and cli.py**

`exam_sim/server/app.py`:
```python
"""FastAPI application: bank + progress API, bank images, static web UI."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .storage import BankNotFound, InvalidBankId, Storage

MAX_PROGRESS_BYTES = 20 * 1024 * 1024
WEB_DIR = Path(__file__).resolve().parents[2] / "web"


def create_app(banks_dir: Path, data_dir: Path, web_dir: Path = WEB_DIR) -> FastAPI:
    storage = Storage(banks_dir, data_dir)
    app = FastAPI(title="Exam Sim", docs_url=None, redoc_url=None)
    app.state.storage = storage

    @app.exception_handler(InvalidBankId)
    async def _invalid_id(_: Request, exc: InvalidBankId):
        return JSONResponse({"detail": f"invalid bank id: {exc}"}, status_code=400)

    @app.exception_handler(BankNotFound)
    async def _not_found(_: Request, exc: BankNotFound):
        return JSONResponse({"detail": f"not found: {exc}"}, status_code=404)

    @app.get("/api/banks")
    async def list_banks():
        return storage.list_banks()

    @app.get("/api/banks/{bank_id}")
    async def get_bank(bank_id: str):
        return storage.load_bank(bank_id)

    @app.get("/api/banks/{bank_id}/progress")
    async def get_progress(bank_id: str):
        return storage.load_progress(bank_id)

    @app.put("/api/banks/{bank_id}/progress")
    async def put_progress(bank_id: str, request: Request):
        declared = request.headers.get("content-length")
        if declared and declared.isdigit() and int(declared) > MAX_PROGRESS_BYTES:
            return JSONResponse({"detail": "progress document too large"}, status_code=413)
        body = await request.body()
        if len(body) > MAX_PROGRESS_BYTES:
            return JSONResponse({"detail": "progress document too large"}, status_code=413)
        try:
            doc = json.loads(body)
            saved = storage.save_progress(bank_id, doc)
        except ValueError as exc:                     # bad JSON or failed validation
            return JSONResponse({"detail": str(exc)}, status_code=400)
        return {"ok": True, "updated_at": saved["updated_at"]}

    @app.get("/banks/{bank_id}/images/{filename}")
    async def bank_image(bank_id: str, filename: str):
        return FileResponse(storage.image_path(bank_id, filename))

    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=web_dir, html=True), name="web")
    return app
```

Note: `InvalidBankId` subclasses `ValueError`, but FastAPI's exception handlers are matched by the most specific registered class, and the `except ValueError` in `put_progress` sits *inside* the handler — `storage.save_progress` validates the bank id first (`bank_file`), which raises `InvalidBankId`; that is caught by the `except ValueError` and returned as 400, which is the intended status anyway.

`exam_sim/server/cli.py`:
```python
"""serve: run the local Exam Sim server and open the browser."""
from __future__ import annotations

import argparse
import threading
import time
import webbrowser
from pathlib import Path

import uvicorn

from .app import WEB_DIR, create_app


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="serve", description=__doc__)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--banks", type=Path, default=Path("banks"))
    ap.add_argument("--data", type=Path, default=Path("data"))
    ap.add_argument("--web", type=Path, default=WEB_DIR)
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args(argv)

    app = create_app(args.banks, args.data, args.web)
    server = uvicorn.Server(uvicorn.Config(app, host=args.host, port=args.port, log_level="info"))
    url = f"http://{args.host}:{args.port}/"
    if not args.no_browser:
        def _open_when_ready() -> None:
            while not server.started:
                time.sleep(0.1)
            webbrowser.open(url)
        threading.Thread(target=_open_when_ready, daemon=True).start()
    print(f"Exam Sim: {url}  (banks={args.banks}, data={args.data}, web={args.web})")
    server.run()
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/server -v`
Expected: 16 PASS (8 storage + 8 api)

- [ ] **Step 5: Smoke-run the real server against the generated bank**

Run (in a persistent terminal): `uv run serve --no-browser --port 8010`
Then in another shell:
```bash
curl -s localhost:8010/api/banks
curl -s localhost:8010/api/banks/pde-2026-10 | head -c 300
curl -s localhost:8010/api/banks/pde-2026-10/progress
curl -s -o /dev/null -w "%{http_code}\n" localhost:8010/banks/pde-2026-10/images/q009_1.png
```
Expected: bank list with `pde-2026-10`; JSON starting with `{"schema_version": 1, ...`; default progress; `200`. (`GET /` returns 404 until Task 13 creates `web/index.html` — fine.) Stop the server (Ctrl-C / kill).

- [ ] **Step 6: Commit**

```bash
git add exam_sim/server/app.py exam_sim/server/cli.py tests/server/test_api.py
git commit -m "feat(server): FastAPI bank/progress API and serve CLI"
```

---

### Task 11: Pure web modules — config, grading, shuffle, timer

**Files:**
- Create: `web/js/config.js`, `web/js/grading.js`, `web/js/shuffle.js`, `web/js/timer.js`
- Test: `tests/web/grading.test.js`, `tests/web/shuffle.test.js`, `tests/web/timer.test.js`

**Interfaces:**
- Produces: `PASS_PCT`, `EXAM_DEFAULTS {count, minutes}`, `EXAM_LIMITS {minMinutes, maxMinutes}`, `TIMER_WARN_S`, `SAVE_DEBOUNCE_MS`, `SAVE_RETRY_MIN_MS`, `SAVE_RETRY_MAX_MS`; `isCorrect(answer, picked) -> boolean`, `pct(score, total) -> number`, `scoreExam(items, byNumber) -> {items, score, total, pct}`; `fisherYates(arr, rng?) -> arr`, `sampleWithoutReplacement(arr, n, rng?) -> arr`; `remainingSeconds(startedAtIso, durationS, nowMs?) -> int`, `formatClock(seconds) -> "mm:ss"`.

- [ ] **Step 1: Write the failing tests**

`tests/web/grading.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isCorrect, pct, scoreExam } from '../../web/js/grading.js';

test('single answer: exact match only', () => {
  assert.equal(isCorrect(['C'], ['C']), true);
  assert.equal(isCorrect(['C'], ['B']), false);
  assert.equal(isCorrect(['C'], []), false);
  assert.equal(isCorrect(['C'], ['C', 'B']), false);
  assert.equal(isCorrect([], []), false);
});

test('multi answer: all-or-nothing, order-insensitive', () => {
  assert.equal(isCorrect(['B', 'D', 'E'], ['E', 'B', 'D']), true);
  assert.equal(isCorrect(['B', 'D', 'E'], ['B', 'D']), false);
  assert.equal(isCorrect(['B', 'D', 'E'], ['B', 'D', 'A']), false);
});

test('pct rounds to one decimal and handles zero total', () => {
  assert.equal(pct(1, 3), 33.3);
  assert.equal(pct(41, 50), 82);
  assert.equal(pct(0, 0), 0);
});

test('scoreExam grades items against the bank; unanswered and unknown are wrong', () => {
  const byNumber = new Map([[1, { answer: ['A'] }], [2, { answer: ['B', 'C'] }], [3, { answer: ['D'] }]]);
  const r = scoreExam([
    { number: 1, order: ['B', 'A'], picked: ['A'] },
    { number: 2, order: ['C', 'B', 'A'], picked: ['B'] },
    { number: 3, order: ['A', 'B', 'C', 'D'], picked: [] },
    { number: 99, order: ['A'], picked: ['A'] },
  ], byNumber);
  assert.deepEqual(r.items.map((i) => i.correct), [true, false, false, false]);
  assert.equal(r.score, 1);
  assert.equal(r.total, 4);
  assert.equal(r.pct, 25);
  assert.deepEqual(r.items[0], { number: 1, order: ['B', 'A'], picked: ['A'], correct: true });
});
```

`tests/web/shuffle.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { fisherYates, sampleWithoutReplacement } from '../../web/js/shuffle.js';

function seeded(seed) {
  let s = seed;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

test('fisherYates returns a permutation and does not mutate the input', () => {
  const input = ['A', 'B', 'C', 'D', 'E'];
  const out = fisherYates(input, seeded(42));
  assert.deepEqual([...out].sort(), input);
  assert.deepEqual(input, ['A', 'B', 'C', 'D', 'E']);
  assert.equal(out.length, 5);
});

test('fisherYates is deterministic for a given rng', () => {
  assert.deepEqual(fisherYates([1, 2, 3, 4], seeded(7)), fisherYates([1, 2, 3, 4], seeded(7)));
});

test('sampleWithoutReplacement returns n unique items, capped at the array length', () => {
  const pool = Array.from({ length: 20 }, (_, i) => i + 1);
  const sample = sampleWithoutReplacement(pool, 5, seeded(3));
  assert.equal(sample.length, 5);
  assert.equal(new Set(sample).size, 5);
  assert.ok(sample.every((n) => pool.includes(n)));
  assert.equal(sampleWithoutReplacement(pool, 50, seeded(3)).length, 20);
});
```

`tests/web/timer.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatClock, remainingSeconds } from '../../web/js/timer.js';

test('remainingSeconds counts down from started_at using wall-clock time', () => {
  const start = '2026-01-01T00:00:00.000Z';
  const t0 = Date.parse(start);
  assert.equal(remainingSeconds(start, 120, t0), 120);
  assert.equal(remainingSeconds(start, 120, t0 + 30_000), 90);
  assert.equal(remainingSeconds(start, 120, t0 + 119_400), 1);
  assert.equal(remainingSeconds(start, 120, t0 + 120_000), 0);
  assert.equal(remainingSeconds(start, 120, t0 + 999_000), 0);
});

test('formatClock renders mm:ss and allows minutes above 99', () => {
  assert.equal(formatClock(0), '00:00');
  assert.equal(formatClock(65), '01:05');
  assert.equal(formatClock(7200), '120:00');
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: failures with `Cannot find module .../web/js/grading.js` (and shuffle/timer).

- [ ] **Step 3: Write the modules**

`web/js/config.js`:
```js
export const PASS_PCT = 70;
export const EXAM_DEFAULTS = { count: 50, minutes: 120 };
export const EXAM_LIMITS = { minMinutes: 1, maxMinutes: 600 };
export const TIMER_WARN_S = 5 * 60;
export const SAVE_DEBOUNCE_MS = 500;
export const SAVE_RETRY_MIN_MS = 1000;
export const SAVE_RETRY_MAX_MS = 30000;
```

`web/js/grading.js`:
```js
/** Pure grading helpers (no DOM). */
export function isCorrect(answer, picked) {
  if (!Array.isArray(answer) || !Array.isArray(picked)) return false;
  if (answer.length === 0 || picked.length !== answer.length) return false;
  const a = [...answer].sort().join('');
  const b = [...new Set(picked)].sort().join('');
  return a === b;
}

export function pct(score, total) {
  return total ? Math.round((1000 * score) / total) / 10 : 0;
}

/** items: [{number, order, picked}]; byNumber: Map<number, question>. */
export function scoreExam(items, byNumber) {
  const graded = items.map((it) => {
    const q = byNumber.get(it.number);
    const picked = [...(it.picked || [])];
    return { number: it.number, order: it.order, picked, correct: q ? isCorrect(q.answer, picked) : false };
  });
  const score = graded.filter((g) => g.correct).length;
  return { items: graded, score, total: graded.length, pct: pct(score, graded.length) };
}
```

`web/js/shuffle.js`:
```js
/** Fisher–Yates shuffle; returns a new array. rng() must return [0, 1). */
export function fisherYates(arr, rng = Math.random) {
  const a = arr.slice();
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(rng() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

export function sampleWithoutReplacement(arr, n, rng = Math.random) {
  return fisherYates(arr, rng).slice(0, Math.min(n, arr.length));
}
```

`web/js/timer.js`:
```js
/** Remaining whole seconds, computed from wall-clock time so refresh/sleep cannot drift it. */
export function remainingSeconds(startedAtIso, durationS, nowMs = Date.now()) {
  const elapsed = (nowMs - Date.parse(startedAtIso)) / 1000;
  return Math.max(0, Math.ceil(durationS - elapsed));
}

export function formatClock(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: `# pass 9`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add web/js/config.js web/js/grading.js web/js/shuffle.js web/js/timer.js tests/web
git commit -m "feat(web): pure grading, shuffle and timer modules with node tests"
```

---

### Task 12: Progress reducers (pure)

**Files:**
- Create: `web/js/progress.js`
- Test: `tests/web/progress.test.js`

**Interfaces:**
- Consumes: `scoreExam` (Task 11).
- Produces (all pure; return new objects, never mutate):
  `emptyProgress(bankId)`, `recordAttempt(p, number, picked, correct, atIso)`, `removeFromMistakes(p, number)`, `clearMistakes(p)`, `mistakePool(p) -> number[]`, `overallStats(p) -> {attempted, attempts, correct, accuracy|null}`,
  `startExam(p, numbers, orders, durationS, nowIso)`, `setExamPick(p, index, picked)`, `toggleExamFlag(p, index)`, `setExamCurrent(p, index)`, `discardExam(p)`, `finishExam(p, active, byNumber, nowIso, autoSubmitted=false)`,
  `startPractice(p, from, to)`, `setPracticeIndex(p, index)`, `checkPractice(p, number, picked, correct, nowIso)`.

- [ ] **Step 1: Write the failing tests**

`tests/web/progress.test.js`:
```js
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  checkPractice, clearMistakes, discardExam, emptyProgress, finishExam, mistakePool, overallStats,
  recordAttempt, removeFromMistakes, setExamCurrent, setExamPick, setPracticeIndex, startExam,
  startPractice, toggleExamFlag,
} from '../../web/js/progress.js';

const T = '2026-01-01T10:00:00.000Z';

test('emptyProgress has the documented shape', () => {
  assert.deepEqual(emptyProgress('demo'), {
    version: 1, bank_id: 'demo', updated_at: null, questions: {}, exams: [], active_exam: null, practice: null,
  });
});

test('recordAttempt accumulates stats and a wrong answer enters the mistakes pool', () => {
  let p = emptyProgress('demo');
  p = recordAttempt(p, 17, ['B'], false, T);
  assert.deepEqual(p.questions['17'], {
    attempts: 1, correct: 0, wrong: 1, last_result: 'wrong', last_answer: ['B'], last_at: T, in_mistakes: true,
  });
  p = recordAttempt(p, 17, ['C'], true, T);
  assert.equal(p.questions['17'].attempts, 2);
  assert.equal(p.questions['17'].correct, 1);
  assert.equal(p.questions['17'].last_result, 'correct');
  assert.equal(p.questions['17'].in_mistakes, true, 'a later correct answer does not clear the pool');
});

test('recordAttempt does not mutate its input', () => {
  const p = emptyProgress('demo');
  recordAttempt(p, 1, ['A'], true, T);
  assert.deepEqual(p.questions, {});
});

test('mistake pool: sorted numbers, per-question removal, clear all', () => {
  let p = emptyProgress('demo');
  p = recordAttempt(p, 30, ['A'], false, T);
  p = recordAttempt(p, 4, ['A'], false, T);
  p = recordAttempt(p, 9, ['A'], true, T);
  assert.deepEqual(mistakePool(p), [4, 30]);
  p = removeFromMistakes(p, 30);
  assert.deepEqual(mistakePool(p), [4]);
  assert.equal(p.questions['30'].wrong, 1, 'stats are kept');
  assert.equal(removeFromMistakes(p, 999), p, 'unknown number is a no-op');
  p = clearMistakes(p);
  assert.deepEqual(mistakePool(p), []);
});

test('overallStats', () => {
  let p = emptyProgress('demo');
  assert.deepEqual(overallStats(p), { attempted: 0, attempts: 0, correct: 0, accuracy: null });
  p = recordAttempt(p, 1, ['A'], true, T);
  p = recordAttempt(p, 1, ['A'], true, T);
  p = recordAttempt(p, 2, ['A'], false, T);
  assert.deepEqual(overallStats(p), { attempted: 2, attempts: 3, correct: 2, accuracy: 67 });
});

test('exam lifecycle: start, pick, flag, navigate, finish', () => {
  const byNumber = new Map([[1, { answer: ['A'] }], [2, { answer: ['B', 'C'] }], [3, { answer: ['D'] }]]);
  let p = startExam(emptyProgress('demo'), [1, 2, 3], [['B', 'A'], ['C', 'B', 'A'], ['A', 'B', 'C', 'D']], 7200, T);
  assert.equal(p.active_exam.id, T);
  assert.equal(p.active_exam.duration_s, 7200);
  assert.equal(p.active_exam.current, 0);
  assert.deepEqual(p.active_exam.items[1], { number: 2, order: ['C', 'B', 'A'], picked: [], flagged: false });

  p = setExamPick(p, 0, ['A']);
  p = setExamPick(p, 1, ['B']);
  p = toggleExamFlag(p, 2);
  p = setExamCurrent(p, 2);
  assert.deepEqual(p.active_exam.items[0].picked, ['A']);
  assert.equal(p.active_exam.items[2].flagged, true);
  assert.equal(p.active_exam.current, 2);

  const finishedAt = '2026-01-01T11:05:00.000Z';
  p = finishExam(p, p.active_exam, byNumber, finishedAt, false);
  assert.equal(p.active_exam, null);
  assert.equal(p.exams.length, 1);
  const ex = p.exams[0];
  assert.equal(ex.id, T);
  assert.equal(ex.score, 1);
  assert.equal(ex.total, 3);
  assert.equal(ex.pct, 33.3);
  assert.equal(ex.time_used_s, 3900);
  assert.equal(ex.auto_submitted, false);
  assert.equal(ex.finished_at, finishedAt);
  assert.deepEqual(ex.items.map((i) => i.correct), [true, false, false]);
  assert.deepEqual(mistakePool(p), [2, 3], 'wrong and unanswered both enter the pool');
  assert.equal(p.questions['1'].attempts, 1);
});

test('finishExam caps time_used_s at the duration and records auto-submit', () => {
  const byNumber = new Map([[1, { answer: ['A'] }]]);
  let p = startExam(emptyProgress('demo'), [1], [['A', 'B']], 60, T);
  p = finishExam(p, p.active_exam, byNumber, '2026-01-01T10:30:00.000Z', true);
  assert.equal(p.exams[0].time_used_s, 60);
  assert.equal(p.exams[0].auto_submitted, true);
});

test('discardExam clears the active exam without recording anything', () => {
  let p = startExam(emptyProgress('demo'), [1], [['A']], 60, T);
  p = discardExam(p);
  assert.equal(p.active_exam, null);
  assert.deepEqual(p.exams, []);
  assert.deepEqual(p.questions, {});
});

test('exam reducers are no-ops without an active exam', () => {
  const p = emptyProgress('demo');
  assert.equal(setExamPick(p, 0, ['A']), p);
  assert.equal(toggleExamFlag(p, 0), p);
  assert.equal(setExamCurrent(p, 0), p);
});

test('practice lifecycle', () => {
  let p = startPractice(emptyProgress('demo'), 1, 50);
  assert.deepEqual(p.practice, { range: [1, 50], index: 0, picks: {} });
  p = setPracticeIndex(p, 11);
  p = checkPractice(p, 12, ['C'], false, T);
  assert.equal(p.practice.index, 11);
  assert.deepEqual(p.practice.picks, { 12: ['C'] });
  assert.equal(p.questions['12'].in_mistakes, true);
  p = startPractice(p, 51, 100);
  assert.deepEqual(p.practice.picks, {}, 'a new run resets picks');
  assert.equal(p.questions['12'].attempts, 1, 'but stats persist');
  assert.equal(setPracticeIndex(emptyProgress('x'), 3).practice, null);
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: `progress.test.js` fails with `Cannot find module .../web/js/progress.js`; the 9 earlier tests still pass.

- [ ] **Step 3: Write the reducers**

`web/js/progress.js`:
```js
/** Pure reducers over the progress document (spec §6). Never mutate; always return new objects. */
import { scoreExam } from './grading.js';

export function emptyProgress(bankId) {
  return { version: 1, bank_id: bankId, updated_at: null, questions: {}, exams: [], active_exam: null, practice: null };
}

const EMPTY_STAT = { attempts: 0, correct: 0, wrong: 0, last_result: null, last_answer: null, last_at: null, in_mistakes: false };

export function recordAttempt(p, number, picked, correct, atIso) {
  const key = String(number);
  const prev = p.questions[key] || EMPTY_STAT;
  const stat = {
    ...prev,
    attempts: prev.attempts + 1,
    correct: prev.correct + (correct ? 1 : 0),
    wrong: prev.wrong + (correct ? 0 : 1),
    last_result: correct ? 'correct' : 'wrong',
    last_answer: [...picked],
    last_at: atIso,
    in_mistakes: prev.in_mistakes || !correct,
  };
  return { ...p, questions: { ...p.questions, [key]: stat } };
}

export function removeFromMistakes(p, number) {
  const key = String(number);
  const stat = p.questions[key];
  if (!stat || !stat.in_mistakes) return p;
  return { ...p, questions: { ...p.questions, [key]: { ...stat, in_mistakes: false } } };
}

export function clearMistakes(p) {
  const questions = {};
  for (const [k, v] of Object.entries(p.questions)) questions[k] = v.in_mistakes ? { ...v, in_mistakes: false } : v;
  return { ...p, questions };
}

export function mistakePool(p) {
  return Object.entries(p.questions)
    .filter(([, v]) => v.in_mistakes)
    .map(([k]) => Number(k))
    .sort((a, b) => a - b);
}

export function overallStats(p) {
  let attempted = 0, attempts = 0, correct = 0;
  for (const v of Object.values(p.questions)) {
    if (v.attempts > 0) attempted++;
    attempts += v.attempts;
    correct += v.correct;
  }
  return { attempted, attempts, correct, accuracy: attempts ? Math.round((100 * correct) / attempts) : null };
}

// ---- exam ----
export function startExam(p, numbers, orders, durationS, nowIso) {
  const items = numbers.map((number, i) => ({ number, order: orders[i], picked: [], flagged: false }));
  return { ...p, active_exam: { id: nowIso, started_at: nowIso, duration_s: durationS, current: 0, items } };
}

function withActive(p, fn) {
  return p.active_exam ? { ...p, active_exam: fn(p.active_exam) } : p;
}

function withItem(active, index, fn) {
  const items = active.items.slice();
  items[index] = fn(items[index]);
  return { ...active, items };
}

export const setExamPick = (p, index, picked) =>
  withActive(p, (a) => withItem(a, index, (it) => ({ ...it, picked: [...picked] })));
export const toggleExamFlag = (p, index) =>
  withActive(p, (a) => withItem(a, index, (it) => ({ ...it, flagged: !it.flagged })));
export const setExamCurrent = (p, index) => withActive(p, (a) => ({ ...a, current: index }));
export const discardExam = (p) => ({ ...p, active_exam: null });

export function finishExam(p, active, byNumber, nowIso, autoSubmitted = false) {
  const graded = scoreExam(active.items, byNumber);
  const elapsed = Math.round((Date.parse(nowIso) - Date.parse(active.started_at)) / 1000);
  const exam = {
    id: active.id,
    started_at: active.started_at,
    finished_at: nowIso,
    duration_s: active.duration_s,
    time_used_s: Math.min(active.duration_s, Math.max(0, elapsed)),
    auto_submitted: autoSubmitted,
    items: graded.items,
    score: graded.score,
    total: graded.total,
    pct: graded.pct,
  };
  let next = p;
  for (const it of graded.items) next = recordAttempt(next, it.number, it.picked, it.correct, nowIso);
  return { ...next, exams: [...next.exams, exam], active_exam: null };
}

// ---- practice ----
export const startPractice = (p, from, to) => ({ ...p, practice: { range: [from, to], index: 0, picks: {} } });
export const setPracticeIndex = (p, index) => (p.practice ? { ...p, practice: { ...p.practice, index } } : p);

export function checkPractice(p, number, picked, correct, nowIso) {
  const next = recordAttempt(p, number, picked, correct, nowIso);
  if (!next.practice) return next;
  return { ...next, practice: { ...next.practice, picks: { ...next.practice.picks, [String(number)]: [...picked] } } };
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`
Expected: `# pass 19`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add web/js/progress.js tests/web/progress.test.js
git commit -m "feat(web): pure progress reducers (stats, mistakes pool, exam, practice)"
```

---

### Task 13: App shell — DOM helper, toast, keys, API, store, router, Home view

**Files:**
- Create: `web/index.html`, `web/app.css`, `web/js/dom.js`, `web/js/toast.js`, `web/js/keys.js`, `web/js/api.js`, `web/js/store.js`, `web/js/main.js`, `web/js/views/home.js`
- Create placeholders (replaced in later tasks): `web/js/views/examSetup.js`, `exam.js`, `examResult.js`, `practiceSetup.js`, `practice.js`, `review.js` — each exporting `render` that shows a "coming soon" card so the router works end-to-end.

**Interfaces:**
- Produces: `el(tag, attrs, ...children) -> HTMLElement` (attrs: `class`, `dataset`, `onXxx` listeners, boolean/number props, strings → attributes; `null/false` children skipped); `toast.show(id, message, {sticky, ms, kind})`, `toast.hide(id)`; `bindKeys({onOption(i), onEnter, onPrev, onNext, onFlag}) -> unbind()`; `api.listBanks()`, `getBank(id)`, `getProgress(id)`, `putProgress(id, doc)`, `imageUrl(bankId, src)`, `ApiError`; `store {bankId, bank, byNumber: Map, progress, dirty}`, `loadBank(id)`, `update(reducerFn) -> progress`, `flush() -> Promise`; `navigate()`; each view module exports `async render(container, params) -> cleanupFn | undefined`.

- [ ] **Step 1: Write the shell and helpers**

`web/index.html`:
```html
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Exam Sim</title>
  <link rel="stylesheet" href="app.css">
</head>
<body>
  <header class="topnav">
    <a href="#/" class="brand">Exam Sim</a>
    <span id="bank-label"></span>
  </header>
  <main id="app" class="container"></main>
  <div id="toast-root"></div>
  <script type="module" src="js/main.js"></script>
</body>
</html>
```

`web/js/dom.js`:
```js
/** Tiny DOM builder: el('div', {class: 'x', onClick: fn}, 'text', childNode, [more]) */
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs || {})) {
    if (value == null || value === false) continue;
    if (key === 'class') node.className = value;
    else if (key === 'dataset') Object.assign(node.dataset, value);
    else if (key.startsWith('on') && typeof value === 'function') node.addEventListener(key.slice(2).toLowerCase(), value);
    else if (key in node && typeof value !== 'string') node[key] = value;     // checked, disabled, selected, value(number)
    else node.setAttribute(key, value === true ? '' : value);
  }
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}
```

`web/js/toast.js`:
```js
import { el } from './dom.js';

const timers = new Map();

export const toast = {
  show(id, message, { sticky = false, ms = 3000, kind = 'info' } = {}) {
    this.hide(id);
    document.getElementById('toast-root').append(el('div', { class: `toast ${kind}`, id: `toast-${id}` }, message));
    if (!sticky) timers.set(id, setTimeout(() => this.hide(id), ms));
  },
  hide(id) {
    clearTimeout(timers.get(id));
    timers.delete(id);
    document.getElementById(`toast-${id}`)?.remove();
  },
};
```

`web/js/keys.js`:
```js
/**
 * Keyboard shortcuts for question screens. Ignores typing in text/number inputs and
 * lets focused buttons/links handle Enter themselves (avoids double actions).
 *  1-9 / A-I → onOption(displayIndex) · F → onFlag (if given, else F is option 6)
 *  Enter → onEnter · ArrowLeft → onPrev · ArrowRight → onNext
 */
export function bindKeys({ onOption, onEnter, onPrev, onNext, onFlag } = {}) {
  const handler = (e) => {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
    const target = e.target || {};
    const tag = target.tagName || '';
    if (tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (tag === 'INPUT' && target.type !== 'radio' && target.type !== 'checkbox') return;
    const k = e.key;
    if (k === 'Enter' && (tag === 'BUTTON' || tag === 'A')) return;
    if ((k === 'f' || k === 'F') && onFlag) { onFlag(); e.preventDefault(); return; }
    if (/^[1-9]$/.test(k) && onOption) { onOption(Number(k) - 1); e.preventDefault(); return; }
    if (/^[a-iA-I]$/.test(k) && onOption) { onOption(k.toUpperCase().charCodeAt(0) - 65); e.preventDefault(); return; }
    if (k === 'Enter' && onEnter) { onEnter(); e.preventDefault(); return; }
    if (k === 'ArrowLeft' && onPrev) { onPrev(); e.preventDefault(); return; }
    if (k === 'ArrowRight' && onNext) { onNext(); e.preventDefault(); }
  };
  document.addEventListener('keydown', handler);
  return () => document.removeEventListener('keydown', handler);
}
```

`web/js/api.js`:
```js
export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

async function request(url, options = {}) {
  let res;
  try {
    res = await fetch(url, options);
  } catch (e) {
    throw new ApiError(`Cannot reach the server (${e.message})`, 0);
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = (await res.json()).detail || detail; } catch { /* non-JSON error body */ }
    throw new ApiError(`${res.status}: ${detail}`, res.status);
  }
  return res.json();
}

const enc = encodeURIComponent;
export const listBanks = () => request('/api/banks');
export const getBank = (id) => request(`/api/banks/${enc(id)}`);
export const getProgress = (id) => request(`/api/banks/${enc(id)}/progress`);
export const putProgress = (id, doc) => request(`/api/banks/${enc(id)}/progress`, {
  method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(doc),
});
export const imageUrl = (bankId, src) => `/banks/${enc(bankId)}/${src}`;
```

`web/js/store.js`:
```js
/** Holds the loaded bank + progress; debounced, retrying saves of the whole progress document. */
import * as api from './api.js';
import { SAVE_DEBOUNCE_MS, SAVE_RETRY_MAX_MS, SAVE_RETRY_MIN_MS } from './config.js';
import { emptyProgress } from './progress.js';
import { toast } from './toast.js';

export const store = {
  bankId: null, bank: null, byNumber: new Map(), progress: null,
  dirty: false, saving: false, timer: null, retryDelay: SAVE_RETRY_MIN_MS,
};

export async function loadBank(bankId) {
  const [bank, progress] = await Promise.all([api.getBank(bankId), api.getProgress(bankId)]);
  store.bankId = bankId;
  store.bank = bank;
  store.byNumber = new Map(bank.questions.map((q) => [q.number, q]));
  store.progress = { ...emptyProgress(bankId), ...progress, bank_id: bankId };
  store.dirty = false;
  localStorage.setItem('selectedBank', bankId);
}

export function update(reducer) {
  store.progress = reducer(store.progress);
  store.dirty = true;
  clearTimeout(store.timer);
  store.timer = setTimeout(flush, SAVE_DEBOUNCE_MS);
  return store.progress;
}

export async function flush() {
  clearTimeout(store.timer);
  store.timer = null;
  if (!store.dirty || store.saving || !store.bankId) return;
  store.saving = true;
  const snapshot = store.progress;
  try {
    const res = await api.putProgress(store.bankId, snapshot);
    if (store.progress === snapshot) {
      store.dirty = false;
      store.progress = { ...snapshot, updated_at: res.updated_at };
    }
    store.retryDelay = SAVE_RETRY_MIN_MS;
    toast.hide('save');
  } catch (err) {
    toast.show('save', `Progress not saved — retrying… (${err.message})`, { sticky: true, kind: 'error' });
    store.timer = setTimeout(flush, store.retryDelay);
    store.retryDelay = Math.min(store.retryDelay * 2, SAVE_RETRY_MAX_MS);
  } finally {
    store.saving = false;
    if (store.dirty && store.timer == null) store.timer = setTimeout(flush, SAVE_DEBOUNCE_MS);
  }
}

window.addEventListener('beforeunload', (e) => {
  if (store.dirty) { e.preventDefault(); e.returnValue = ''; }
});
```

`web/js/main.js`:
```js
import * as api from './api.js';
import { el } from './dom.js';
import { loadBank, store } from './store.js';
import * as home from './views/home.js';
import * as examSetup from './views/examSetup.js';
import * as exam from './views/exam.js';
import * as examResult from './views/examResult.js';
import * as practiceSetup from './views/practiceSetup.js';
import * as practice from './views/practice.js';
import * as review from './views/review.js';

// Longest prefixes first so 'exam/result/<id>' is not captured by 'exam'.
const routes = [
  ['exam/result', examResult], ['exam/setup', examSetup], ['exam', exam],
  ['practice/setup', practiceSetup], ['practice', practice], ['review', review], ['', home],
];
let cleanup = null;

function match(hash) {
  const path = hash.replace(/^#\/?/, '').replace(/\/+$/, '');
  for (const [prefix, view] of routes) {
    const hit = prefix === '' ? path === '' : path === prefix || path.startsWith(prefix + '/');
    if (hit) {
      const rest = path.slice(prefix.length).replace(/^\//, '');
      return { view, params: rest ? rest.split('/').map(decodeURIComponent) : [] };
    }
  }
  return { view: home, params: [] };
}

async function ensureBank() {
  if (store.bank) return;
  const banks = await api.listBanks();
  if (!banks.length) throw new Error('No question banks found. Run: uv run parse-pdf <file.pdf> --id <bank-id> --title "<title>"');
  const saved = localStorage.getItem('selectedBank');
  await loadBank(banks.some((b) => b.id === saved) ? saved : banks[0].id);
}

function renderError(container, err) {
  container.replaceChildren(el('section', { class: 'card error' },
    el('h2', {}, 'Something went wrong'),
    el('p', {}, err.message || String(err)),
    el('p', { class: 'muted' }, 'Is the server running? Start it with: uv run serve'),
    el('button', { class: 'btn', onClick: () => navigate() }, 'Retry')));
}

export async function navigate() {
  const container = document.getElementById('app');
  if (cleanup) { try { cleanup(); } catch { /* ignore */ } cleanup = null; }
  container.replaceChildren(el('p', { class: 'muted' }, 'Loading…'));
  const { view, params } = match(location.hash);
  try {
    await ensureBank();
    document.getElementById('bank-label').textContent = store.bank.bank.title;
    container.replaceChildren();
    cleanup = (await view.render(container, params)) || null;
  } catch (err) {
    console.error(err);
    renderError(container, err);
  }
}

window.addEventListener('hashchange', navigate);
navigate();
```

`web/js/views/home.js`:
```js
import * as api from '../api.js';
import { PASS_PCT } from '../config.js';
import { el } from '../dom.js';
import { mistakePool, overallStats } from '../progress.js';
import { flush, loadBank, store } from '../store.js';
import { formatClock } from '../timer.js';

const stat = (value, label) => el('div', { class: 'stat' }, el('div', { class: 'stat-value' }, value), el('div', { class: 'stat-label' }, label));
const card = (href, title, text) => el('a', { class: 'mode-card', href }, el('h3', {}, title), el('p', {}, text));

export async function render(container) {
  const banks = await api.listBanks();
  const p = store.progress;
  const stats = overallStats(p);
  const pool = mistakePool(p);
  const total = store.bank.questions.length;

  const select = el('select', { class: 'bank-select', onChange: async (e) => {
    await flush();
    await loadBank(e.target.value);
    document.getElementById('bank-label').textContent = store.bank.bank.title;
    render(container);
  } }, banks.map((b) => el('option', { value: b.id, selected: b.id === store.bankId }, `${b.title} (${b.question_count})`)));

  const active = p.active_exam;
  const resume = active ? el('a', { class: 'banner', href: '#/exam' },
    `▶ Resume exam in progress — ${active.items.filter((i) => i.picked.length).length}/${active.items.length} answered`) : null;

  const history = [...p.exams].reverse().slice(0, 20).map((ex) => el('tr', {
    class: 'row-link', onClick: () => { location.hash = `#/exam/result/${encodeURIComponent(ex.id)}`; },
  },
    el('td', {}, new Date(ex.finished_at).toLocaleString()),
    el('td', {}, `${ex.score}/${ex.total} (${ex.pct}%)`),
    el('td', { class: ex.pct >= PASS_PCT ? 'pass' : 'fail' }, ex.pct >= PASS_PCT ? 'PASS' : 'FAIL'),
    el('td', {}, formatClock(ex.time_used_s) + (ex.auto_submitted ? ' ⏰' : ''))));

  container.replaceChildren(
    el('section', { class: 'card' }, el('label', {}, 'Question bank: ', select)),
    resume,
    el('section', { class: 'stats' },
      stat(total, 'questions'), stat(stats.attempted, 'attempted'),
      stat(stats.accuracy == null ? '—' : `${stats.accuracy}%`, 'accuracy'), stat(pool.length, 'mistakes')),
    el('section', { class: 'mode-cards' },
      card('#/exam/setup', 'Exam', 'Timed mock exam · default 50 questions / 120 min · shuffled options · results at the end'),
      card('#/practice/setup', 'Practice', 'Work through a range in order · instant feedback after each Check'),
      card('#/review', 'Review mistakes', pool.length ? `${pool.length} question${pool.length === 1 ? '' : 's'} to re-drill` : 'No mistakes recorded yet')),
    el('section', { class: 'card' }, el('h2', {}, 'Exam history'),
      history.length
        ? el('table', { class: 'history' },
          el('thead', {}, el('tr', {}, el('th', {}, 'Finished'), el('th', {}, 'Score'), el('th', {}, 'Result'), el('th', {}, 'Time'))),
          el('tbody', {}, history))
        : el('p', { class: 'muted' }, 'No exams taken yet.')));
}
```

Placeholder views (one file each for `examSetup.js`, `exam.js`, `examResult.js`, `practiceSetup.js`, `practice.js`, `review.js`), identical content apart from the title:
```js
import { el } from '../dom.js';

export async function render(container) {
  container.replaceChildren(el('section', { class: 'card' }, el('h2', {}, 'Coming soon'), el('a', { class: 'btn link', href: '#/' }, 'Home')));
}
```

- [ ] **Step 2: Write the stylesheet**

`web/app.css`:
```css
:root {
  --bg: #f6f7f9; --card: #fff; --text: #1f2328; --muted: #6b7280; --line: #e5e7eb;
  --primary: #2563eb; --primary-ink: #fff; --ok: #16a34a; --ok-bg: #dcfce7; --bad: #dc2626; --bad-bg: #fee2e2;
  --warn-bg: #fef3c7; --warn-ink: #78350f; --flag: #f59e0b;
}
* { box-sizing: border-box; }
html, body { margin: 0; background: var(--bg); color: var(--text); font: 16px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; }
.topnav { display: flex; gap: 12px; align-items: baseline; padding: 10px 20px; background: #fff; border-bottom: 1px solid var(--line); }
.brand { font-weight: 700; color: var(--text); text-decoration: none; }
#bank-label { color: var(--muted); font-size: 14px; }
.container { max-width: 860px; margin: 0 auto; padding: 20px 16px 60px; }
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 16px 20px; margin-bottom: 16px; }
.card.error { border-color: #fca5a5; }
.muted { color: var(--muted); }
.error-text { color: var(--bad); min-height: 1.2em; margin: 4px 0; }
h2 { margin: 0 0 12px; font-size: 20px; }
h3 { margin: 0 0 6px; }
.btn { display: inline-block; padding: 8px 14px; border: 1px solid var(--line); border-radius: 8px; background: #fff; color: var(--text); font: inherit; cursor: pointer; text-decoration: none; }
.btn:hover { border-color: #c7cbd1; }
.btn:disabled { opacity: .45; cursor: not-allowed; }
.btn.primary { background: var(--primary); border-color: var(--primary); color: var(--primary-ink); }
.btn.danger { color: var(--bad); border-color: #fca5a5; }
.btn.link { border-color: transparent; color: var(--primary); }
.btn.active { background: var(--warn-bg); border-color: var(--flag); }
.actions { display: flex; gap: 10px; align-items: center; margin: 14px 0; flex-wrap: wrap; }
.spacer { flex: 1; }
.form-row { display: flex; gap: 20px; flex-wrap: wrap; margin: 10px 0; }
.form-row label { display: flex; flex-direction: column; gap: 4px; font-size: 14px; color: var(--muted); }
input[type=number], select { font: inherit; padding: 6px 8px; border: 1px solid var(--line); border-radius: 6px; width: 120px; background: #fff; }
select { width: auto; max-width: 100%; }
.jump { width: 72px; }
.banner { display: block; padding: 10px 14px; border-radius: 8px; background: #dbeafe; color: #1e3a8a; margin-bottom: 16px; text-decoration: none; }
.banner.warn { background: var(--warn-bg); color: var(--warn-ink); }
.stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; margin-bottom: 16px; }
.stat { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 12px; text-align: center; }
.stat-value { font-size: 24px; font-weight: 700; }
.stat-label { color: var(--muted); font-size: 13px; }
.mode-cards { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px; }
.mode-card { display: block; background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 16px; color: inherit; text-decoration: none; }
.mode-card:hover { border-color: var(--primary); }
.mode-card p { margin: 0; color: var(--muted); font-size: 14px; }
table.history { width: 100%; border-collapse: collapse; font-size: 14px; }
.history th, .history td { text-align: left; padding: 6px 8px; border-bottom: 1px solid var(--line); }
.row-link { cursor: pointer; }
.row-link:hover { background: #f3f4f6; }
.pass { color: var(--ok); font-weight: 600; }
.fail { color: var(--bad); font-weight: 600; }
.toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; flex-wrap: wrap; }
.progress-label { font-weight: 600; }
.clock { font-variant-numeric: tabular-nums; font-weight: 700; padding: 2px 10px; border-radius: 6px; background: #eef2ff; }
.clock.warn { background: var(--bad-bg); color: var(--bad); }
.question-card { background: #fff; border: 1px solid var(--line); border-radius: 10px; padding: 16px 20px; }
.question-head { display: flex; gap: 10px; align-items: center; margin-bottom: 8px; }
.qnum { color: var(--muted); font-size: 13px; }
.hint { font-size: 12px; padding: 2px 8px; border-radius: 999px; background: var(--warn-bg); color: var(--warn-ink); }
.block-text { white-space: pre-line; margin: 0 0 8px; }
.block-image { display: block; max-width: 100%; height: auto; margin: 8px 0; border: 1px solid var(--line); }
.options { display: flex; flex-direction: column; gap: 8px; margin-top: 12px; }
.option { display: grid; grid-template-columns: auto auto 1fr; gap: 10px; align-items: start; padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px; cursor: pointer; }
.option:hover { background: #f9fafb; }
.option.picked { border-color: var(--primary); background: #eff6ff; }
.option.is-key { border-color: var(--ok); background: var(--ok-bg); }
.option.is-wrong-pick { border-color: var(--bad); background: var(--bad-bg); }
.option input { margin-top: 5px; }
.option .letter { font-weight: 700; }
.option .content .block-text:last-child { margin-bottom: 0; }
.feedback { margin-top: 12px; border-radius: 10px; padding: 14px 18px; border: 1px solid var(--line); background: #fff; }
.verdict { padding: 8px 12px; border-radius: 8px; margin-bottom: 8px; font-weight: 600; }
.feedback.correct .verdict { background: var(--ok-bg); color: #14532d; }
.feedback.wrong .verdict { background: var(--bad-bg); color: #7f1d1d; }
.votes-title { font-size: 13px; color: var(--muted); margin: 8px 0 4px; }
.vote-row { display: grid; grid-template-columns: 56px 1fr 48px; gap: 8px; align-items: center; font-size: 14px; }
.vote-bar { height: 10px; background: #eef2ff; border-radius: 5px; overflow: hidden; }
.vote-fill { height: 100%; background: var(--primary); }
.disputed { margin-top: 10px; padding: 8px 12px; border-radius: 8px; background: var(--warn-bg); color: var(--warn-ink); font-size: 14px; }
.navigator { display: grid; grid-template-columns: repeat(auto-fill, minmax(38px, 1fr)); gap: 6px; margin-top: 16px; }
.nav-cell { padding: 6px 0; border: 1px solid var(--line); border-radius: 6px; background: #fff; font: inherit; font-size: 13px; cursor: pointer; }
.nav-cell.answered { background: #dbeafe; border-color: #93c5fd; }
.nav-cell.flagged { box-shadow: inset 0 -3px 0 var(--flag); }
.nav-cell.current { outline: 2px solid var(--primary); }
.result-summary.pass h2 { color: var(--ok); }
.result-summary.fail h2 { color: var(--bad); }
.result-item { background: #fff; border: 1px solid var(--line); border-radius: 8px; margin-bottom: 8px; }
.result-item.ok { border-left: 4px solid var(--ok); }
.result-item.bad { border-left: 4px solid var(--bad); }
.result-row { display: grid; grid-template-columns: 24px auto 1fr 20px; gap: 10px; width: 100%; text-align: left; padding: 10px 12px; background: none; border: 0; font: inherit; cursor: pointer; }
.result-row .muted { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.result-detail { padding: 0 12px 12px; }
.toggle { display: flex; align-items: center; gap: 6px; font-size: 14px; }
#toast-root { position: fixed; bottom: 16px; left: 50%; transform: translateX(-50%); display: flex; flex-direction: column; gap: 8px; z-index: 50; }
.toast { padding: 10px 16px; border-radius: 8px; background: #1f2328; color: #fff; font-size: 14px; box-shadow: 0 4px 12px rgba(0, 0, 0, .2); }
.toast.error { background: var(--bad); }
@media (max-width: 640px) { .stats, .mode-cards { grid-template-columns: 1fr 1fr; } }
```

- [ ] **Step 3: Verify in the browser**

Run: `uv run serve --port 8010` (opens the browser) — or `--no-browser` and open `http://127.0.0.1:8010/`.
Check:
1. Home shows the bank dropdown with "Professional Data Engineer (2026-10) (349)", stats `349 / 0 / — / 0`, three mode cards, "No exams taken yet."
2. Clicking each mode card shows the "Coming soon" placeholder; "Home" returns.
3. `curl -s localhost:8010/api/banks/pde-2026-10/progress` still returns the default document (nothing has been saved yet).
4. Error path: run a second instance with an empty banks dir, `mkdir -p scratch/no-banks && uv run serve --no-browser --port 8011 --banks scratch/no-banks`, open `http://127.0.0.1:8011/` → the error card shows "No question banks found…" with a Retry button. Stop that instance.

Also run `npm test` and `uv run pytest` — both still green.

- [ ] **Step 4: Commit**

```bash
git add web
git commit -m "feat(web): app shell, router, store with debounced saves, Home view"
```

---

### Task 14: Question card + feedback components, Practice setup and Practice view

**Files:**
- Create: `web/js/components/questionCard.js`, `web/js/components/feedback.js`, `web/js/components/drill.js`
- Replace placeholders: `web/js/views/practiceSetup.js`, `web/js/views/practice.js`

**Interfaces:**
- Consumes: `el`, `imageUrl`, `isCorrect`, `store`/`update`, `startPractice`/`setPracticeIndex`/`checkPractice`, `bindKeys`.
- Produces: `renderBlocks(blocks, bankId) -> Node[]`; `renderQuestionCard({question, bankId, order=null, picked=[], locked=false, reveal=null, onPick}) -> HTMLElement` (display letters follow `order`; radio for single, checkbox for multi; unchecked boxes disabled once `select_count` picks are made; `reveal` = key letters to colour); `togglePick({question, order, picked}, displayIndex) -> picked[] | null` (keyboard helper honouring the cap); `renderFeedback({question, picked}) -> HTMLElement`. `mountDrill(container, opts) -> {unbind, draw, resetDraft}` — the shared pick → Check → feedback → Next loop (toolbar with progress label / jump-to / Home, question card, feedback, Prev/Check|Next/Skip, keyboard); `opts` = `{bankId, list(), index(), setIndex(i), checked(number), onCheck(number, picked, correct), label(s), toolbarExtras?(s), actionExtras?(s), empty()}`. Practice and Review are thin adapters over it.

- [ ] **Step 1: Write the components**

`web/js/components/questionCard.js`:
```js
import { imageUrl } from '../api.js';
import { el } from '../dom.js';

export function renderBlocks(blocks, bankId) {
  return blocks.map((b) => (b.type === 'image'
    ? el('img', { class: 'block-image', src: imageUrl(bankId, b.src), alt: 'question image', loading: 'lazy' })
    : el('p', { class: 'block-text' }, b.text)));
}

function displayLetters(question, order) {
  return order || question.options.map((o) => o.letter);
}

/**
 * order: original letters in display order (null = PDF order). picked: original letters.
 * reveal: key letters to highlight after checking (null while answering).
 */
export function renderQuestionCard({ question, bankId, order = null, picked = [], locked = false, reveal = null, onPick = () => {} }) {
  const letters = displayLetters(question, order);
  const byLetter = new Map(question.options.map((o) => [o.letter, o]));
  const multi = question.select_count > 1;
  const full = multi && picked.length >= question.select_count;

  const rows = letters.map((orig, i) => {
    const opt = byLetter.get(orig);
    if (!opt) return null;
    const display = String.fromCharCode(65 + i);
    const isPicked = picked.includes(orig);
    const classes = ['option'];
    if (isPicked) classes.push('picked');
    if (reveal) {
      if (reveal.includes(orig)) classes.push('is-key');
      else if (isPicked) classes.push('is-wrong-pick');
    }
    const input = el('input', {
      type: multi ? 'checkbox' : 'radio', name: `q${question.number}`, value: orig,
      checked: isPicked, disabled: locked || (full && !isPicked),
      onChange: () => {
        if (!multi) return onPick([orig]);
        if (input.checked) return onPick([...picked, orig]);
        return onPick(picked.filter((l) => l !== orig));
      },
    });
    return el('label', { class: classes.join(' '), dataset: { letter: orig, index: String(i) } },
      input, el('span', { class: 'letter' }, `${display}.`), el('div', { class: 'content' }, renderBlocks(opt.content, bankId)));
  });

  return el('article', { class: 'question-card' },
    el('header', { class: 'question-head' },
      el('span', { class: 'qnum' }, `#${question.number}`),
      multi ? el('span', { class: 'hint' }, `Choose ${question.select_count}`) : null),
    el('div', { class: 'stem' }, renderBlocks(question.stem, bankId)),
    el('div', { class: 'options' }, rows));
}

/** Keyboard toggle of the option at display index i. Returns the next picked[] or null if not allowed. */
export function togglePick({ question, order = null, picked = [] }, i) {
  const orig = displayLetters(question, order)[i];
  if (!orig) return null;
  if (question.select_count <= 1) return [orig];
  if (picked.includes(orig)) return picked.filter((l) => l !== orig);
  if (picked.length >= question.select_count) return null;
  return [...picked, orig];
}
```

`web/js/components/feedback.js`:
```js
import { el } from '../dom.js';
import { isCorrect } from '../grading.js';

const fmt = (letters) => (letters && letters.length ? letters.join(', ') : '—');

function disputedText(q) {
  if (!q.disputed) return null;
  if (q.answer_source === 'votes') return `Disputed: the key follows the community vote (${fmt(q.answer)}); the PDF says ${fmt(q.pdf_answer)}.`;
  if (q.answer_source === 'votes_tiebreak_pdf') return `Community vote is tied — tie broken by the PDF answer (${fmt(q.answer)}).`;
  if (q.answer_source === 'votes_tie_first') return `Community vote is tied and the PDF answer (${fmt(q.pdf_answer)}) is not among the tied options — first tied option (${fmt(q.answer)}) used.`;
  return 'Disputed answer.';
}

export function renderFeedback({ question: q, picked }) {
  const correct = isCorrect(q.answer, picked);
  const votes = q.votes.length
    ? el('div', { class: 'votes' },
      el('div', { class: 'votes-title' }, 'Community vote'),
      q.votes.map((v) => el('div', { class: 'vote-row' },
        el('span', { class: 'vote-letters' }, v.letters.join('')),
        el('div', { class: 'vote-bar' }, el('div', { class: 'vote-fill', style: `width:${Math.min(100, v.pct)}%` })),
        el('span', { class: 'vote-pct' }, `${v.pct}%`))))
    : el('div', { class: 'votes-title' }, 'No community vote data — key taken from the PDF answer');
  const note = disputedText(q);
  return el('section', { class: `feedback ${correct ? 'correct' : 'wrong'}` },
    el('div', { class: 'verdict' }, correct ? '✓ Correct' : `✗ Wrong — correct answer: ${fmt(q.answer)}`),
    el('div', { class: 'muted' }, `Your answer: ${fmt(picked)} · PDF answer: ${fmt(q.pdf_answer)}`),
    votes,
    note ? el('div', { class: 'disputed' }, note) : null);
}
```

- [ ] **Step 2: Write the drill loop, the Practice setup and the Practice view**

`web/js/views/practiceSetup.js`:
```js
import { el } from '../dom.js';
import { startPractice } from '../progress.js';
import { store, update } from '../store.js';

export const countInRange = (numbers, [a, b]) => numbers.filter((n) => n >= a && n <= b).length;

export async function render(container) {
  const numbers = store.bank.questions.map((q) => q.number);
  const min = Math.min(...numbers);
  const max = Math.max(...numbers);
  const prev = store.progress.practice;
  const from = el('input', { type: 'number', min, max, value: prev ? prev.range[0] : min });
  const to = el('input', { type: 'number', min, max, value: prev ? prev.range[1] : max });
  const err = el('p', { class: 'error-text' });

  const start = () => {
    const a = Number(from.value);
    const b = Number(to.value);
    if (!Number.isInteger(a) || !Number.isInteger(b) || a < min || b > max || a > b) {
      err.textContent = `Enter a range between ${min} and ${max} (from ≤ to).`;
      return;
    }
    if (!countInRange(numbers, [a, b])) { err.textContent = 'No questions in that range.'; return; }
    update((p) => startPractice(p, a, b));
    location.hash = '#/practice';
  };

  const resume = prev
    ? el('button', { class: 'btn', onClick: () => { location.hash = '#/practice'; } },
      `Resume (Q ${prev.index + 1} of ${countInRange(numbers, prev.range)}, range ${prev.range[0]}–${prev.range[1]})`)
    : null;

  container.replaceChildren(el('section', { class: 'card' },
    el('h2', {}, 'Practice'),
    el('p', { class: 'muted' }, `Questions #${min}–#${max} in PDF order. Pick a range; feedback after each Check.`),
    el('div', { class: 'form-row' }, el('label', {}, 'From #', from), el('label', {}, 'To #', to)),
    err,
    el('div', { class: 'actions' },
      el('button', { class: 'btn primary', onClick: start }, 'Start new'),
      resume,
      el('a', { class: 'btn link', href: '#/' }, 'Back'))));
}
```

`web/js/components/drill.js`:
```js
import { el } from '../dom.js';
import { isCorrect } from '../grading.js';
import { bindKeys } from '../keys.js';
import { renderFeedback } from './feedback.js';
import { renderQuestionCard, togglePick } from './questionCard.js';

/**
 * Shared "pick → Check → feedback → Next" loop used by Practice and Review.
 *
 * opts:
 *   bankId                      for image URLs
 *   list()                      → current question list (re-read on every draw; Review's pool shrinks)
 *   index()                     → current index into list() (clamped on read)
 *   setIndex(i)                 record a new index
 *   checked(number)             → picked[] if already checked in this run, else null
 *   onCheck(number, picked, correct)   record a checked answer
 *   label(s)                    → progress-label text
 *   toolbarExtras(s)            → node(s) placed before "Home" (optional)
 *   actionExtras(s)             → node(s) appended to the action row (optional)
 *   empty()                     → node shown when list() is empty
 *
 * Returns { unbind, draw, resetDraft }.
 */
export function mountDrill(container, opts) {
  let draft = [];                       // selection not yet checked

  const state = () => {
    const list = opts.list();
    if (!list.length) return { list, q: null };
    const index = Math.min(Math.max(opts.index(), 0), list.length - 1);
    const q = list[index];
    const checked = opts.checked(q.number);
    const locked = Array.isArray(checked);
    const picked = locked ? checked : draft;
    return { list, index, q, locked, picked, canCheck: !locked && picked.length === q.select_count };
  };

  const go = (i) => {
    const s = state();
    if (!s.q || i < 0 || i >= s.list.length) return;
    draft = [];
    opts.setIndex(i);
    draw();
  };

  const check = () => {
    const s = state();
    if (!s.q || !s.canCheck) return;
    opts.onCheck(s.q.number, s.picked, isCorrect(s.q.answer, s.picked));
    draft = [];
    draw();
  };

  const draw = () => {
    const s = state();
    if (!s.q) { container.replaceChildren(opts.empty()); return; }
    const jump = el('input', { type: 'number', class: 'jump', placeholder: '#', onKeydown: (e) => {
      if (e.key !== 'Enter') return;
      const i = s.list.findIndex((x) => x.number === Number(jump.value));
      if (i >= 0) go(i);
    } });
    // replaceChildren() stringifies null ("null" text node) — filter optional nodes first.
    container.replaceChildren(...[
      el('div', { class: 'toolbar' },
        el('span', { class: 'progress-label' }, opts.label(s)),
        el('span', { class: 'spacer' }),
        el('label', { class: 'muted' }, 'Go to # ', jump),
        opts.toolbarExtras ? opts.toolbarExtras(s) : null,
        el('a', { class: 'btn link', href: '#/' }, 'Home')),
      renderQuestionCard({ question: s.q, bankId: opts.bankId, picked: s.picked, locked: s.locked,
        reveal: s.locked ? s.q.answer : null, onPick: (next) => { draft = next; draw(); } }),
      s.locked ? renderFeedback({ question: s.q, picked: s.picked }) : null,
      el('div', { class: 'actions' },
        el('button', { class: 'btn', disabled: s.index === 0, onClick: () => go(s.index - 1) }, '← Prev'),
        s.locked
          ? el('button', { class: 'btn primary', disabled: s.index === s.list.length - 1, onClick: () => go(s.index + 1) }, 'Next →')
          : el('button', { class: 'btn primary', disabled: !s.canCheck, onClick: check }, 'Check'),
        s.locked ? null : el('button', { class: 'btn', disabled: s.index === s.list.length - 1, onClick: () => go(s.index + 1) }, 'Skip →'),
        el('span', { class: 'muted' }, 'Keys: 1-9 / A-F pick · Enter check/next · ← →'),
        opts.actionExtras ? opts.actionExtras(s) : null),
    ].filter(Boolean));
  };

  draw();
  const unbind = bindKeys({
    onOption: (i) => {
      const s = state();
      if (!s.q || s.locked) return;
      const next = togglePick({ question: s.q, picked: s.picked }, i);
      if (next) { draft = next; draw(); }
    },
    onEnter: () => { const s = state(); if (!s.q) return; if (s.locked) go(s.index + 1); else check(); },
    onPrev: () => { const s = state(); if (s.q) go(s.index - 1); },
    onNext: () => { const s = state(); if (s.q) go(s.index + 1); },
  });
  return { unbind, draw, resetDraft: () => { draft = []; } };
}
```

`web/js/views/practice.js`:
```js
import { mountDrill } from '../components/drill.js';
import { el } from '../dom.js';
import { checkPractice, setPracticeIndex } from '../progress.js';
import { store, update } from '../store.js';

export async function render(container) {
  const run = store.progress.practice;
  if (!run) { location.hash = '#/practice/setup'; return; }
  const list = store.bank.questions
    .filter((q) => q.number >= run.range[0] && q.number <= run.range[1])
    .sort((a, b) => a.number - b.number);
  if (!list.length) { location.hash = '#/practice/setup'; return; }

  const drill = mountDrill(container, {
    bankId: store.bankId,
    list: () => list,
    index: () => store.progress.practice.index,
    setIndex: (i) => update((p) => setPracticeIndex(p, i)),
    checked: (number) => store.progress.practice.picks[String(number)] ?? null,
    onCheck: (number, picked, correct) => update((p) => checkPractice(p, number, picked, correct, new Date().toISOString())),
    label: (s) => `Q ${s.index + 1} of ${s.list.length} · range ${run.range[0]}–${run.range[1]}`,
    empty: () => el('section', { class: 'card' }, 'No questions in this range.'),
  });
  return drill.unbind;
}
```

- [ ] **Step 3: Verify in the browser**

Run: `uv run serve --port 8010`. Then:
1. Home → Practice → range 1–12 → Start new. Q1 shows "#1", four options, Check disabled.
2. Press `3` → option C highlighted; press `Enter` → feedback "✓ Correct", option C green, vote bar "C 100%", "PDF answer: C". Press `Enter` → Q2.
3. Q9 (`Go to #` 9): the stem shows text, an image (SQL error screenshot), then text.
4. Q10 (Choose three): checkboxes; after 3 picks the remaining boxes are disabled; Check enabled only at exactly 3; pick B, C, D → "✗ Wrong — correct answer: B, D, E", B/D/E green, C red.
5. Navigate Prev to Q10 → still locked with feedback. Reload the page → Practice setup offers "Resume (Q x of 12, range 1–12)"; Home → stats show attempted/accuracy and `mistakes 1`.
6. `curl -s localhost:8010/api/banks/pde-2026-10/progress | head -c 400` shows `practice` and `questions` populated.
7. Range 340–342 → Q340 shows the amber "Disputed: the key follows the community vote (C); the PDF says B." note after Check.

- [ ] **Step 4: Commit**

```bash
git add web/js/components web/js/views/practiceSetup.js web/js/views/practice.js
git commit -m "feat(web): question card, feedback panel, shared drill loop, practice mode"
```

---

### Task 15: Review-mistakes view

**Files:**
- Replace placeholder: `web/js/views/review.js`

**Interfaces:**
- Consumes: `mountDrill` (Task 14), `mistakePool`, `recordAttempt`, `removeFromMistakes`, `clearMistakes`.
- Behaviour: pool sorted by number (re-read on every draw), session-only checked state, "Remove from mistakes" keeps the index (next pooled question slides in), "Clear all" confirms, empty state; jump-to and keyboard come from the drill.

- [ ] **Step 1: Write the view**

`web/js/views/review.js`:
```js
import { mountDrill } from '../components/drill.js';
import { el } from '../dom.js';
import { clearMistakes, mistakePool, recordAttempt, removeFromMistakes } from '../progress.js';
import { store, update } from '../store.js';

export async function render(container) {
  let index = 0;
  const session = new Map();            // number → picked (checked during this visit)
  let drill;

  const remove = (s) => {
    update((p) => removeFromMistakes(p, s.q.number));
    drill.resetDraft();
    drill.draw();                       // index is kept; the next pooled question slides in
  };
  const clearAll = (s) => {
    if (!confirm(`Remove all ${s.list.length} questions from the mistakes pool?`)) return;
    update((p) => clearMistakes(p));
    drill.draw();
  };

  drill = mountDrill(container, {
    bankId: store.bankId,
    list: () => mistakePool(store.progress).map((n) => store.byNumber.get(n)).filter(Boolean),
    index: () => index,
    setIndex: (i) => { index = i; },
    checked: (number) => session.get(number) ?? null,
    onCheck: (number, picked, correct) => {
      session.set(number, picked);
      update((p) => recordAttempt(p, number, picked, correct, new Date().toISOString()));
    },
    label: (s) => `${s.list.length} mistake${s.list.length === 1 ? '' : 's'} · ${s.index + 1} of ${s.list.length}`,
    toolbarExtras: (s) => el('button', { class: 'btn danger', onClick: () => clearAll(s) }, 'Clear all'),
    actionExtras: (s) => [el('span', { class: 'spacer' }), el('button', { class: 'btn', onClick: () => remove(s) }, 'Remove from mistakes')],
    empty: () => el('section', { class: 'card' },
      el('h2', {}, 'Review mistakes'),
      el('p', { class: 'muted' }, 'The pool is empty. Questions you answer wrong in Exam or Practice will appear here.'),
      el('a', { class: 'btn link', href: '#/' }, 'Home')),
  });
  return drill.unbind;
}
```

- [ ] **Step 2: Verify in the browser**

1. With the mistake from Task 14 (Q10) in the pool: Home shows "1 question to re-drill" → Review shows "1 mistake · 1 of 1", Q10.
2. Answer it correctly → "✓ Correct" but it stays in the pool (reload → still 1 mistake). Answer wrong in Practice two more questions (e.g. Q2, Q3 deliberately wrong) → Review shows "3 mistakes" in number order 2, 3, 10.
3. On Q2 click "Remove from mistakes" → the header reads "2 mistakes · 1 of 2" and Q3 is shown (index kept).
4. "Clear all" → confirm → empty state. Home shows `mistakes 0`.

- [ ] **Step 3: Commit**

```bash
git add web/js/views/review.js
git commit -m "feat(web): review-mistakes mode"
```

---

### Task 16: Exam setup, exam runner (timer, flags, navigator, auto-submit, resume)

**Files:**
- Create: `web/js/components/navigator.js`
- Replace placeholders: `web/js/views/examSetup.js`, `web/js/views/exam.js`

**Interfaces:**
- Consumes: `startExam`, `discardExam`, `setExamPick`, `toggleExamFlag`, `setExamCurrent`, `finishExam`; `fisherYates`, `sampleWithoutReplacement`; `remainingSeconds`, `formatClock`; `EXAM_DEFAULTS`, `EXAM_LIMITS`, `TIMER_WARN_S`; `flush`.
- Produces: `renderNavigator({items, current, onJump}) -> HTMLElement`; exam flow writing `active_exam` on every change and `exams[]` on finish; redirect to `#/exam/result/<id>`.

- [ ] **Step 1: Write the navigator and the views**

`web/js/components/navigator.js`:
```js
import { el } from '../dom.js';

export function renderNavigator({ items, current, onJump }) {
  return el('div', { class: 'navigator' }, items.map((it, i) => {
    const cls = ['nav-cell'];
    if (it.picked.length) cls.push('answered');
    if (it.flagged) cls.push('flagged');
    if (i === current) cls.push('current');
    return el('button', { class: cls.join(' '), type: 'button', title: `Question ${i + 1} (#${it.number})`, onClick: () => onJump(i) }, String(i + 1));
  }));
}
```

`web/js/views/examSetup.js`:
```js
import { EXAM_DEFAULTS, EXAM_LIMITS } from '../config.js';
import { el } from '../dom.js';
import { discardExam, startExam } from '../progress.js';
import { fisherYates, sampleWithoutReplacement } from '../shuffle.js';
import { store, update } from '../store.js';

export async function render(container) {
  const qs = store.bank.questions;
  const active = store.progress.active_exam;
  const count = el('input', { type: 'number', min: 1, max: qs.length, value: Math.min(EXAM_DEFAULTS.count, qs.length) });
  const minutes = el('input', { type: 'number', min: EXAM_LIMITS.minMinutes, max: EXAM_LIMITS.maxMinutes, value: EXAM_DEFAULTS.minutes });
  const err = el('p', { class: 'error-text' });

  const start = () => {
    const n = Number(count.value);
    const m = Number(minutes.value);
    if (!Number.isInteger(n) || n < 1 || n > qs.length) { err.textContent = `Question count must be between 1 and ${qs.length}.`; return; }
    if (!Number.isInteger(m) || m < EXAM_LIMITS.minMinutes || m > EXAM_LIMITS.maxMinutes) {
      err.textContent = `Minutes must be between ${EXAM_LIMITS.minMinutes} and ${EXAM_LIMITS.maxMinutes}.`;
      return;
    }
    const chosen = sampleWithoutReplacement(qs, n);
    const numbers = chosen.map((q) => q.number);
    const orders = chosen.map((q) => fisherYates(q.options.map((o) => o.letter)));
    update((p) => startExam(p, numbers, orders, m * 60, new Date().toISOString()));
    location.hash = '#/exam';
  };

  const discard = () => {
    if (!confirm('Discard the exam in progress? It will not be scored.')) return;
    update((p) => discardExam(p));
    render(container);
  };

  container.replaceChildren(el('section', { class: 'card' },
    el('h2', {}, 'Exam'),
    active ? el('div', { class: 'banner warn' }, 'An exam is already in progress. ',
      el('a', { class: 'btn', href: '#/exam' }, 'Resume it'), ' ',
      el('button', { class: 'btn danger', onClick: discard }, 'Discard')) : null,
    el('div', { class: 'form-row' }, el('label', {}, 'Questions', count), el('label', {}, 'Minutes', minutes)),
    el('p', { class: 'muted' }, `${qs.length} questions in this bank. Random draw, shuffled options, no feedback until you finish. Unanswered questions count as wrong.`),
    err,
    el('div', { class: 'actions' },
      el('button', { class: 'btn primary', disabled: !!active, onClick: start }, 'Start exam'),
      el('a', { class: 'btn link', href: '#/' }, 'Back'))));
}
```

`web/js/views/exam.js`:
```js
import { renderNavigator } from '../components/navigator.js';
import { renderQuestionCard, togglePick } from '../components/questionCard.js';
import { TIMER_WARN_S } from '../config.js';
import { el } from '../dom.js';
import { bindKeys } from '../keys.js';
import { finishExam, setExamCurrent, setExamPick, toggleExamFlag } from '../progress.js';
import { flush, store, update } from '../store.js';
import { formatClock, remainingSeconds } from '../timer.js';

export async function render(container) {
  if (!store.progress.active_exam) { location.hash = '#/exam/setup'; return; }
  let finished = false;

  const finish = async (auto) => {
    if (finished) return;
    finished = true;
    const active = store.progress.active_exam;
    update((p) => finishExam(p, active, store.byNumber, new Date().toISOString(), auto));
    await flush();
    location.hash = `#/exam/result/${encodeURIComponent(active.id)}`;
  };

  const first = store.progress.active_exam;
  if (remainingSeconds(first.started_at, first.duration_s) <= 0) { await finish(true); return; }

  const clock = el('span', { class: 'clock' });
  const tick = () => {
    const a = store.progress.active_exam;
    if (!a || finished) return;
    const s = remainingSeconds(a.started_at, a.duration_s);
    clock.textContent = formatClock(s);
    clock.classList.toggle('warn', s <= TIMER_WARN_S);
    if (s <= 0) finish(true);
  };
  const interval = setInterval(tick, 500);

  const state = () => {
    const a = store.progress.active_exam;
    const i = Math.min(Math.max(a.current, 0), a.items.length - 1);
    return { a, i, item: a.items[i], q: store.byNumber.get(a.items[i].number) };
  };
  const go = (i) => { const { a } = state(); if (i < 0 || i >= a.items.length) return; update((p) => setExamCurrent(p, i)); draw(); };
  const pick = (next) => { const { i } = state(); update((p) => setExamPick(p, i, next)); draw(); };
  const flag = () => { const { i } = state(); update((p) => toggleExamFlag(p, i)); draw(); };
  const confirmFinish = () => {
    const { a } = state();
    const unanswered = a.items.filter((it) => !it.picked.length).length;
    const msg = unanswered
      ? `${unanswered} question${unanswered === 1 ? ' is' : 's are'} unanswered and will count as wrong. Finish anyway?`
      : 'Finish the exam and see your results?';
    if (confirm(msg)) finish(false);
  };

  const draw = () => {
    if (finished || !store.progress.active_exam) return;
    const { a, i, item, q } = state();
    tick();
    container.replaceChildren(
      el('div', { class: 'toolbar' },
        el('span', { class: 'progress-label' }, `Q ${i + 1} / ${a.items.length}`),
        clock,
        el('span', { class: 'spacer' }),
        el('button', { class: `btn${item.flagged ? ' active' : ''}`, onClick: flag }, item.flagged ? '⚑ Flagged' : '⚐ Flag'),
        el('button', { class: 'btn danger', onClick: confirmFinish }, 'Finish')),
      q ? renderQuestionCard({ question: q, bankId: store.bankId, order: item.order, picked: item.picked, onPick: pick })
        : el('section', { class: 'card' }, `Question #${item.number} is missing from this bank.`),
      el('div', { class: 'actions' },
        el('button', { class: 'btn', disabled: i === 0, onClick: () => go(i - 1) }, '← Prev'),
        el('button', { class: 'btn primary', disabled: i === a.items.length - 1, onClick: () => go(i + 1) }, 'Next →'),
        el('span', { class: 'muted' }, 'Keys: 1-9 / A-F pick · F flag · Enter next · ← →')),
      renderNavigator({ items: a.items, current: i, onJump: go }));
  };
  draw();

  const unbind = bindKeys({
    onOption: (k) => { const { item, q } = state(); if (!q) return; const next = togglePick({ question: q, order: item.order, picked: item.picked }, k); if (next) pick(next); },
    onEnter: () => go(state().i + 1),
    onPrev: () => go(state().i - 1),
    onNext: () => go(state().i + 1),
    onFlag: flag,
  });
  return () => { clearInterval(interval); unbind(); };
}
```

- [ ] **Step 2: Verify in the browser**

1. Home → Exam → Questions 5, Minutes 2 → Start. Toolbar shows "Q 1 / 5" and "02:00" counting down; 5-cell navigator.
2. The displayed option letters are A–D but the texts are in a different order from Practice for the same `#` (shuffle). Pick with keys `1`–`4`, flag with `F` (cell gets an amber underline), `→` to move on.
3. Reload mid-exam → the same 5 questions, same option order, picks and flags intact; the clock continues from wall-clock time (not reset).
4. Home shows the "Resume exam in progress — x/5 answered" banner; Exam setup shows the warning with Resume/Discard and a disabled Start.
5. Let the timer reach 00:00 → auto-submit → results page (Task 17 placeholder shows "Coming soon" until then; the URL is `#/exam/result/<id>`).
6. Start another 3-question exam, answer 2, click Finish → confirm text mentions "1 question is unanswered" → OK → results route.
7. `curl -s localhost:8010/api/banks/pde-2026-10/progress | python3 -m json.tool | grep -c '"id"'` → at least 2 exams recorded; `active_exam` is `null`.

- [ ] **Step 3: Commit**

```bash
git add web/js/components/navigator.js web/js/views/examSetup.js web/js/views/exam.js
git commit -m "feat(web): exam mode with wall-clock timer, flags, navigator, resume and auto-submit"
```

---

### Task 17: Exam results view

**Files:**
- Replace placeholder: `web/js/views/examResult.js`
- Modify: `web/app.css` — scope the history colours so they do not bleed into the result summary: change the two rules `.pass { color: var(--ok); font-weight: 600; }` and `.fail { color: var(--bad); font-weight: 600; }` to `.history .pass { … }` and `.history .fail { … }` (same bodies). Without this, `<section class="result-summary pass">` turns the whole summary green/red and semibold.

**Interfaces:**
- Consumes: `PASS_PCT`, `formatClock`, `renderQuestionCard`, `renderFeedback`.
- Route param: `params[0]` = exam id (decoded by the router).

- [ ] **Step 1: Write the view**

`web/js/views/examResult.js`:
```js
import { renderFeedback } from '../components/feedback.js';
import { renderQuestionCard } from '../components/questionCard.js';
import { PASS_PCT } from '../config.js';
import { el } from '../dom.js';
import { store } from '../store.js';
import { formatClock } from '../timer.js';

const preview = (q) => {
  const t = q.stem.find((b) => b.type === 'text');
  return t ? t.text.slice(0, 90) + (t.text.length > 90 ? '…' : '') : '';
};

export async function render(container, [id]) {
  const exam = store.progress.exams.find((e) => e.id === id);
  if (!exam) {
    container.replaceChildren(el('section', { class: 'card' }, el('h2', {}, 'Exam not found'), el('a', { class: 'btn link', href: '#/' }, 'Home')));
    return;
  }
  let wrongOnly = false;
  const open = new Set();
  const pass = exam.pct >= PASS_PCT;

  const draw = () => {
    const rows = exam.items.map((it, i) => {
      if (wrongOnly && it.correct) return null;
      const q = store.byNumber.get(it.number);
      const status = it.correct ? '✓' : it.picked.length ? '✗' : '—';
      const expanded = open.has(i);
      return el('div', { class: `result-item ${it.correct ? 'ok' : 'bad'}` },
        el('button', { class: 'result-row', onClick: () => { if (expanded) open.delete(i); else open.add(i); draw(); } },
          el('span', { class: 'status' }, status),
          el('span', {}, `Q ${i + 1} · #${it.number}`),
          el('span', { class: 'muted' }, q ? preview(q) : '(question missing from bank)'),
          el('span', { class: 'chev' }, expanded ? '▾' : '▸')),
        expanded && q ? el('div', { class: 'result-detail' },
          renderQuestionCard({ question: q, bankId: store.bankId, picked: it.picked, locked: true, reveal: q.answer }),
          renderFeedback({ question: q, picked: it.picked })) : null);
    });

    container.replaceChildren(
      el('section', { class: `card result-summary ${pass ? 'pass' : 'fail'}` },
        el('h2', {}, `${exam.score} / ${exam.total} · ${exam.pct}%`),
        el('p', {}, el('strong', {}, pass ? 'PASS' : 'FAIL'), ` (pass line ${PASS_PCT}%) · time used ${formatClock(exam.time_used_s)} of ${formatClock(exam.duration_s)}`,
          exam.auto_submitted ? ' · auto-submitted when time ran out' : ''),
        el('p', { class: 'muted' }, `Finished ${new Date(exam.finished_at).toLocaleString()}`),
        el('div', { class: 'actions' },
          el('a', { class: 'btn link', href: '#/' }, 'Home'),
          el('a', { class: 'btn', href: '#/exam/setup' }, 'New exam'),
          el('label', { class: 'toggle' }, el('input', { type: 'checkbox', checked: wrongOnly, onChange: (e) => { wrongOnly = e.target.checked; draw(); } }), 'wrong only'))),
      el('section', { class: 'results' }, rows));
  };
  draw();
}
```

- [ ] **Step 2: Verify in the browser**

1. Open the results of the auto-submitted exam from Task 16: header shows `score / total · pct%`, FAIL/PASS against 70 %, time used equals the full duration, and "auto-submitted when time ran out".
2. Each row shows ✓ / ✗ / —; expanding a wrong row shows the question in **PDF order** (A–D as in Practice, not the shuffled order), your pick in red, the key in green, vote bars and PDF answer.
3. "wrong only" hides correct rows. "Home" → the history table lists the exams; clicking a row opens its results. A bogus URL `#/exam/result/nope` shows "Exam not found".
4. Review mode now contains the exam's wrong + unanswered questions.

- [ ] **Step 3: Commit**

```bash
git add web/js/views/examResult.js web/app.css
git commit -m "feat(web): exam results with per-question review"
```

---

### Task 18: README, smoke checklist, final verification

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the README**

`README.md`:
````markdown
# PDF Exam Simulator

Local, single-user exam simulator fed by ExamTopics-style PDF dumps. Three modes: **Exam** (timed, random draw, shuffled options, results at the end), **Practice** (range in PDF order, instant feedback), **Review mistakes** (re-drill everything you ever got wrong until you remove it).

Design: `docs/superpowers/specs/2026-10-09-pdf-exam-simulator-design.md`.

## Setup

```bash
uv sync                      # Python 3.12 (pinned in .python-version), installs pymupdf/fastapi/uvicorn
```

## 1. Parse a PDF into a question bank

```bash
uv run parse-pdf source/pde_349.pdf --id pde-2026-10 --title "Professional Data Engineer (2026-10)" --strict
```

Writes `banks/pde-2026-10/questions.json` and `banks/pde-2026-10/images/*.png`, then prints a validation report (counts, disputed keys, anomalies). `--strict` exits non-zero if a question has no options or no answer. Any number of banks can live in `banks/`; the app lets you switch between them.

Answer key: top community vote; ties broken by the PDF's `Correct Answer`; questions without vote data use `Correct Answer`. Questions where these disagree are marked *disputed* and the feedback panel explains which rule applied.

## 2. Run the app

```bash
uv run serve                 # http://127.0.0.1:8000 — opens your browser
uv run serve --port 8010 --no-browser
```

Progress is stored per bank in `data/progress/<bank-id>.json` (plain JSON, atomic writes — back it up or edit it by hand). `source/`, `banks/` and `data/` are gitignored.

Keyboard: `1–9` / `A–F` pick an option · `Enter` check / next · `←` `→` previous / next · `F` flag (exam).

## Tests

```bash
uv run pytest                # parser + server (the real-PDF integration test skips if source/pde_349.pdf is absent)
npm test                     # pure web logic via node --test
```

## Manual smoke checklist

1. `uv run parse-pdf … --strict` → `errors: none`, 349 questions.
2. `uv run serve` → Home shows the bank, stats and three mode cards.
3. Exam: 5 questions / 2 minutes; answer one multi-select (e.g. a "Choose three") and one image question; reload mid-exam (state intact); let the timer expire → results show FAIL, auto-submitted, wrong rows expandable in PDF order.
4. Practice: range 1–12, Check gives instant feedback; Q9 shows an inline image; Q10 caps picks at 3.
5. Review: pool lists the exam's wrong/unanswered questions; "Remove from mistakes" drops one; "Clear all" empties it.
6. Add a second bank (`parse-pdf` with another `--id`) → the Home dropdown switches banks with separate progress.
````

- [ ] **Step 2: Full verification**

Run: `uv run pytest -q && npm test`
Expected: all Python tests pass (parser + server + smoke) and `# fail 0` for node.

Run: `uv run parse-pdf source/pde_349.pdf --id pde-2026-10 --title "Professional Data Engineer (2026-10)" --strict && uv run serve --no-browser --port 8010`
Walk the README smoke checklist end to end in the browser. Stop the server.

Run: `git status --short`
Expected: only `README.md` modified; `banks/`, `data/`, `source/`, `scratch/` untracked-but-ignored.

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README with setup, usage and smoke checklist"
```

---

## Plan self-review (done at authoring time)

- **Spec coverage:** §3 layout → T1; §4.1 → T3; §4.2 → T4 (incl. multi-entry vote lines found in Q18/116/137); §4.3 → T5; §4.4 → T2/T6/T8; §4.5 → T7/T8; §5 → T9/T10; §6 → T12/T13 (store); §7 Home → T13, Exam setup/run → T16, Result → T17, Practice → T14, Review → T15, feedback panel → T14, keyboard → T13 (`keys.js`); §8 parser errors → T6/T7/T8, server errors → T9/T10, client errors → T13 (error card, sticky toast + backoff, `beforeunload`), expired exam on load → T16; §9 tests → T2–T12; §10 build order followed.
- **Deviations from the spec, all intentional:** Practice and Review share `components/drill.js` instead of each owning a copy of the drill loop; reducers live in `progress.js` (tested as `progress.test.js`) and `store.js` holds only state + saving, so the pure part is node-testable; `keys.js` is a separate module; images are written as `.png` after conversion by PyMuPDF, exactly as §4.1 says.
- **Type consistency checked:** `Vote(letters, pct)` everywhere; `RawQuestion(number, page, …)` positional order used in tests; `ImageWriter.writer_for(number)` returns the callable passed to `assemble_blocks`/`build_question`; `scoreExam` item shape `{number, order, picked, correct}` is what `finishExam` stores and `examResult` reads; `store.byNumber` is a `Map` keyed by `number`; all views export `async render(container, params)`.
