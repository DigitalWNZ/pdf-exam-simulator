# PDF Exam Simulator — Design Spec

**Date:** 2026-10-09
**Status:** Draft for user review
**Source material:** `source/pde_349.pdf` — ExamTopics-style dump, Professional Data Engineer, 349 questions, 277 pages, text layer present (no OCR needed).

## 1. Goal

A local, single-user, browser-based exam simulator whose question bank is produced by parsing ExamTopics-style PDFs. The first bank is the 349-question Professional Data Engineer dump; the parser and app must accept further PDFs from the same source without code changes.

### Non-goals

- Multi-user, authentication, cloud sync, mobile-first layout.
- Explanations/discussion text (the PDF is the `without_discussion` edition).
- Editing questions in the UI.
- Persistent bookmarks (only an in-exam, session-scoped "flag").

## 2. Decisions (from the grilling session)

| Topic | Decision |
|---|---|
| Relationship to `vce_simulator` | None. Fresh standalone project. |
| Modes | **Exam**, **Practice**, **Review mistakes** |
| Answer key | Top community vote. Ties broken by the PDF's `Correct Answer`. No vote data → `Correct Answer`. Both are always shown in feedback, with vote percentages. |
| Multi-select | All-or-nothing. Checkboxes, "Choose N" hint, selection capped at N. |
| Exam parameters | Default 50 questions / 120 minutes, both adjustable on the setup screen. Uniform random draw without replacement from the whole bank. |
| Practice | Pick a question range (default all), sequential order. Select → **Check** → instant feedback → Next. Free back/forward navigation. |
| Review pool | Every question ever answered wrong, in any mode. Stays until manually removed (per question or clear-all). Answering correctly does **not** remove it. |
| Banks | Parser is a reusable CLI. App lists all banks and switches between them; each bank has its own progress file. |
| Option shuffling | Exam mode only. Practice/Review keep the PDF's A–D order. |
| Devices | Laptop browser on `localhost`. Responsive layout is nice-to-have. |
| Persistence | Plain JSON file on disk per bank, written by a small local server. Must survive browser data loss. |
| Architecture | Python end-to-end: PyMuPDF parser + FastAPI server + vanilla-JS static UI, no build step, managed by `uv`. |

Decisions made by the implementer (cheap to change, flagged for review):

1. Pass line is **70 %** (Google does not publish one); a constant in `web/js/config.js`.
2. Unanswered exam questions count as wrong **and** enter the mistakes pool.
3. Exam mode has a session-scoped **Flag** per question and a navigator grid, mirroring the real exam UI.
4. Keyboard shortcuts: `1–6`/`A–F` toggle options, `Enter` = Check/Next, `←`/`→` = Prev/Next, `F` = flag (exam only).
5. Progress is saved as a whole-document `PUT`; with two tabs open the last write wins.
6. The post-exam review shows options in the **original PDF order** (the shuffled order is only used while the exam is running).
7. In Practice, a checked question is locked for that run (no re-answer); starting a new run resets it.

## 3. Repository layout & runtime

```
pdf_exam_simulator/
├── pyproject.toml                 # uv project; deps: pymupdf, fastapi, uvicorn[standard]; dev: pytest, httpx
├── README.md                      # run instructions + manual UI smoke checklist
├── exam_sim/
│   ├── __init__.py
│   ├── parser/
│   │   ├── cli.py                 # `parse-pdf` entry point
│   │   ├── extract.py             # PDF → ordered stream of Line/Image items (PyMuPDF)
│   │   ├── blocks.py              # stream → raw question blocks (state machine)
│   │   ├── key.py                 # answer-key rule
│   │   ├── model.py               # dataclasses + JSON serialisation
│   │   └── report.py              # validation report, --strict
│   └── server/
│       ├── app.py                 # FastAPI app, routes, static mounts
│       ├── storage.py             # bank discovery, atomic progress read/write
│       └── cli.py                 # `serve` entry point (opens browser)
├── web/
│   ├── index.html
│   ├── app.css
│   └── js/
│       ├── main.js                # bootstrap + hash router
│       ├── config.js              # PASS_PCT = 70, defaults
│       ├── api.js                 # fetch wrappers
│       ├── store.js               # progress state, debounced save, dirty flag
│       ├── grading.js             # pure: isCorrect, scoreExam
│       ├── shuffle.js             # pure: fisherYates, sampleWithoutReplacement
│       ├── timer.js               # pure: remainingSeconds(startedAt, durationS, now)
│       ├── components/
│       │   ├── questionCard.js    # stem/options/choose-N/cap; original or shuffled order
│       │   ├── feedback.js        # key, PDF answer, vote bars, disputed badge
│       │   └── navigator.js       # exam grid
│       └── views/
│           ├── home.js, examSetup.js, exam.js, examResult.js,
│           ├── practiceSetup.js, practice.js, review.js
├── banks/<bank_id>/questions.json + images/*.png     # generated — gitignored
├── data/progress/<bank_id>.json                      # generated — gitignored
├── source/*.pdf                                      # input PDFs — gitignored
├── tests/
│   ├── parser/  test_extract.py test_blocks.py test_key.py test_real_pdf.py
│   ├── server/  test_api.py test_storage.py
│   └── web/     grading.test.js shuffle.test.js timer.test.js store.test.js
└── docs/superpowers/specs/2026-10-09-pdf-exam-simulator-design.md
```

Commands:

```bash
uv sync
uv run parse-pdf source/pde_349.pdf --id pde-2026-10 --title "Professional Data Engineer (2026-10)" [--strict] [--out banks]
uv run serve [--port 8000] [--banks banks] [--data data] [--no-browser]
uv run pytest
node --test tests/web
```

Only code, tests, docs and config are committed. Dump content (`source/`, `banks/`, `data/`) is gitignored.

## 4. Parser

### 4.1 Extraction (`extract.py`)

- Open with PyMuPDF; for each page call `page.get_text("dict")`.
- Emit one ordered stream of items across all pages, in reading order (`page.get_text("dict", sort=True)`; the layout is single-column):
  - `Line(text, page)` — one per text line (spans joined, whitespace collapsed).
  - `Image(xref, page, width, height)` — one per image block.
- Noise filters, all generic:
  - **Watermark:** any image xref that appears on more than 50 % of pages is dropped. (Here: xref 657, present on all 277 pages.)
  - **Footer:** lines matching `^\[\d{6}\]$` or `^https?://\S+$`.
  - **Preamble:** everything before the first `^Question #\d+$` line (here: the page-1 title).
  - **Tiny images:** images with width or height < 20 px are dropped (9×6 px bullet artefacts seen on ~10 pages).
- Image bytes are extracted via `doc.extract_image(xref)` and written as `images/q{number:03d}_{k}.png` (converted to PNG if not already) once the owning question is known.

### 4.2 Block parsing (`blocks.py`)

A state machine over the item stream. States: `STEM → OPTIONS → ANSWER → VOTES`.

| Trigger (line regex) | Action |
|---|---|
| `^Question #(\d+)$` | Close the current question (if any), start a new one. |
| `^Topic (\d+)$` immediately after the header | Record topic. |
| `^([A-Z])\.(\s+(.*))?$` **and** the letter equals the next expected letter (A, then B, …) | Start a new option. Letters out of sequence are treated as ordinary text. This prevents a wrapped stem line such as `…replica in region B.` from becoming an option. |
| `^Most Voted$` (also accepted as a trailing ` Most Voted` suffix on an option line) | Tag the most recently opened option `most_voted = True`. |
| `^Correct Answer:\s*([A-Z]+)$` | Record `pdf_answer` as a list of letters; leave `OPTIONS`. |
| `^Community vote distribution$` | Enter `VOTES`. |
| one or more `([A-Z]+)\s*\((\d+)%\)` entries filling a line while in `VOTES` (the PDF packs minority entries together, e.g. `BCE (5%)CDE (3%)ACD (3%)` in Q18/Q116/Q137) | Append one `{letters, pct}` per entry, in order. |
| `Image` item | Append an image block to the stem (state `STEM`) or to the open option (state `OPTIONS`). Images after `Correct Answer` are discarded with a warning. |
| anything else | Append to the current text target (stem or open option). |

Text assembly: consecutive lines are joined with a single space, except that a newline is preserved before a line matching `^\d+\.\s` (numbered procedure steps, e.g. Q321), and before/after an image block. Leading/trailing whitespace is trimmed; empty text blocks are dropped.

Multi-select detection: `select_count = len(answer)` (see 4.3). The stem regex `\((Choose|Select)\s+(two|three|\d)\)` is only used by the validation report to cross-check.

### 4.3 Answer key (`key.py`)

```python
def resolve_key(pdf_answer: list[str], votes: list[Vote]) -> KeyResult:
    if not votes:
        return KeyResult(answer=pdf_answer, source="pdf", disputed=False)
    top = votes[0].pct
    tied = [v.letters for v in votes if v.pct == top]
    if len(tied) == 1:
        answer = tied[0]
        return KeyResult(answer, source="votes", disputed=(sorted(answer) != sorted(pdf_answer)))
    answer = pdf_answer if any(sorted(t) == sorted(pdf_answer) for t in tied) else tied[0]
    return KeyResult(answer, source="votes_tiebreak_pdf" if answer == pdf_answer else "votes_tie_first", disputed=True)
```

Known outcomes on this PDF: Q340/Q342/Q347 → key follows the 100 % community vote, `disputed`; Q109/Q216/Q217/Q270/Q328 → tie broken by `pdf_answer`, `disputed`; Q320 → key `D` (community) vs PDF `BD`, `disputed`; Q321–Q343 without vote data → `source="pdf"`.

### 4.4 Output schema (`banks/<id>/questions.json`)

```json
{
  "schema_version": 1,
  "bank": {
    "id": "pde-2026-10",
    "title": "Professional Data Engineer (2026-10)",
    "source_pdf": "pde_349.pdf",
    "parsed_at": "2026-10-09T08:00:00Z",
    "question_count": 349
  },
  "questions": [
    {
      "number": 9,
      "topic": "1",
      "stem": [
        {"type": "text", "text": "Your company is using WILDCARD tables … the following error:"},
        {"type": "image", "src": "images/q009_1.png", "w": 709, "h": 208},
        {"type": "text", "text": "Which table name will make the SQL statement work correctly?"}
      ],
      "options": [
        {"letter": "A", "content": [{"type": "text", "text": "'bigquery-public-data.noaa_gsod.gsod'"}]},
        {"letter": "B", "content": [{"type": "text", "text": "bigquery-public-data.noaa_gsod.gsod*"}]}
      ],
      "answer": ["D"],
      "select_count": 1,
      "pdf_answer": ["D"],
      "votes": [{"letters": ["D"], "pct": 63}, {"letters": ["B"], "pct": 38}],
      "answer_source": "votes",
      "disputed": false
    }
  ]
}
```

- `number` is the PDF's question number and is the stable identifier used by progress files.
- `stem` and `options[].content` are ordered lists of content blocks so images keep their position (Q9 inline image; Q243 image-only options).
- `answer`, `pdf_answer`, `votes[].letters` are sorted lists of letters.
- Image `src` is relative to the bank directory; the server serves it at `/banks/<id>/images/…`.

### 4.5 Validation report (`report.py`)

Printed after every run:

- question count, min/max/missing/duplicate numbers;
- histogram of options per question; count of image blocks;
- questions with 0 options, no `pdf_answer`, `answer` letters not present in options, `select_count` disagreeing with a `(Choose N)` hint;
- list of `disputed` questions with key vs PDF answer;
- count of questions without vote data;
- any unrecognised line after `Correct Answer` (possible layout drift), with page numbers.

`--strict` exits with status 1 if any question has 0 options, no answer, or answer letters not in its options. Without `--strict`, such questions are still written but flagged in the report; the app shows them normally (they can be hand-fixed in the JSON).

## 5. Server

FastAPI app, run with uvicorn on `127.0.0.1:<port>`.

| Method & path | Behaviour |
|---|---|
| `GET /api/banks` | Scan `<banks>/*/questions.json`; return `[{id, title, question_count}]` sorted by title. |
| `GET /api/banks/{id}` | Return the bank JSON. 404 if missing. |
| `GET /api/banks/{id}/progress` | Return the progress document, or the empty default if the file does not exist. |
| `PUT /api/banks/{id}/progress` | Body = full progress document. Validate `version == 1` and `bank_id == id`; set `updated_at`; write atomically; return `{"ok": true, "updated_at": …}`. |
| `GET /banks/{id}/images/{file}` | Static files from the bank directory. |
| `GET /` and `/{static}` | Static files from `web/`. |

Rules:

- `id` must match `^[a-z0-9][a-z0-9._-]{0,63}$`, else 400. Paths are resolved under the banks/data roots and rejected if they escape them.
- Atomic write: write to `<file>.tmp` in the same directory, `fsync`, `os.replace`.
- Corrupt progress JSON on read: rename it to `<file>.corrupt-<timestamp>`, log a warning, return the empty default. The app keeps working; nothing is silently overwritten.
- Request bodies over 20 MB are rejected (413) as a sanity limit.
- `serve` opens the browser after the server is listening unless `--no-browser`.

## 6. Progress document (`data/progress/<bank_id>.json`)

```json
{
  "version": 1,
  "bank_id": "pde-2026-10",
  "updated_at": "2026-10-09T08:12:00Z",
  "questions": {
    "17": {
      "attempts": 3, "correct": 2, "wrong": 1,
      "last_result": "wrong", "last_answer": ["B"], "last_at": "2026-10-09T08:10:00Z",
      "in_mistakes": true
    }
  },
  "exams": [
    {
      "id": "2026-10-09T07:00:00Z",
      "started_at": "2026-10-09T07:00:00Z", "finished_at": "2026-10-09T08:05:00Z",
      "duration_s": 7200, "time_used_s": 3900, "auto_submitted": false,
      "items": [{"number": 17, "order": ["C", "A", "D", "B"], "picked": ["B"], "correct": false}],
      "score": 41, "total": 50, "pct": 82.0
    }
  ],
  "active_exam": null,
  "practice": {"range": [1, 349], "index": 11, "picks": {"3": ["C"], "4": ["A"]}}
}
```

- `active_exam` has the same shape as an `exams[]` entry minus the results fields, plus `current` (index) and `items[].flagged`. It is written on every change (debounced 500 ms) so a refresh or restart resumes the exam with the same questions, option order, picks, flags and clock.
- Per-question stats are updated by exactly three events: **exam finished** (each item), **practice Check**, **review Check**. Each event increments `attempts` and `correct`/`wrong`, sets `last_*`, and on a wrong result sets `in_mistakes = true`. Nothing else sets or clears `in_mistakes` except the explicit "Remove from mistakes" and "Clear all" actions.
- `practice.picks` holds checked answers for the current run; "Start new" resets `practice`, "Resume" keeps it.
- All timestamps are UTC ISO-8601 strings produced by the client; `updated_at` is set by the server.

## 7. Web UI

Hash-routed single page; the selected bank id is remembered in `localStorage` (UI preference only — never progress).

| Route | Screen |
|---|---|
| `#/` | **Home** — bank dropdown; stats (questions, attempted, accuracy, mistakes count); "Resume exam" banner when `active_exam` exists; three cards: Exam / Practice / Review (with pool count); exam history table (date, score %, pass/fail, time used) linking to results. |
| `#/exam/setup` | Count (1…bank size, default 50) and minutes (1…600, default 120). Start → draws questions, shuffles each question's options, writes `active_exam`. |
| `#/exam` | Top bar: "Q 12 / 50", countdown `mm:ss` (red under 5 min), Flag toggle, Finish. Question card with display letters A… in shuffled order, radio or checkbox, "Choose N" hint, cap at N. Prev/Next and navigator grid (unanswered / answered / flagged / current). Finish shows a confirm with the unanswered count. At 0:00 the exam auto-submits. No feedback during the exam. |
| `#/exam/result/<id>` | Score (e.g. 41/50 · 82 %), PASS/FAIL against `PASS_PCT`, time used, auto-submitted badge. List of items with ✓/✗/— and a "wrong only" filter; expanding an item shows the full question in original PDF order with the user's pick, the key, and the shared feedback panel. |
| `#/practice/setup` | From/To (default 1…N), Start new, Resume (shows "Q x of range") when a run exists. |
| `#/practice` | "Q 12 of 50 · #12". Card in original order. Check (enabled only when exactly `select_count` options are picked) → feedback panel, question locked. Prev/Next, jump-to-number input. Position persisted. |
| `#/review` | Header "23 mistakes · Clear all" (confirm). Drill through the pool sorted by number, same Check/feedback flow (Check requires exactly `select_count` picks). Each question has "Remove from mistakes"; removing keeps the current index so the next pooled question slides in. Jump-to-number input. Position is not persisted — the drill starts at the first pooled question. Empty state when the pool is empty. |

Shared **feedback panel**: Correct/Wrong banner; options coloured (key green, wrong picks red); vote bars ("C 83 % · B 11 % · A 6 %"); "PDF answer: C"; when `disputed`, an amber badge explaining which rule applied ("Key follows community vote; PDF says B" / "Tie — broken by PDF answer").

Exam internals: question draw uses `sampleWithoutReplacement`; per-question `order` is a Fisher–Yates permutation of the option letters stored in `active_exam`; display label = position (A, B, …), grading maps back to original letters. Remaining time is computed from `started_at + duration_s − now` (wall clock), never from an accumulating interval, so sleep/refresh cannot desynchronise it. If `active_exam` is already expired when the app loads, it is auto-submitted immediately with the picks on record.

Styling: one `app.css`, system font stack, content column max-width 860 px, light theme, images `max-width: 100 %`. No CSS framework.

## 8. Error handling

| Layer | Condition | Behaviour |
|---|---|---|
| Parser | Image cannot be extracted | Warning; a text block `[image missing]` is written in its place. |
| Parser | Question with 0 options / no answer / answer letter not among options | Reported; exit 1 under `--strict`, else written and flagged. |
| Parser | Unrecognised lines after `Correct Answer` | Reported with page numbers (layout drift signal). |
| Server | Bad bank id / path escape | 400. |
| Server | Unknown bank | 404. |
| Server | Corrupt progress file | Backed up as `.corrupt-<ts>`, empty default returned, warning logged. |
| Server | Write failure | 500 with message; the temp file is removed; the previous file is untouched. |
| Client | Bank list or bank fetch fails | Error screen with Retry and the hint "run `uv run serve`". |
| Client | Progress save fails | Sticky toast "Progress not saved — retrying…"; retry with exponential backoff (1 s → 30 s); `beforeunload` warns while dirty. |
| Client | Invalid setup inputs | Inline validation; Start disabled. |

## 9. Testing

- **Parser unit tests** (no PDF needed): `test_extract.py` for noise filters on synthetic item streams; `test_blocks.py` for wrapped lines, numbered steps, out-of-sequence letters, `Most Voted` tagging, votes parsing, images in stem/options, missing vote section; `test_key.py` as a table of the rule in §4.3.
- **Parser integration test** (`test_real_pdf.py`, skipped if `source/pde_349.pdf` is absent): 349 questions, numbers 1…349 with no gaps; Q1 → `["C"]`; Q10 → `["B","D","E"]`, `select_count 3`; Q236 has exactly 4 options; Q243 has 4 options whose content is a single image each; Q9 stem is `text, image, text`; Q340 key `["C"]`, disputed; Q328 key `["A"]`, source `votes_tiebreak_pdf`; Q321 source `pdf`; no block text contains `zhangxuetu` or `[202610]`; every question's option letters are `A, B, C, …` in sequence; every `answer` letter exists in `options`.
- **Server tests** (`pytest` + `TestClient`, temp dirs): bank listing, bank fetch, default progress, PUT→GET round-trip, no `.tmp` left behind, corrupt-file backup, 400 on bad id, 404 on unknown bank, 413 on oversize body.
- **Web tests** (`node --test`, pure modules only): `grading` (set equality, empty pick, multi-select), `shuffle` (permutation property, sample size/uniqueness), `timer` (remaining seconds, expiry), `store` reducers (stat updates for the three events; mistakes pool add/remove/clear; unanswered → wrong + pool).
- **Manual smoke checklist** in README: parse → serve → run a 5-question/2-minute exam including a multi-select and an image question → refresh mid-exam → let the timer expire → check results → practice a range → review mistakes → remove one → clear all → switch bank.

## 10. Build order (for the implementation plan)

1. Project scaffold (`pyproject.toml`, `uv sync`, package skeletons, test runners).
2. Parser: extract → blocks → key → model/JSON → report/CLI; unit tests first, then the real-PDF integration test; generate `banks/pde-2026-10`.
3. Server: storage + API + static mounts; tests.
4. Web: config/api/store/pure modules with tests → question card + feedback → Home → Practice → Review → Exam (setup, run, result).
5. README, smoke checklist, final end-to-end pass.
