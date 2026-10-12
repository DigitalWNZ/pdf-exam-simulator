# Question Notes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A free-text note on every question (Practice, Review mistakes, Future review, expanded Exam results). Adding a note marks the question for future review; removing it from the list keeps the note. Notes persist in the per-bank progress document.

**Architecture:** One new string `comment` on the per-question stat in `data/progress/<bank>.json`, written only by a new pure reducer `setComment` in `web/js/progress.js` (which also sets `marked: true` when a note is first added). A new `noteEditor.js` component renders the note / editor at the bottom of the question card through a new `footExtras` slot (mirror of the existing `headExtras`) on `renderQuestionCard` and `mountDrill`; unsaved drafts live in module state so host redraws never lose text. No server change.

**Tech Stack:** Browser ES modules, no build step, no npm packages; Node 22 only for `npm test` (`node --test tests/web/*.test.js`); Python/`uv` only to run the server for verification.

**Spec:** `docs/superpowers/specs/2026-10-12-question-notes-design.md` (read it first; §2 decisions, §3 the mark rule, §4.1 editor behaviour).

## Global Constraints

- `comment` is written **only** by `setComment`. Adding a note (empty → non-empty) sets `marked: true`; editing or deleting a note never changes `marked`; `setMarked`, `clearMarked`, **Remove from list**, **Clear all** and `recordAttempt` never touch `comment`.
- `setComment` trims (`String(text ?? '').trim()`), returns the **same object** when the trimmed text is unchanged, and `getComment` returns `''` for missing, legacy or non-string values. The progress document keeps `version: 1`; no server or API change.
- Editor copy, verbatim: `✎ Add note`, `Edit note`, `Save`, `Cancel`, `Delete` (Delete only when a saved note exists); placeholder `Your note for this question…`. `Escape` = Cancel, `Enter` with `metaKey`/`ctrlKey` = Save. The textarea is focused when the editor opens, not on later redraws.
- Typing never redraws the screen. Open editors and their unsaved text survive host redraws (module-level `drafts` Map keyed by question number). The component never redraws anything itself; it calls `onChange()` after Save / Cancel / Delete / open.
- The note editor appears in Practice, Review mistakes, Future review and the expanded Exam-result card — **never** in a running exam. `web/js/views/exam.js` is not modified.
- `web/` must not need a build step or any npm package; nothing under `.superpowers/` is ever committed.
- Commit after every task with the message given in the task, touching only the files the task names.

## File Map

| File | Responsibility |
|---|---|
| `web/js/progress.js` | **Modify.** `EMPTY_STAT.comment`; new `getComment`, `setComment` |
| `tests/web/progress.test.js` | **Modify.** Four new tests; two existing deep-equals gain `comment: ''` |
| `web/js/components/noteEditor.js` | **Create.** `renderNoteEditor({ number, onChange })` — note display + editor, draft state |
| `web/js/components/questionCard.js` | **Modify.** Optional `footExtras` slot after `.options` |
| `web/app.css` | **Modify.** `.note`, `.note-text`, `.note-input`, `.note .actions` |
| `web/js/components/drill.js` | **Modify.** Optional `footExtras(s)` option forwarded to the card |
| `web/js/views/practice.js`, `review.js`, `marked.js`, `examResult.js` | **Modify.** Pass the note editor as `footExtras` |
| `README.md`, `docs/superpowers/specs/2026-10-11-future-review-list-design.md` | **Modify.** Notes paragraph + smoke items; cross-reference |

**Browser verification:** the repo has no DOM test harness. Verification of UI behaviour uses the scratch headless-Chrome DevTools-protocol script the controller provides at `<repo>/.superpowers/sdd/2026-10-12-question-notes/browser-check.mjs` (git-ignored; it spawns `uv run serve --port 8010 --no-browser --data <that dir>/data` and headless Chrome on port 9333, runs numbered `item(name, fn)` blocks and exits non-zero on failure). Tasks 3 and 4 extend/run it. If it is absent, perform the listed steps by hand in a browser against `uv run serve --port 8010 --no-browser --data /tmp/notes-check` and record what you observed.

---

### Task 1: `getComment` / `setComment` reducers (pure, TDD)

**Files:**
- Modify: `web/js/progress.js` (line 8 `EMPTY_STAT`; insert a new section after the `markedPool` function, which ends at line 71)
- Test: `tests/web/progress.test.js`

**Interfaces:**
- Consumes: existing `emptyProgress`, `recordAttempt`, `isMarked`, `setMarked`, `clearMarked`, `markedPool`, `removeFromMistakes`, `clearMistakes`, `overallStats`, `mistakePool`.
- Produces (exported from `web/js/progress.js`):
  - `getComment(p, number) -> string` — `''` unless the entry exists and `comment` is a string.
  - `setComment(p, number, text) -> p'` — `next = String(text ?? '').trim()`; same object when `next === getComment(p, number)`; otherwise `{ ...prev, comment: next, marked: prev.marked === true || (prevText === '' && next !== '') }` with `prev` created from `EMPTY_STAT` if absent.
  - `EMPTY_STAT` now has `comment: ''`, so every stat created by `recordAttempt` / `setMarked` carries the key.

- [ ] **Step 1: Write the failing tests**

In `tests/web/progress.test.js`:

(a) Replace the import block (lines 3–7) with:

```js
import {
  checkPractice, clearMarked, clearMistakes, discardExam, emptyProgress, finishExam, getComment, isMarked,
  markedPool, mistakePool, overallStats, recordAttempt, removeFromMistakes, setComment, setExamCurrent,
  setExamPick, setMarked, setPracticeIndex, startExam, startPractice, toggleExamFlag,
} from '../../web/js/progress.js';
```

(b) Two existing shape assertions gain the new key. Line 21 (inside `'recordAttempt accumulates stats …'`) becomes:

```js
    attempts: 1, correct: 0, wrong: 1, last_result: 'wrong', last_answer: ['B'], last_at: T, in_mistakes: true, marked: false, comment: '',
```

and line 134 (inside `'setMarked on an unattempted question …'`) becomes:

```js
    attempts: 0, correct: 0, wrong: 0, last_result: null, last_answer: null, last_at: null, in_mistakes: false, marked: true, comment: '',
```

(c) Append at the end of the file:

```js
// ---- question notes ----
test('getComment is empty for unknown, legacy and non-string entries; setComment creates an entry and marks it', () => {
  let p = emptyProgress('demo');
  assert.equal(getComment(p, 1), '');
  const legacy = { ...p, questions: {
    5: { attempts: 1, correct: 1, wrong: 0, last_result: 'correct', last_answer: ['A'], last_at: T, in_mistakes: false },
    6: { attempts: 0, correct: 0, wrong: 0, last_result: null, last_answer: null, last_at: null, in_mistakes: false, marked: false, comment: null },
  } };
  assert.equal(getComment(legacy, 5), '', 'legacy entry without the key');
  assert.equal(getComment(legacy, 6), '', 'non-string value');
  p = setComment(p, 42, 'x');
  assert.deepEqual(p.questions['42'], {
    attempts: 0, correct: 0, wrong: 0, last_result: null, last_answer: null, last_at: null, in_mistakes: false, marked: true, comment: 'x',
  });
  assert.equal(getComment(p, 42), 'x');
  assert.deepEqual(markedPool(p), [42], 'adding a note marks the question');
  assert.deepEqual(overallStats(p), { attempted: 0, attempts: 0, correct: 0, accuracy: null }, 'a note is not an attempt');
  assert.deepEqual(mistakePool(p), []);
});

test('setComment trims and is a no-op (same object) when the text is unchanged', () => {
  const empty = emptyProgress('demo');
  assert.equal(setComment(empty, 7, ''), empty, 'deleting a note that does not exist');
  assert.equal(setComment(empty, 7, '   '), empty, 'whitespace-only is an empty note');
  const once = setComment(empty, 7, '  hi  ');
  assert.equal(getComment(once, 7), 'hi');
  assert.equal(setComment(once, 7, 'hi'), once, 'same text again');
  assert.equal(setComment(once, 7, ' hi '), once, 'same text after trimming');
  assert.deepEqual(empty.questions, {}, 'input is not mutated');
  assert.equal(getComment(setComment(once, 7, undefined), 7), '', 'undefined clears the note');
});

test('a note marks the question only when it is first added', () => {
  let p = setComment(emptyProgress('demo'), 17, 'first');
  assert.equal(isMarked(p, 17), true, 'add → marked');
  p = setMarked(p, 17, false);
  assert.equal(getComment(p, 17), 'first', 'unmarking keeps the note');
  p = setComment(p, 17, 'edited');
  assert.equal(isMarked(p, 17), false, 'edit → still unmarked');
  p = setComment(p, 17, '');
  assert.equal(getComment(p, 17), '');
  assert.equal(isMarked(p, 17), false, 'delete → still unmarked');
  p = setComment(p, 17, 'again');
  assert.equal(isMarked(p, 17), true, 'adding again is a new add → marked');
  let q = setMarked(emptyProgress('demo'), 3, true);
  q = setComment(q, 3, 'note on a marked question');
  assert.equal(isMarked(q, 3), true);
  assert.equal(getComment(q, 3), 'note on a marked question');
});

test('comment is independent of attempts, marks and the mistakes pool', () => {
  let p = setComment(emptyProgress('demo'), 9, 'keep me');
  p = recordAttempt(p, 9, ['B'], false, T);
  assert.equal(getComment(p, 9), 'keep me', 'recordAttempt preserves the note');
  p = removeFromMistakes(p, 9);
  p = recordAttempt(p, 9, ['B'], false, T);
  p = clearMistakes(p);
  assert.equal(getComment(p, 9), 'keep me', 'mistake reducers preserve the note');
  p = clearMarked(p);
  assert.equal(getComment(p, 9), 'keep me', 'clearMarked preserves the note');
  p = setMarked(p, 9, true);
  p = setMarked(p, 9, false);
  assert.equal(getComment(p, 9), 'keep me', 'setMarked preserves the note');
  p = recordAttempt(p, 9, ['B'], false, T);
  p = setComment(p, 9, 'edited');
  assert.equal(p.questions['9'].attempts, 3, 'setComment preserves counters');
  assert.equal(p.questions['9'].in_mistakes, true, 'setComment preserves in_mistakes');
  assert.equal(isMarked(p, 9), false, 'editing does not re-mark');
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test`
Expected: the progress test file fails to load with `SyntaxError: The requested module '../../web/js/progress.js' does not provide an export named 'getComment'` (Node may name `setComment` instead; the whole file is reported as failed while the other three test files still pass).

- [ ] **Step 3: Implement the reducers**

In `web/js/progress.js`:

(a) Replace line 8 with:

```js
const EMPTY_STAT = { attempts: 0, correct: 0, wrong: 0, last_result: null, last_answer: null, last_at: null, in_mistakes: false, marked: false, comment: '' };
```

(b) Insert after the `markedPool` function (after line 71, before `overallStats`):

```js
// ---- question notes ("Add note") ----
// `comment` is written only here. Adding a note (empty → non-empty) also marks the question for future
// review; editing or deleting a note never changes `marked`. Other reducers spread the stat and keep it.
export function getComment(p, number) {
  const c = p.questions[String(number)]?.comment;
  return typeof c === 'string' ? c : '';
}

export function setComment(p, number, text) {
  const next = String(text ?? '').trim();
  const prevText = getComment(p, number);
  if (prevText === next) return p;
  const key = String(number);
  const prev = p.questions[key] || EMPTY_STAT;
  const marked = prev.marked === true || (prevText === '' && next !== '');
  return { ...p, questions: { ...p.questions, [key]: { ...prev, comment: next, marked } } };
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test`
Expected: `# pass 28`, `# fail 0` (24 existing + 4 new), no warnings.

- [ ] **Step 5: Commit**

```bash
git add web/js/progress.js tests/web/progress.test.js
git commit -m "feat(web): question-note reducers (getComment, setComment marks on first add)"
```

---

### Task 2: Note editor component, card `footExtras` slot, CSS

**Files:**
- Create: `web/js/components/noteEditor.js`
- Modify: `web/js/components/questionCard.js` (signature line 18; article lines 48–54)
- Modify: `web/app.css` (append after line 89 `.toggle …`)

**Interfaces:**
- Consumes: `getComment`, `setComment` (Task 1); `store`, `update` from `web/js/store.js`; `el` from `web/js/dom.js` (`el` skips `null`/`false` attrs and children, flattens arrays, assigns non-string props such as `rows` directly, sets string attrs with `setAttribute`, binds `onXxx` listeners; a string child becomes a text node — for a `<textarea>` that is its initial value).
- Produces:
  - `renderNoteEditor({ number, onChange = () => {} }) -> HTMLDivElement` (`div.note`), behaviour per spec §4.1.
  - `renderQuestionCard({ …, footExtras = null })` — `footExtras` (node or array) is appended as the last child of `article.question-card`, after `.options`. Absent → card unchanged.

DOM modules without a DOM harness: this task verifies with `node --check` and keeps `npm test` at 28; behaviour is exercised in Task 3.

- [ ] **Step 1: Create `noteEditor.js`**

`web/js/components/noteEditor.js`:

```js
import { el } from '../dom.js';
import { getComment, setComment } from '../progress.js';
import { store, update } from '../store.js';

/**
 * Per-question note ("Add note") rendered at the bottom of a question card.
 * Closed: the saved note (if any) + "Edit note" / "✎ Add note". Open: textarea + Save / Cancel / Delete.
 * Open editors and their unsaved text live in `drafts` (module state keyed by bank id + question number), so a
 * host redraw re-renders the editor with the draft intact and typing never triggers a redraw.
 * Saves go through store.update(); the host is asked to redraw via onChange(). Never redraws itself.
 */
const drafts = new Map();                                   // number → { text, focus }

export function renderNoteEditor({ number, onChange = () => {} }) {
  const key = `${store.bankId}:${number}`;
  const saved = getComment(store.progress, number);
  const draft = drafts.get(key);

  if (!draft) {
    const open = () => { drafts.set(key, { text: saved, focus: true }); onChange(); };
    return el('div', { class: 'note' },
      saved ? el('div', { class: 'note-text' }, saved) : null,
      el('button', { class: 'btn link', onClick: open }, saved ? 'Edit note' : '✎ Add note'));
  }

  const close = () => { drafts.delete(key); onChange(); };
  const save = () => { update((p) => setComment(p, number, textarea.value)); close(); };
  const remove = () => { update((p) => setComment(p, number, '')); close(); };
  const textarea = el('textarea', {
    class: 'note-input', rows: 3, placeholder: 'Your note for this question…',
    onInput: () => { draft.text = textarea.value; },
    onKeydown: (e) => {
      if (e.key === 'Escape') { e.preventDefault(); close(); }
      else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save(); }
    },
  }, draft.text);
  if (draft.focus) {                                        // focus once, when the editor was just opened
    draft.focus = false;
    setTimeout(() => { textarea.focus(); textarea.setSelectionRange(textarea.value.length, textarea.value.length); }, 0);
  }
  return el('div', { class: 'note editing' },
    textarea,
    el('div', { class: 'actions' },
      el('button', { class: 'btn primary', onClick: save }, 'Save'),
      el('button', { class: 'btn', onClick: close }, 'Cancel'),
      saved ? el('button', { class: 'btn danger', onClick: remove }, 'Delete') : null));
}
```

(`save` references `textarea`, which is declared on the next lines; both are closures invoked only on user events, after the declarations ran.)

- [ ] **Step 2: Add the `footExtras` slot to `questionCard.js`**

(a) Replace the signature (line 18) with:

```js
export function renderQuestionCard({ question, bankId, order = null, picked = [], locked = false, reveal = null, onPick = () => {}, headExtras = null, footExtras = null }) {
```

(b) Replace the `return el('article', …)` statement (lines 48–54) with:

```js
  return el('article', { class: 'question-card' },
    el('header', { class: 'question-head' },
      el('span', { class: 'qnum' }, `#${question.number}`),
      multi ? el('span', { class: 'hint' }, `Choose ${question.select_count}`) : null,
      headExtras ? [el('span', { class: 'spacer' }), headExtras] : null),
    el('div', { class: 'stem' }, renderBlocks(question.stem, bankId)),
    el('div', { class: 'options' }, rows),
    footExtras);
```

- [ ] **Step 3: CSS**

Append to `web/app.css` directly after line 89 (`.toggle { … }`):

```css
.note { margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--line); font-size: 14px; }
.note-text { white-space: pre-wrap; margin: 0 0 6px; }
.note-input { display: block; width: 100%; min-height: 72px; font: inherit; padding: 8px 10px; border: 1px solid var(--line); border-radius: 8px; resize: vertical; }
.note .actions { margin: 8px 0 0; }
```

- [ ] **Step 4: Syntax-check and keep the suite green**

Run: `node --check web/js/components/noteEditor.js && node --check web/js/components/questionCard.js && npm test`
Expected: no `--check` output; `# pass 28`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add web/js/components/noteEditor.js web/js/components/questionCard.js web/app.css
git commit -m "feat(web): note editor component and question-card footExtras slot"
```

---

### Task 3: Wire the editor into the drill views and exam results; browser verification

**Files:**
- Modify: `web/js/components/drill.js` (doc comment lines 20–21; `renderQuestionCard` call lines 72–74)
- Modify: `web/js/views/practice.js` (import line 2; options after line 25)
- Modify: `web/js/views/review.js` (import line 2; options after line 35)
- Modify: `web/js/views/marked.js` (import line 2; options after line 39)
- Modify: `web/js/views/examResult.js` (import line 3; card call lines 37–38)

**Interfaces:**
- Consumes: `renderNoteEditor` (Task 2), `renderQuestionCard.footExtras` (Task 2).
- Produces: `mountDrill` option `footExtras(s) -> node`, forwarded to the card on every draw (same idiom as `headExtras`). Views pass `footExtras: (s) => renderNoteEditor({ number: s.q.number, onChange: () => drill.draw() })`; a plain `drill.draw()` is correct in all three drills (saving/deleting a note never removes a question from any list; adding one marks it, which in Future review is already the case).

- [ ] **Step 1: `drill.js`**

(a) Insert after the `headExtras(s)` doc line (line 20):

```js
 *   footExtras(s)               → node appended at the bottom of the question card (optional)
```

(b) Replace the `renderQuestionCard` call (lines 72–74) with:

```js
      renderQuestionCard({ question: s.q, bankId: opts.bankId, picked: s.picked, locked: s.locked,
        reveal: s.locked ? s.q.answer : null, onPick: (next) => { draft = next; draw(); },
        headExtras: opts.headExtras ? opts.headExtras(s) : null,
        footExtras: opts.footExtras ? opts.footExtras(s) : null }),
```

- [ ] **Step 2: Practice, Review mistakes, Future review**

In each of `web/js/views/practice.js`, `web/js/views/review.js`, `web/js/views/marked.js`:

(a) Insert after line 2 (`import { renderMarkToggle } …`):

```js
import { renderNoteEditor } from '../components/noteEditor.js';
```

(b) Insert this option line directly after the `onMark:` line (practice.js line 25, review.js line 35, marked.js line 39):

```js
    footExtras: (s) => renderNoteEditor({ number: s.q.number, onChange: () => drill.draw() }),
```

- [ ] **Step 3: Exam results**

In `web/js/views/examResult.js`:

(a) Insert after line 3 (`import { renderMarkToggle } …`):

```js
import { renderNoteEditor } from '../components/noteEditor.js';
```

(b) Replace the card call (lines 37–38) with:

```js
          renderQuestionCard({ question: q, bankId: store.bankId, picked: it.picked, locked: true, reveal: q.answer,
            headExtras: renderMarkToggle({ number: it.number, onChange: draw }),
            footExtras: renderNoteEditor({ number: it.number, onChange: draw }) }),
```

- [ ] **Step 4: Verify in the browser (headless harness)**

Run first: `for f in web/js/components/drill.js web/js/views/practice.js web/js/views/review.js web/js/views/marked.js web/js/views/examResult.js; do node --check "$f" || echo "SYNTAX ERROR: $f"; done; npm test` → no errors, `# pass 28`.

Then extend `.superpowers/sdd/2026-10-12-question-notes/browser-check.mjs` (do not rewrite it; insert new `item(...)` blocks before its final exceptions/isolation items and renumber those) so the run covers, in this order, continuing from the state the earlier items leave (one question marked from the exam-result items):

1. Practice (range 1–12) → jump to Q6: the card ends with `div.note` containing a `✎ Add note` button and no `.note-text`; the running count of `.note` elements on the page is 1. Click it → `textarea.note-input` exists and `document.activeElement` is that textarea. Set its value to `First note` and dispatch an `input` event. Click option A (`.option input`) → `.option.picked` exists **and** the textarea is still present with value `First note` (draft survived the redraw). Click `Save` → `.note-text` reads `First note`, the header mark checkbox is checked, the store has `marked: true` and `comment: 'First note'` for Q6; Home's Future review card count increased by exactly 1; after ≥ 1 s the isolated progress file contains `"comment": "First note"`.
2. Practice Q6: `Edit note` → textarea prefilled with `First note`; set `Second note` + input event; dispatch `keydown` `Enter` with `ctrlKey: true` on the textarea → editor closed, `.note-text` = `Second note`. `Edit note` → set `zzz` → dispatch `keydown` `Escape` → editor closed, `.note-text` still `Second note`. `Edit note` → `Delete` → no `.note-text`, `✎ Add note` shown, header checkbox **still checked** (deleting keeps the mark), store `comment: ''`.
3. Practice Q6: add `Third` → Save. `#/marked` lists Q6 (label count includes it) with `.note-text` = `Third`. **Remove from list** on Q6. Practice → Q6: `.note-text` = `Third`, header checkbox unchecked. `Edit note` → `Third edited` → Save → checkbox still unchecked and store `marked: false` (editing never re-marks).
4. Exam results: open the finished exam from Home history, expand the first row: `.result-detail .note` exists with `✎ Add note`; add `From result` → Save → the row is still expanded, `.note-text` shows `From result`, that question's store entry has `marked: true`. Collapsed rows and the summary card contain no `.note`.
5. Start a new exam (`#/exam/setup` → Start): the running exam page has **no** `.note` element; finish it with `window.confirm` stubbed to `true` (or leave it — the existing items cope with an active exam only if you finish it; finishing is simpler).
6. The pre-existing exceptions/isolation items still pass (no uncaught exceptions / `console.error`; the real `data/progress` file untouched; ports released).

Run: `node .superpowers/sdd/2026-10-12-question-notes/browser-check.mjs` → all items `PASS`, exit 0. Then run a negative control with the five product files of this task stashed (`git stash push -- web/js/components/drill.js web/js/views/practice.js web/js/views/review.js web/js/views/marked.js web/js/views/examResult.js`), confirm the new items fail, `git stash pop`, and re-run to green before committing. Kill any server/Chrome you started; `git status --short` must show only the five files.

- [ ] **Step 5: Commit**

```bash
git add web/js/components/drill.js web/js/views/practice.js web/js/views/review.js web/js/views/marked.js web/js/views/examResult.js
git commit -m "feat(web): note editor on Practice, Review mistakes, Future review and exam results"
```

---

### Task 4: Docs, spec cross-reference, final verification

**Files:**
- Modify: `README.md` (insert after line 33; append smoke items after line 55)
- Modify: `docs/superpowers/specs/2026-10-11-future-review-list-design.md` (insert after line 27)

- [ ] **Step 1: README**

(a) Insert after line 33 (the paragraph beginning `Progress is stored per bank …`), separated by blank lines:

```markdown
Notes: every question card outside a running exam has an *Add note* editor (Save / Cancel / Delete; `Esc` cancels, `⌘/Ctrl+Enter` saves). Adding a note marks the question for future review; removing it from that list keeps the note. Notes are stored in the progress file as `"comment"`.
```

(b) Append after smoke item 10 (line 55):

```markdown
11. Practice: *Add note* on Q4 → type → Save → note shown under the options and the question is now ticked; Home → Future review shows it with the note.
12. Future review: *Remove from list* on Q4 → Practice Q4 still shows the note, unticked; *Delete* removes the note; reload → state persists; `data/progress/<bank>.json` contains `"comment"`.
```

- [ ] **Step 2: Cross-reference in the future-review spec**

Insert after line 27 of `docs/superpowers/specs/2026-10-11-future-review-list-design.md` (the "Implementer picks …" paragraph), as its own paragraph:

```markdown
Related: adding a note to a question (see `2026-10-12-question-notes-design.md`) also marks it; removing a question from this list never deletes its note.
```

- [ ] **Step 3: Final verification**

```bash
npm test
uv run pytest -q -p no:warnings
for f in web/js/progress.js web/js/components/noteEditor.js web/js/components/questionCard.js web/js/components/drill.js web/js/views/practice.js web/js/views/review.js web/js/views/marked.js web/js/views/examResult.js; do node --check "$f" || echo "SYNTAX ERROR: $f"; done
node .superpowers/sdd/2026-10-12-question-notes/browser-check.mjs
git status --short
```

Expected: `# pass 28 / # fail 0`; pytest all passed (73); no `SYNTAX ERROR`; harness all items `PASS`, exit 0; `git status` shows only the two doc files before the commit and nothing after.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/superpowers/specs/2026-10-11-future-review-list-design.md
git commit -m "docs: question notes in README and future-review spec"
```
