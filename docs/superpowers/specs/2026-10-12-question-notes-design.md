# Question Notes ("Add note") — Design Spec

**Date:** 2026-10-12
**Status:** Approved in brainstorming; awaiting user review of this document
**Builds on:** `2026-10-11-future-review-list-design.md` (the Future review list) and the base spec `2026-10-09-pdf-exam-simulator-design.md`.

## 1. Goal

Let the user write a free-text note on any question. A question that gets a note joins the existing **Future review** list, so notes and marks are reviewed in one place. Notes are persisted on disk with the rest of the progress document.

### Non-goals

- Notes during a running exam (the exam screen stays untouched).
- Markdown rendering, search across notes, export, note history.
- A note indicator in collapsed exam-result rows or a note count on Home.
- Changing the server or the progress API.

## 2. Decisions

| Topic | Decision |
|---|---|
| Relationship to Future review | **Adding** a note (empty → non-empty) sets `marked: true`, so the question joins the single Future review list. Editing or deleting a note never changes `marked`. **Remove from list** / **Clear all** / unticking only unmark — the note stays. |
| Editor | Explicit editor at the bottom of the question card: `✎ Add note` → textarea with **Save** / **Cancel** (+ **Delete** when a note exists). Saved note is shown as text with **Edit note**. Typing never redraws the screen; an unsaved draft survives host redraws (picking an option, `M`, Check). |
| Where | Everywhere the mark checkbox appears: Practice, Review mistakes, Future review, expanded Exam results. Never in a running exam. |
| Storage | `comment` string on the per-question stat in the progress document, next to `marked`. One document per bank; no server change. |
| Text | Plain text, multi-line, trimmed at both ends on save; no length limit. |

Implementer picks (cheap to change): labels `✎ Add note` / `Edit note` / `Save` / `Cancel` / `Delete`; placeholder `Your note for this question…`; `Escape` = Cancel and `⌘/Ctrl+Enter` = Save inside the textarea; the textarea is focused when the editor opens.

## 3. Data model (`web/js/progress.js`)

```json
"17": {
  "attempts": 3, "correct": 2, "wrong": 1,
  "last_result": "wrong", "last_answer": ["B"], "last_at": "2026-10-09T08:10:00Z",
  "in_mistakes": true,
  "marked": true,
  "comment": "Dataflow for streaming + exactly-once; Dataproc only when Spark is required."
}
```

- `EMPTY_STAT` gains `comment: ''`. Files written before this change have no `comment` key — a missing or non-string value reads as `''`. `version` stays `1`.
- Only `setComment` writes `comment`. All other reducers spread the previous stat and therefore preserve it (`recordAttempt`, `setMarked`, `clearMarked`, `removeFromMistakes`, `clearMistakes`, exam/practice reducers).

| Function | Behaviour |
|---|---|
| `getComment(p, number)` | The note text, or `''` when the entry is missing, legacy, or non-string. |
| `setComment(p, number, text)` | `next = String(text ?? '').trim()`. Returns `p` unchanged when `next === getComment(p, number)`. Otherwise writes `comment: next` on the entry (created from `EMPTY_STAT` if absent) and sets `marked` to `prev.marked === true || (previous text was '' && next !== '')`. Deleting a note is `setComment(p, number, '')`. |

Consequences of the rule, spelled out:

- add note → marked; **Remove from list** → unmarked, note kept; edit note → still unmarked; delete note → still unmarked; add a note again later → marked again (that is a new add).
- adding a note to a question that is already marked changes only `comment`.

Persistence is unchanged: `store.update(reducer)` → debounced whole-document `PUT` → atomic write to `data/progress/<bank_id>.json`. Failures surface through the existing sticky toast/retry.

## 4. Web UI

### 4.1 `components/noteEditor.js` (new)

`renderNoteEditor({ number, onChange = () => {} })` returns one `div.note`:

- **Closed, no note:** a `✎ Add note` button (`btn link`).
- **Closed, note exists:** the note text in `div.note-text` (`white-space: pre-wrap`) and an `Edit note` button (`btn link`).
- **Open:** a `textarea.note-input` (3 rows, placeholder `Your note for this question…`) followed by an action row with **Save** (`btn primary`), **Cancel** (`btn`) and, only when a saved note exists, **Delete** (`btn danger`).

State: a module-level `Map` `drafts` keyed by question number holds `{ text, focus }` while an editor is open. Opening sets `drafts.set(number, { text: savedText, focus: true })` and calls `onChange()`; every render while the entry exists shows the textarea with `text` as its value and keeps it updated on `input` (`drafts.get(number).text = textarea.value`, no redraw). When `focus` is `true` the render schedules `textarea.focus()` (and moves the caret to the end) once, then clears the flag, so later redraws do not steal focus. **Save:** `update((p) => setComment(p, number, textarea.value))`, delete the draft, `onChange()`. **Cancel:** delete the draft, `onChange()`. **Delete:** `update((p) => setComment(p, number, ''))`, delete the draft, `onChange()`. Keyboard inside the textarea: `Escape` → Cancel; `Enter` with `metaKey` or `ctrlKey` → Save. The component never redraws anything itself and depends only on `store`, `progress.js`, `dom.js`.

Because drafts are keyed by number and live for the page session, navigating away from a question and back re-opens its unsaved editor; drafts are never persisted.

The global key handler (`keys.js`) already returns early for `TEXTAREA` targets, so typing `1`, `m`, `Enter` or arrows in the note never picks options, marks, checks or navigates.

### 4.2 `components/questionCard.js`

`renderQuestionCard` accepts an optional `footExtras` node (or array), appended after `.options` as the last child of the card. The running Exam passes nothing and is unchanged.

### 4.3 `components/drill.js`

New optional option `footExtras(s)` → node, forwarded to `renderQuestionCard` on every draw (same idiom as `headExtras`).

### 4.4 Views

| View | Change |
|---|---|
| `views/practice.js`, `views/review.js`, `views/marked.js` | Add `footExtras: (s) => renderNoteEditor({ number: s.q.number, onChange: () => drill.draw() })`. In Future review a saved or deleted note never changes the list (adding marks, and the question is already marked there), so a plain `drill.draw()` is correct. |
| `views/examResult.js` | In the expanded detail pass `footExtras: renderNoteEditor({ number: it.number, onChange: draw })` next to the existing `headExtras`. The `open` Set keeps the row expanded across the redraw. |
| `views/home.js`, `views/exam.js`, `main.js` | Unchanged. |

### 4.5 CSS (`web/app.css`)

```css
.note { margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--line); font-size: 14px; }
.note-text { white-space: pre-wrap; margin: 0 0 6px; }
.note-input { display: block; width: 100%; min-height: 72px; font: inherit; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; resize: vertical; }
.note .actions { margin: 8px 0 0; }
```

(`* { box-sizing: border-box }` already applies, so `width: 100%` plus padding fits the card.)

## 5. Error handling

No new failure modes. `setComment` is total (coerces to string, trims). A redraw while the editor is open re-renders from the draft, so no keystrokes are lost; only the caret position resets. Notes for questions missing from the bank remain in the document and are simply never shown.

## 6. Testing

**`tests/web/progress.test.js`** (node --test):

1. `getComment` is `''` for unknown numbers, legacy entries without the key, and a non-string value; `setComment` on an unattempted question creates `{ ...EMPTY_STAT, comment: 'x', marked: true }` with `attempts: 0`; `overallStats` and `mistakePool` unaffected.
2. Trim and identity: `'  hi  '` saves as `'hi'`; saving the same text again returns the **same object**; `setComment(empty, 7, '')` and `setComment(empty, 7, '   ')` return the same object.
3. Mark rule: add → `marked: true`; `setMarked(false)`; edit → still `false`; delete (`''`) → still `false`, `comment: ''`; add again → `true`. Adding to an already-marked question leaves `marked: true`.
4. Independence: `recordAttempt`, `setMarked`, `clearMarked`, `removeFromMistakes`, `clearMistakes` preserve `comment`; `setComment` preserves counters, `in_mistakes` and (when not a first add) `marked`.
5. Existing shape assertions (`recordAttempt` and `setMarked` deep-equals) gain `comment: ''`.

**Headless browser harness** (scratch `browser-check.mjs`, extended): Practice → `Add note` → textarea focused → type → click an option → draft still present and pick kept → `Save` → note text shown, mark checkbox ticked, Home card count +1, progress file contains `"comment"`; `Edit note` → change → `Save`; `Delete` → note gone, still marked; Future review → **Remove from list** → in Practice the note is still shown and the box is unticked; edit it there → still unticked; `Escape` cancels an edit; `⌘/Ctrl+Enter` saves; expanded exam result shows the editor; the running exam has no `.note`.

**Manual smoke (README):**

11. Practice: *Add note* on Q4 → type → Save → note shown under the options and the question is now ticked; Home → Future review shows it with the note.
12. Future review: *Remove from list* on Q4 → Practice Q4 still shows the note, unticked; *Delete* removes the note; reload → state persists; `data/progress/<bank>.json` contains `"comment"`.

## 7. Documentation

- README: feature sentence (notes on every question card outside the exam; adding a note marks the question for future review; notes live in the progress file), smoke items 11–12.
- `2026-10-11-future-review-list-design.md`: add one line under §2 pointing here: "Adding a note (see `2026-10-12-question-notes-design.md`) also marks a question."

## 8. Build order (for the implementation plan)

1. `progress.js` `getComment`/`setComment` + tests.
2. `noteEditor.js`, `questionCard.js` `footExtras`, CSS.
3. `drill.js` `footExtras`; wire Practice, Review, Future review, Exam results; extend the harness.
4. README + spec cross-reference; final verification.
