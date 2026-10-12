# Future-Review List ("Mark for future review") — Design Spec

**Date:** 2026-10-11
**Status:** Approved in brainstorming; awaiting user review of this document
**Builds on:** `2026-10-09-pdf-exam-simulator-design.md` (the base spec). This spec replaces the base spec's non-goal "Persistent bookmarks".

## 1. Goal

Let the user tick a **"Mark for future review"** checkbox on any question and later drill through the marked questions in a dedicated screen, removing them one by one or all at once — exactly the workflow that already exists for the mistakes pool. The list must be persisted on disk and survive browser data loss.

### Non-goals

- Marking during a running exam (the session-scoped ⚐ Flag stays as it is).
- Notes / tags / multiple lists.
- Automatic removal on a correct answer.
- Changing the server or the progress API.

## 2. Decisions

| Topic | Decision |
|---|---|
| Where the checkbox appears | Practice, Review mistakes, Exam results (expanded question), and the Future review screen itself. **Not** during a running exam. |
| Leaving the list | Only by explicit action: untick the checkbox, **Remove from list**, or **Clear all**. Answering correctly does not remove it. |
| Drill behaviour | Same as Review mistakes: pick → Check → feedback → Next. Attempts count toward stats; a wrong answer also enters the mistakes pool. |
| Storage | A per-question `marked: true` flag inside the existing progress document, mirroring `in_mistakes`. One document per bank, so the list is per bank. No server changes. |

Implementer picks (cheap to change): screen name **Future review**; route `#/marked`; keyboard shortcut `M`; button text **Remove from list**; Home mode-card grid becomes 2×2.

Related: adding a note to a question (see `2026-10-12-question-notes-design.md`) also marks it; removing a question from this list never deletes its note.

## 3. Data model (`web/js/progress.js`)

The per-question stat gains one boolean:

```json
"questions": {
  "17": {
    "attempts": 3, "correct": 2, "wrong": 1,
    "last_result": "wrong", "last_answer": ["B"], "last_at": "2026-10-09T08:10:00Z",
    "in_mistakes": true,
    "marked": true
  }
}
```

- `EMPTY_STAT` gets `marked: false`.
- A question that was never attempted but is marked gets a stat entry `{ ...EMPTY_STAT, marked: true }` (`attempts: 0`). `overallStats` already counts only entries with `attempts > 0`, so Home's *attempted* / *accuracy* stats are unaffected.
- Progress files written before this change have no `marked` key; a missing key means unmarked. `version` stays `1`.
- Only the reducers below set or clear `marked`. `recordAttempt`, `removeFromMistakes`, `clearMistakes` and the exam/practice reducers spread the previous stat and therefore preserve it.

New pure reducers / selectors (never mutate; return the same object when nothing changes, like `removeFromMistakes`):

| Function | Behaviour |
|---|---|
| `setMarked(p, number, marked)` | Set the flag. Creates the stat entry from `EMPTY_STAT` if absent. Returns `p` unchanged if the flag already has that value (including "unmark a question with no entry"). |
| `clearMarked(p)` | Set `marked: false` on every entry that has it. |
| `markedPool(p)` | Numbers with `marked === true`, ascending. |
| `isMarked(p, number)` | Boolean convenience for the checkbox. |

Persistence is unchanged: every change goes through `store.update(reducer)` → debounced whole-document `PUT /api/banks/{id}/progress` → atomic write to `data/progress/<bank_id>.json`. Save failures surface through the existing sticky "Progress not saved — retrying…" toast and retry loop.

## 4. Web UI

### 4.1 `components/markToggle.js` (new)

`renderMarkToggle({ number, onChange = () => {} })` returns

```html
<label class="toggle"><input type="checkbox"> Mark for future review</label>
```

- `checked` is read from `isMarked(store.progress, number)` at render time.
- On change: `update((p) => setMarked(p, number, input.checked))`, then `onChange()` so the host view redraws itself (all views are redraw-on-change; the toggle never redraws anything itself).
- It depends only on `store`, `progress.js` and `dom.js`.

### 4.2 `components/questionCard.js`

`renderQuestionCard` accepts an optional `headExtras` node (or array). When given, the header renders `#17 · Choose 2 · <spacer> · headExtras`. `el()` drops `null`/`false` children, so callers can pass `null`. The running Exam passes nothing and is visually unchanged.

### 4.3 `components/drill.js`

Two new optional options:

- `headExtras(s)` → node, forwarded to `renderQuestionCard` on every draw.
- `onMark(s)` — called when the user presses `M` (only when a question is shown). As with `toolbarExtras`/`actionExtras` handlers today, **the view's handler is responsible for calling `drill.draw()`**; drill does not redraw on its own after `onMark`.

Views that need `drill` inside their option callbacks use the `let drill; … drill = mountDrill(…)` pattern already used by `review.js`.

### 4.4 `keys.js`

`bindKeys` gains `onMark`: `m`/`M` → `onMark()` (when provided; otherwise the key is ignored as today). `M` does not collide with option letters `A–I` or `F`. Keyboard hint text in the drill action row becomes `Keys: 1-9 / A-F pick · Enter check/next · ← → · M mark`.

### 4.5 Views

| View | Change |
|---|---|
| `views/practice.js` | `headExtras: (s) => renderMarkToggle({ number: s.q.number, onChange: () => drill.draw() })` and `onMark: (s) => { update((p) => setMarked(p, s.q.number, !isMarked(p, s.q.number))); drill.draw(); }`. Marking never touches the unchecked draft selection. |
| `views/review.js` | Same as Practice. |
| `views/marked.js` (**new**, route `#/marked`, title "Future review") | A near-copy of `review.js` wired to `markedPool`. Label: `N marked · i of N`. Toolbar: **Clear all** → `confirm("Remove all N questions from the future-review list?")` → `clearMarked`. One `remove(s)` function — `update((p) => setMarked(p, s.q.number, false)); drill.resetDraft(); drill.draw();` (index kept; the next marked question slides in) — is used by all three removal paths: the **Remove from list** button in the action row, the header checkbox (rendered ticked; its `onChange` calls `drill.resetDraft(); drill.draw()`), and the `M` key (`onMark: remove`). Session-scoped `checked` map as in Review. Empty state: "Nothing marked. Tick *Mark for future review* on any question in Practice, Review mistakes or an exam result." + Home link. Questions missing from the bank are filtered out (`.filter(Boolean)`), as in Review. |
| `views/examResult.js` | In the expanded `result-detail`, pass `headExtras: renderMarkToggle({ number, onChange: draw })`. The `open` set lives in the closure, so expanded rows stay open across the redraw. |
| `views/home.js` | Fourth mode card **Future review** → `#/marked`, text `N question(s) marked` / `Nothing marked yet`. Stats row unchanged. |
| `main.js` | Add `['marked', marked]` to `routes` (before `['', home]`). |
| `views/exam.js` | Unchanged. |

### 4.6 CSS (`web/app.css`)

- `.mode-cards { grid-template-columns: repeat(2, 1fr); }` — four cards; the existing `max-width: 640px` rule already yields `1fr 1fr`.
- `.question-head .spacer` is already available via the global `.spacer { flex: 1 }`; the header is a flex row, so no new rule is needed. `.toggle` already styles the checkbox label.

## 5. Error handling

No new failure modes. Reducers are total functions; the toggle re-reads state on every render, so a failed/late save cannot desynchronise the checkbox from the in-memory document. Marked questions whose number no longer exists in the bank are skipped when drilling (same as the mistakes pool).

## 6. Testing

**`tests/web/progress.test.js`** (node --test, pure reducers):

1. `setMarked` on an unattempted question creates `{ ...EMPTY_STAT, marked: true }`; `attempts` stays `0`; `overallStats(p).attempted` stays `0`.
2. `setMarked` is idempotent: marking an already-marked question (or unmarking one with no entry) returns the **same object**.
3. `markedPool` returns ascending numbers; `setMarked(…, false)` removes; `clearMarked` empties the pool and keeps stats.
4. `recordAttempt`, `removeFromMistakes` and `clearMistakes` preserve `marked`; `setMarked` preserves `in_mistakes` and counters.
5. `isMarked` is `false` for unknown numbers and for legacy entries without the key.

**Server tests:** none needed (the document is opaque to the server; existing PUT→GET round-trip covers it).

**Manual smoke (append to README checklist):**

7. Practice: tick *Mark for future review* on Q3 → Home card shows "1 question marked" → Future review drills Q3 with Check/feedback → *Remove from list* → empty state.
8. Open a past exam result, expand a question, tick the box → it appears in Future review.
9. Reload the page → still marked; `data/progress/<bank>.json` contains `"marked": true`.
10. Future review with 2+ questions: *Clear all* → confirm → empty state; `M` toggles the mark in Practice.

## 7. Documentation

- README: "Four modes" (add **Future review**), keyboard line gains `M mark for future review`, smoke checklist items above.
- Base spec `2026-10-09-pdf-exam-simulator-design.md`: amend the non-goal "Persistent bookmarks (only an in-exam, session-scoped flag)" to "Superseded by `2026-10-11-future-review-list-design.md`".

## 8. Build order (for the implementation plan)

1. `progress.js` reducers + tests.
2. `keys.js` `onMark`; `questionCard.js` `headExtras`; `markToggle.js`.
3. `drill.js` `headExtras` / `onMark`; wire Practice and Review.
4. `views/marked.js` + route + Home card + CSS.
5. `examResult.js` toggle.
6. README + base-spec amendment; manual smoke pass.
