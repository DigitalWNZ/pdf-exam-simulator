# PDF Exam Simulator

Local, single-user exam simulator fed by ExamTopics-style PDF dumps. Four modes: **Exam** (timed, random draw, shuffled options, results at the end), **Practice** (range in PDF order, instant feedback), **Review mistakes** (re-drill everything you ever got wrong until you remove it), **Future review** (re-drill the questions you ticked *Mark for future review* until you remove them).

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

- Mislabeled options are repaired generically: an option printed with a wrong letter (this PDF prints Q224's third option as `G.`) is renumbered when the question's `Correct Answer` or votes corroborate it, and the report lists it under `relabeled option letters`.
- On this machine `uv` lives in pyenv's Python 3.12.6, which `.python-version` pins — run `uv` commands from the repo root (elsewhere pyenv selects a Python without `uv`).

## 2. Run the app

```bash
uv run serve                 # http://127.0.0.1:8000 — opens your browser
uv run serve --port 8010 --no-browser
```

Progress is stored per bank in `data/progress/<bank-id>.json` (plain JSON, atomic writes — back it up or edit it by hand). `source/`, `banks/` and `data/` are gitignored.

Keyboard: `1–9` / `A–F` pick an option · `Enter` check / next · `←` `→` previous / next · `F` flag (exam) · `M` mark for future review (practice / review).

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
7. Practice: tick *Mark for future review* on Q3 → Home card shows "1 question marked" → Future review drills Q3 with Check/feedback → "Remove from list" → empty state.
8. Open a past exam result, expand a question, tick the box → it appears in Future review.
9. Reload the page → still marked; `data/progress/<bank>.json` contains `"marked": true`.
10. Future review with 2+ questions: "Clear all" → confirm → empty state; `M` toggles the mark in Practice.
