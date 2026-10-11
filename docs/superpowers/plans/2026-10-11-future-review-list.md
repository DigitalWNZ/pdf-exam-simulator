# Future-Review List Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A persistent "Mark for future review" checkbox on every question (Practice, Review mistakes, Exam results, and the new screen itself) plus a **Future review** screen (`#/marked`) that drills the marked questions with per-question *Remove from list* and *Clear all* — mirroring the existing mistakes pool.

**Architecture:** One new boolean `marked` on the per-question stat inside the existing progress document (`data/progress/<bank>.json`), managed by four pure reducers/selectors in `web/js/progress.js`. A tiny `markToggle.js` component reads/writes it through `store.update`, is slotted into a new `headExtras` slot of the question card (via a new `drill.js` option), and the new `views/marked.js` is a near-copy of `views/review.js`. The server is untouched (it only validates `version` and `bank_id`).

**Tech Stack:** Browser ES modules, no build step, no npm packages; Node 22 only for `node --test tests/web/*.test.js` (`npm test`); Python/`uv` only to run the server for manual verification (`uv run serve`).

**Spec:** `docs/superpowers/specs/2026-10-11-future-review-list-design.md` (read it first; §2 lists the decisions, §4.5 the per-view behaviour).

## Global Constraints

- No server or API change. The progress document keeps `version: 1`; the server is opaque to the new key.
- `marked` is set or cleared **only** by `setMarked` and `clearMarked`. Nothing automatic: answering correctly never removes a question from the list.
- The checkbox appears in Practice, Review mistakes, Exam results (expanded question) and Future review — **never** in a running exam (`views/exam.js` is not modified).
- Reducers never mutate their input and return the **same object** when nothing changes (same convention as `removeFromMistakes`).
- Future review drills like Review mistakes: pick → Check → feedback → Next; `recordAttempt` is called, so attempts count and a wrong answer also enters the mistakes pool.
- Copy, verbatim: checkbox label **Mark for future review**; screen title / Home card **Future review**; route `#/marked`; keyboard shortcut `M`; button **Remove from list**; toolbar button **Clear all**.
- Progress files written before this change have no `marked` key — a missing key means unmarked.
- `web/` must not need a build step or any npm package. Node 22 is only used for `npm test`.
- Commit after every task with the message given in the task.

## File Map

| File | Responsibility |
|---|---|
| `web/js/progress.js` | **Modify.** `EMPTY_STAT.marked`; new `isMarked`, `setMarked`, `clearMarked`, `markedPool` |
| `tests/web/progress.test.js` | **Modify.** Reducer tests for the above; one existing deep-equal updated for the new key |
| `web/js/keys.js` | **Modify.** `bindKeys` gains `onMark` (`m`/`M`) |
| `web/js/components/questionCard.js` | **Modify.** Optional `headExtras` slot at the right of the card header |
| `web/js/components/markToggle.js` | **Create.** `renderMarkToggle({ number, onChange })` — the checkbox |
| `web/js/components/drill.js` | **Modify.** Optional `headExtras(s)` and `onMark(s)` options; `M` in the key hint |
| `web/js/views/practice.js`, `web/js/views/review.js` | **Modify.** Pass `headExtras` + `onMark` |
| `web/js/views/marked.js` | **Create.** Future review screen (drill over `markedPool`) |
| `web/js/main.js` | **Modify.** Route `#/marked` |
| `web/js/views/home.js` | **Modify.** Fourth mode card with the marked count |
| `web/app.css` | **Modify.** `.mode-cards` 2×2; pointer cursor on `.toggle` |
| `web/js/views/examResult.js` | **Modify.** Toggle on the expanded question card |
| `README.md`, `docs/superpowers/specs/2026-10-09-pdf-exam-simulator-design.md` | **Modify.** Four modes, `M` key, smoke items; base-spec non-goal superseded |

---

### Task 1: Progress reducers for the future-review list (pure, TDD)

**Files:**
- Modify: `web/js/progress.js` (line 8 `EMPTY_STAT`; add a new section after `mistakePool`, i.e. after line 44)
- Test: `tests/web/progress.test.js`

**Interfaces:**
- Consumes: existing `emptyProgress`, `recordAttempt`, `removeFromMistakes`, `clearMistakes`, `mistakePool`, `overallStats`.
- Produces (exact signatures, all exported from `web/js/progress.js`):
  - `isMarked(p, number) -> boolean` — `true` only when the entry exists and `marked === true`.
  - `setMarked(p, number, marked) -> p'` — `marked` is coerced with `Boolean()`; creates the entry from `EMPTY_STAT` when missing; returns the same `p` when the flag already has that value.
  - `clearMarked(p) -> p'` — `marked: false` on every entry that had it `true`.
  - `markedPool(p) -> number[]` — ascending question numbers with `marked === true`.
  - `EMPTY_STAT` now has `marked: false`, so every stat created by `recordAttempt` carries the key.

- [ ] **Step 1: Write the failing tests**

In `tests/web/progress.test.js`:

(a) Replace the import block (lines 3–7) with:

```js
import {
  checkPractice, clearMarked, clearMistakes, discardExam, emptyProgress, finishExam, isMarked, markedPool,
  mistakePool, overallStats, recordAttempt, removeFromMistakes, setExamCurrent, setExamPick, setMarked,
  setPracticeIndex, startExam, startPractice, toggleExamFlag,
} from '../../web/js/progress.js';
```

(b) In the existing test `'recordAttempt accumulates stats and a wrong answer enters the mistakes pool'`, the first `assert.deepEqual` must include the new key — change it to:

```js
  assert.deepEqual(p.questions['17'], {
    attempts: 1, correct: 0, wrong: 1, last_result: 'wrong', last_answer: ['B'], last_at: T, in_mistakes: true, marked: false,
  });
```

(c) Append at the end of the file:

```js
// ---- future-review list ----
test('setMarked on an unattempted question creates an entry without counting an attempt', () => {
  let p = emptyProgress('demo');
  p = setMarked(p, 42, true);
  assert.deepEqual(p.questions['42'], {
    attempts: 0, correct: 0, wrong: 0, last_result: null, last_answer: null, last_at: null, in_mistakes: false, marked: true,
  });
  assert.equal(isMarked(p, 42), true);
  assert.deepEqual(overallStats(p), { attempted: 0, attempts: 0, correct: 0, accuracy: null }, 'marking is not an attempt');
  assert.deepEqual(mistakePool(p), [], 'marking does not touch the mistakes pool');
});

test('setMarked is a no-op (same object) when the flag already has that value', () => {
  const empty = emptyProgress('demo');
  assert.equal(setMarked(empty, 7, false), empty, 'unmarking a question with no entry');
  const once = setMarked(empty, 7, true);
  assert.equal(setMarked(once, 7, true), once, 'marking twice');
  assert.deepEqual(empty.questions, {}, 'input is not mutated');
});

test('marked pool: sorted numbers, per-question removal, clear all; stats and mistakes are kept', () => {
  let p = emptyProgress('demo');
  p = setMarked(p, 30, true);
  p = setMarked(p, 4, true);
  p = recordAttempt(p, 9, ['A'], false, T);
  assert.deepEqual(markedPool(p), [4, 30]);
  p = setMarked(p, 30, false);
  assert.deepEqual(markedPool(p), [4]);
  assert.equal(p.questions['30'].marked, false);
  p = recordAttempt(p, 4, ['A'], false, T);
  p = clearMarked(p);
  assert.deepEqual(markedPool(p), []);
  assert.equal(p.questions['4'].wrong, 1, 'stats are kept');
  assert.deepEqual(mistakePool(p), [4, 9], 'mistakes pool is kept');
});

test('marked and in_mistakes are independent', () => {
  let p = emptyProgress('demo');
  p = setMarked(p, 17, true);
  p = recordAttempt(p, 17, ['B'], false, T);
  assert.equal(p.questions['17'].marked, true, 'recordAttempt preserves marked');
  p = removeFromMistakes(p, 17);
  assert.equal(p.questions['17'].marked, true, 'removeFromMistakes preserves marked');
  p = recordAttempt(p, 17, ['B'], false, T);
  p = clearMistakes(p);
  assert.equal(p.questions['17'].marked, true, 'clearMistakes preserves marked');
  p = setMarked(p, 17, false);
  assert.equal(p.questions['17'].attempts, 2, 'setMarked preserves counters');
  assert.equal(p.questions['17'].in_mistakes, false, 'setMarked preserves in_mistakes');
});

test('isMarked is false for unknown numbers and for legacy entries without the key', () => {
  const p = emptyProgress('demo');
  assert.equal(isMarked(p, 1), false);
  const legacy = { ...p, questions: { 5: { attempts: 1, correct: 1, wrong: 0, last_result: 'correct', last_answer: ['A'], last_at: T, in_mistakes: false } } };
  assert.equal(isMarked(legacy, 5), false);
  assert.deepEqual(markedPool(legacy), []);
  assert.equal(setMarked(legacy, 5, false), legacy, 'unmarking a legacy entry is a no-op');
  assert.equal(setMarked(legacy, 5, true).questions['5'].marked, true);
  assert.equal(setMarked(legacy, 5, true).questions['5'].attempts, 1, 'legacy counters are kept');
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test`
Expected: the progress test file fails to load with `SyntaxError: The requested module '../../web/js/progress.js' does not provide an export named 'clearMarked'` (Node may name any of the four new exports; it is an ESM named-import error, so the whole file is reported as failed while the other three test files still pass).

- [ ] **Step 3: Implement the reducers**

In `web/js/progress.js`:

(a) Replace line 8 with:

```js
const EMPTY_STAT = { attempts: 0, correct: 0, wrong: 0, last_result: null, last_answer: null, last_at: null, in_mistakes: false, marked: false };
```

(b) Insert after the `mistakePool` function (after line 44, before `overallStats`):

```js
// ---- future-review list ("Mark for future review") ----
// `marked` is set or cleared only here; recordAttempt/mistake reducers spread the stat and preserve it.
export function isMarked(p, number) {
  return p.questions[String(number)]?.marked === true;
}

export function setMarked(p, number, marked) {
  const next = Boolean(marked);
  if (isMarked(p, number) === next) return p;
  const key = String(number);
  const prev = p.questions[key] || EMPTY_STAT;
  return { ...p, questions: { ...p.questions, [key]: { ...prev, marked: next } } };
}

export function clearMarked(p) {
  const questions = {};
  for (const [k, v] of Object.entries(p.questions)) questions[k] = v.marked ? { ...v, marked: false } : v;
  return { ...p, questions };
}

export function markedPool(p) {
  return Object.entries(p.questions)
    .filter(([, v]) => v.marked === true)
    .map(([k]) => Number(k))
    .sort((a, b) => a - b);
}
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `npm test`
Expected: `# pass 24`, `# fail 0` (19 existing + 5 new).

- [ ] **Step 5: Commit**

```bash
git add web/js/progress.js tests/web/progress.test.js
git commit -m "feat(web): future-review reducers (setMarked, clearMarked, markedPool, isMarked)"
```

---

### Task 2: `M` shortcut, question-card header slot, mark-toggle component

**Files:**
- Modify: `web/js/keys.js`
- Modify: `web/js/components/questionCard.js` (signature line 18; header lines 48–51)
- Create: `web/js/components/markToggle.js`

**Interfaces:**
- Consumes: `isMarked`, `setMarked` (Task 1); `store`, `update` from `web/js/store.js`; `el` from `web/js/dom.js`.
- Produces:
  - `bindKeys({ …, onMark })` — `m`/`M` calls `onMark()` and prevents default **only when `onMark` is provided**; otherwise `M` is ignored exactly as today.
  - `renderQuestionCard({ …, headExtras = null })` — when `headExtras` is a node (or array of nodes) it is rendered at the right end of `.question-head` after a `.spacer`.
  - `renderMarkToggle({ number, onChange = () => {} }) -> HTMLLabelElement` — checkbox reflecting `isMarked(store.progress, number)`; on change it runs `update((p) => setMarked(p, number, input.checked))` and then `onChange()`. It never redraws anything itself.

These are DOM modules; the repo tests DOM code in the browser (Task 3), so this task only syntax-checks and keeps `npm test` green.

- [ ] **Step 1: Add `onMark` to `keys.js`**

Replace the whole file with:

```js
/**
 * Keyboard shortcuts for question screens. Ignores typing in text/number inputs and
 * lets focused buttons/links handle Enter themselves (avoids double actions).
 *  1-9 / A-I → onOption(displayIndex) · F → onFlag (if given, else F is option 6) · M → onMark (if given)
 *  Enter → onEnter · ArrowLeft → onPrev · ArrowRight → onNext
 */
export function bindKeys({ onOption, onEnter, onPrev, onNext, onFlag, onMark } = {}) {
  const handler = (e) => {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
    const target = e.target || {};
    const tag = target.tagName || '';
    if (tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (tag === 'INPUT' && target.type !== 'radio' && target.type !== 'checkbox') return;
    const k = e.key;
    if (k === 'Enter' && (tag === 'BUTTON' || tag === 'A')) return;
    if ((k === 'f' || k === 'F') && onFlag) { onFlag(); e.preventDefault(); return; }
    if ((k === 'm' || k === 'M') && onMark) { onMark(); e.preventDefault(); return; }
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

- [ ] **Step 2: Add the `headExtras` slot to `questionCard.js`**

(a) Replace the signature (line 18) with:

```js
export function renderQuestionCard({ question, bankId, order = null, picked = [], locked = false, reveal = null, onPick = () => {}, headExtras = null }) {
```

(b) Replace the header (lines 48–51, the `el('article', …` opening through the `multi ? … : null),` line) with:

```js
  return el('article', { class: 'question-card' },
    el('header', { class: 'question-head' },
      el('span', { class: 'qnum' }, `#${question.number}`),
      multi ? el('span', { class: 'hint' }, `Choose ${question.select_count}`) : null,
      headExtras ? [el('span', { class: 'spacer' }), headExtras] : null),
```

(`el()` flattens arrays and drops `null`, so the exam — which passes no `headExtras` — renders exactly as before.)

- [ ] **Step 3: Create `markToggle.js`**

`web/js/components/markToggle.js`:

```js
import { el } from '../dom.js';
import { isMarked, setMarked } from '../progress.js';
import { store, update } from '../store.js';

/**
 * "Mark for future review" checkbox for one question. Reads the flag from store.progress when
 * rendered, persists changes through store.update(), then calls onChange() so the host view can
 * redraw itself. Never redraws anything on its own.
 */
export function renderMarkToggle({ number, onChange = () => {} }) {
  const input = el('input', {
    type: 'checkbox',
    checked: isMarked(store.progress, number),
    onChange: () => { update((p) => setMarked(p, number, input.checked)); onChange(); },
  });
  return el('label', { class: 'toggle' }, input, 'Mark for future review');
}
```

- [ ] **Step 4: Syntax-check and keep the suite green**

Run: `node --check web/js/keys.js && node --check web/js/components/questionCard.js && node --check web/js/components/markToggle.js && npm test`
Expected: no output from the three `--check`s; `# pass 24`, `# fail 0`.

- [ ] **Step 5: Commit**

```bash
git add web/js/keys.js web/js/components/questionCard.js web/js/components/markToggle.js
git commit -m "feat(web): M shortcut, question-card header slot, mark-for-review toggle"
```

---

### Task 3: Drill support; wire Practice and Review mistakes

**Files:**
- Modify: `web/js/components/drill.js`
- Modify: `web/js/views/practice.js`
- Modify: `web/js/views/review.js`

**Interfaces:**
- Consumes: `renderMarkToggle` (Task 2), `bindKeys.onMark` (Task 2), `renderQuestionCard.headExtras` (Task 2), `isMarked`, `setMarked` (Task 1).
- Produces: `mountDrill(container, opts)` accepts two new optional options:
  - `headExtras(s) -> node` — called on every draw with the drill state `s` (`s.q` is the current question) and forwarded to `renderQuestionCard`.
  - `onMark(s)` — called when the user presses `M` while a question is shown. **The view's handler must call `drill.draw()` itself** (drill does not redraw after `onMark`), the same contract as `toolbarExtras` / `actionExtras` handlers.
  - The key hint in the action row gains ` · M mark` when `onMark` is provided.

- [ ] **Step 1: Extend `drill.js`**

(a) In the doc comment (lines 10–20) add two lines after the `actionExtras(s)` line:

```js
 *   headExtras(s)               → node placed at the right of the question-card header (optional)
 *   onMark(s)                   M key pressed while a question is shown; the handler redraws (optional)
```

(b) Replace the `renderQuestionCard` call inside `draw()` (lines 70–71) with:

```js
      renderQuestionCard({ question: s.q, bankId: opts.bankId, picked: s.picked, locked: s.locked,
        reveal: s.locked ? s.q.answer : null, onPick: (next) => { draft = next; draw(); },
        headExtras: opts.headExtras ? opts.headExtras(s) : null }),
```

(c) Replace the key-hint line (line 79) with:

```js
        el('span', { class: 'muted' }, `Keys: 1-9 / A-F pick · Enter check/next · ← →${opts.onMark ? ' · M mark' : ''}`),
```

(d) Replace the `bindKeys({ … })` call (lines 85–95) with:

```js
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
    onMark: opts.onMark ? () => { const s = state(); if (s.q) opts.onMark(s); } : undefined,
  });
```

- [ ] **Step 2: Wire Practice**

Replace `web/js/views/practice.js` with:

```js
import { mountDrill } from '../components/drill.js';
import { renderMarkToggle } from '../components/markToggle.js';
import { el } from '../dom.js';
import { checkPractice, isMarked, setMarked, setPracticeIndex } from '../progress.js';
import { store, update } from '../store.js';

export async function render(container) {
  const run = store.progress.practice;
  if (!run) { location.hash = '#/practice/setup'; return; }
  const list = store.bank.questions
    .filter((q) => q.number >= run.range[0] && q.number <= run.range[1])
    .sort((a, b) => a.number - b.number);
  if (!list.length) { location.hash = '#/practice/setup'; return; }
  let drill;

  drill = mountDrill(container, {
    bankId: store.bankId,
    list: () => list,
    index: () => store.progress.practice.index,
    setIndex: (i) => update((p) => setPracticeIndex(p, i)),
    checked: (number) => store.progress.practice.picks[String(number)] ?? null,
    onCheck: (number, picked, correct) => update((p) => checkPractice(p, number, picked, correct, new Date().toISOString())),
    label: (s) => `Q ${s.index + 1} of ${s.list.length} · range ${run.range[0]}–${run.range[1]}`,
    headExtras: (s) => renderMarkToggle({ number: s.q.number, onChange: () => drill.draw() }),
    onMark: (s) => { update((p) => setMarked(p, s.q.number, !isMarked(p, s.q.number))); drill.draw(); },
    empty: () => el('section', { class: 'card' }, 'No questions in this range.'),
  });
  return drill.unbind;
}
```

(Marking only redraws; the drill keeps its unchecked `draft` selection, so ticking the box never loses picks.)

- [ ] **Step 3: Wire Review mistakes**

In `web/js/views/review.js`:

(a) Replace the imports (lines 1–4) with:

```js
import { mountDrill } from '../components/drill.js';
import { renderMarkToggle } from '../components/markToggle.js';
import { el } from '../dom.js';
import { clearMistakes, isMarked, mistakePool, recordAttempt, removeFromMistakes, setMarked } from '../progress.js';
import { store, update } from '../store.js';
```

(b) Insert two options after the `label:` line (line 32), before `toolbarExtras:`:

```js
    headExtras: (s) => renderMarkToggle({ number: s.q.number, onChange: () => drill.draw() }),
    onMark: (s) => { update((p) => setMarked(p, s.q.number, !isMarked(p, s.q.number))); drill.draw(); },
```

- [ ] **Step 4: Verify in the browser**

Run: `node --check web/js/components/drill.js && node --check web/js/views/practice.js && node --check web/js/views/review.js && npm test`, then `uv run serve` (from the repo root).

1. Home → Practice → range 1–12 → Start new. The card header reads `#1 … ☐ Mark for future review` at the right; the key hint ends with `· M mark`.
2. Pick an option (do **not** Check), tick the box → the box stays ticked **and the pick is still selected**. Press `M` → unticked; `M` again → ticked.
3. Reload the page (resume Practice) → Q1 is still ticked. `cat data/progress/pde-2026-10.json | grep -c '"marked": true'` → `1`.
4. Answer Q2 wrong → Home → Review mistakes: the same checkbox appears on Q2; tick it; Home → Practice → Q2 → still ticked.
5. Exam → setup → Start: **no** checkbox in the running exam; `M` does nothing. Finish or leave it.

- [ ] **Step 5: Commit**

```bash
git add web/js/components/drill.js web/js/views/practice.js web/js/views/review.js
git commit -m "feat(web): mark-for-review toggle in Practice and Review mistakes"
```

---

### Task 4: Future review screen, route, Home card, CSS

**Files:**
- Create: `web/js/views/marked.js`
- Modify: `web/js/main.js` (imports lines 4–10; `routes` lines 13–16)
- Modify: `web/js/views/home.js` (import line 4; lines 15, 43–46)
- Modify: `web/app.css` (lines 38, 89)

**Interfaces:**
- Consumes: `mountDrill` with `headExtras`/`onMark` (Task 3), `renderMarkToggle` (Task 2), `markedPool`, `setMarked`, `clearMarked`, `recordAttempt` (Task 1).
- Produces: route `#/marked` → `views/marked.js` `render(container)`; Home card **Future review** linking to it.
- Behaviour (spec §4.5): list = `markedPool` re-read on every draw; label `N marked · i of N`; session-only checked state; one `remove(s)` used by the **Remove from list** button, by unticking the header checkbox, and by `M`; **Clear all** confirms; empty state.

- [ ] **Step 1: Write the view**

`web/js/views/marked.js`:

```js
import { mountDrill } from '../components/drill.js';
import { renderMarkToggle } from '../components/markToggle.js';
import { el } from '../dom.js';
import { clearMarked, markedPool, recordAttempt, setMarked } from '../progress.js';
import { store, update } from '../store.js';

/** Future review: drill through every question ticked "Mark for future review" until it is removed. */
export async function render(container) {
  let index = 0;
  const session = new Map();            // number → picked (checked during this visit)
  let drill;

  const dropCurrent = () => {           // the current question left the list: keep the index, the next one slides in
    drill.resetDraft();
    drill.draw();
  };
  const remove = (s) => {
    update((p) => setMarked(p, s.q.number, false));
    dropCurrent();
  };
  const clearAll = (s) => {
    if (!confirm(`Remove all ${s.list.length} questions from the future-review list?`)) return;
    update((p) => clearMarked(p));
    drill.draw();
  };

  drill = mountDrill(container, {
    bankId: store.bankId,
    list: () => markedPool(store.progress).map((n) => store.byNumber.get(n)).filter(Boolean),
    index: () => index,
    setIndex: (i) => { index = i; },
    checked: (number) => session.get(number) ?? null,
    onCheck: (number, picked, correct) => {
      session.set(number, picked);
      update((p) => recordAttempt(p, number, picked, correct, new Date().toISOString()));
    },
    label: (s) => `${s.list.length} marked · ${s.index + 1} of ${s.list.length}`,
    headExtras: (s) => renderMarkToggle({ number: s.q.number, onChange: dropCurrent }),   // box is always ticked here; unticking = remove
    onMark: remove,
    toolbarExtras: (s) => el('button', { class: 'btn danger', onClick: () => clearAll(s) }, 'Clear all'),
    actionExtras: (s) => [el('span', { class: 'spacer' }), el('button', { class: 'btn', onClick: () => remove(s) }, 'Remove from list')],
    empty: () => el('section', { class: 'card' },
      el('h2', {}, 'Future review'),
      el('p', { class: 'muted' }, 'Nothing marked. Tick "Mark for future review" on any question in Practice, Review mistakes or an exam result.'),
      el('a', { class: 'btn link', href: '#/' }, 'Home')),
  });
  return drill.unbind;
}
```

- [ ] **Step 2: Add the route**

In `web/js/main.js`:

(a) Add after line 10 (`import * as review …`):

```js
import * as marked from './views/marked.js';
```

(b) Replace the `routes` array (lines 13–16) with:

```js
const routes = [
  ['exam/result', examResult], ['exam/setup', examSetup], ['exam', exam],
  ['practice/setup', practiceSetup], ['practice', practice], ['review', review], ['marked', marked], ['', home],
];
```

- [ ] **Step 3: Add the Home card**

In `web/js/views/home.js`:

(a) Replace line 4 with:

```js
import { markedPool, mistakePool, overallStats } from '../progress.js';
```

(b) Insert after line 15 (`const pool = mistakePool(p);`):

```js
  const marked = markedPool(p);
```

(c) Replace the `mode-cards` section (lines 43–46) with:

```js
    el('section', { class: 'mode-cards' },
      card('#/exam/setup', 'Exam', 'Timed mock exam · default 50 questions / 120 min · shuffled options · results at the end'),
      card('#/practice/setup', 'Practice', 'Work through a range in order · instant feedback after each Check'),
      card('#/review', 'Review mistakes', pool.length ? `${pool.length} question${pool.length === 1 ? '' : 's'} to re-drill` : 'No mistakes recorded yet'),
      card('#/marked', 'Future review', marked.length ? `${marked.length} question${marked.length === 1 ? '' : 's'} marked` : 'Nothing marked yet')),
```

- [ ] **Step 4: CSS**

In `web/app.css`:

(a) Replace line 38 with:

```css
.mode-cards { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px; }
```

(b) Replace line 89 with:

```css
.toggle { display: flex; align-items: center; gap: 6px; font-size: 14px; cursor: pointer; }
```

- [ ] **Step 5: Verify in the browser**

Run: `node --check web/js/views/marked.js && node --check web/js/main.js && node --check web/js/views/home.js && npm test`, then `uv run serve`.

1. Home shows four mode cards in a 2×2 grid; the fourth reads **Future review** with `2 questions marked` (Q1 and Q2 from Task 3) — or whatever you currently have marked.
2. Click it → `#/marked` shows `2 marked · 1 of 2`, Q1, the header box ticked, buttons **Clear all** (toolbar) and **Remove from list** (action row), key hint ending `· M mark`.
3. Pick the right answer → Check → "Correct" feedback; Q1 **stays** in the list (reload → still `2 marked`).
4. On Q1 click **Remove from list** → header reads `1 marked · 1 of 1` and Q2 is shown (index kept).
5. Mark three more questions in Practice (Q3, Q4, Q5). Back in Future review on Q2 (`4 marked · 1 of 4`): untick the header box → Q3 slides in (`3 marked · 1 of 3`); press `M` → Q4 slides in (`2 marked · 1 of 2`).
6. Jump input: type `5` + Enter → Q5 (`2 of 2`). **Clear all** → confirm → empty state with the hint and a Home link. Home card now says `Nothing marked yet`.
7. `grep -c '"marked": true' data/progress/pde-2026-10.json` → `0`.

- [ ] **Step 6: Commit**

```bash
git add web/js/views/marked.js web/js/main.js web/js/views/home.js web/app.css
git commit -m "feat(web): future-review screen (#/marked) with remove and clear all"
```

---

### Task 5: Mark from exam results

**Files:**
- Modify: `web/js/views/examResult.js` (imports lines 1–6; detail lines 35–37)

**Interfaces:**
- Consumes: `renderMarkToggle` (Task 2), `renderQuestionCard.headExtras` (Task 2).
- Behaviour: in an expanded result row the question card header carries the toggle; toggling redraws the results view and the `open` set (closure state) keeps the row expanded.

- [ ] **Step 1: Add the toggle to the expanded card**

(a) Insert after line 2 (`import { renderQuestionCard } …`):

```js
import { renderMarkToggle } from '../components/markToggle.js';
```

(b) Replace the expanded-detail expression (lines 35–37) with:

```js
        expanded && q ? el('div', { class: 'result-detail' },
          renderQuestionCard({ question: q, bankId: store.bankId, picked: it.picked, locked: true, reveal: q.answer,
            headExtras: renderMarkToggle({ number: it.number, onChange: draw }) }),
          renderFeedback({ question: q, picked: it.picked })) : null);
```

- [ ] **Step 2: Verify in the browser**

Run: `node --check web/js/views/examResult.js && npm test`, then `uv run serve`.

1. Home → Exam history → open any result (take a 2-question / 1-minute exam first if the table is empty).
2. Expand a row → the card header shows `☐ Mark for future review`. Tick it → the row **stays expanded** and the box is ticked. Expand a second row and tick it too.
3. Home → the Future review card shows `2 questions marked`; open it → both questions, in ascending number order.
4. Back on the result page: untick one → Future review shows `1 marked`.

- [ ] **Step 3: Commit**

```bash
git add web/js/views/examResult.js
git commit -m "feat(web): mark-for-review toggle on exam results"
```

---

### Task 6: Docs, base-spec amendment, final verification

**Files:**
- Modify: `README.md` (lines 3, 35, 44–51)
- Modify: `docs/superpowers/specs/2026-10-09-pdf-exam-simulator-design.md` (line 16)

- [ ] **Step 1: README**

(a) Replace line 3 with:

```markdown
Local, single-user exam simulator fed by ExamTopics-style PDF dumps. Four modes: **Exam** (timed, random draw, shuffled options, results at the end), **Practice** (range in PDF order, instant feedback), **Review mistakes** (re-drill everything you ever got wrong until you remove it), **Future review** (re-drill the questions you ticked *Mark for future review* until you remove them).
```

(b) Replace line 35 with:

```markdown
Keyboard: `1–9` / `A–F` pick an option · `Enter` check / next · `←` `→` previous / next · `F` flag (exam) · `M` mark for future review (practice / review).
```

(c) Append to the manual smoke checklist after item 6:

```markdown
7. Practice: tick *Mark for future review* on Q3 → Home card shows "1 question marked" → Future review drills Q3 with Check/feedback → "Remove from list" → empty state.
8. Open a past exam result, expand a question, tick the box → it appears in Future review.
9. Reload the page → still marked; `data/progress/<bank>.json` contains `"marked": true`.
10. Future review with 2+ questions: "Clear all" → confirm → empty state; `M` toggles the mark in Practice.
```

- [ ] **Step 2: Base spec non-goal**

In `docs/superpowers/specs/2026-10-09-pdf-exam-simulator-design.md` replace line 16 with:

```markdown
- ~~Persistent bookmarks~~ — superseded by `2026-10-11-future-review-list-design.md` (the in-exam "flag" stays session-scoped).
```

- [ ] **Step 3: Final verification**

Run:

```bash
npm test
uv run pytest -q
for f in web/js/keys.js web/js/components/questionCard.js web/js/components/markToggle.js web/js/components/drill.js web/js/views/practice.js web/js/views/review.js web/js/views/marked.js web/js/main.js web/js/views/home.js web/js/views/examResult.js; do node --check "$f" || echo "SYNTAX ERROR: $f"; done
git status --short
```

Expected: `# pass 24 / # fail 0`; pytest all green (the real-PDF test runs if `source/pde_349.pdf` exists, otherwise skips); no `SYNTAX ERROR` lines; `git status` shows only the two doc files. Then walk README smoke items 7–10 once in the browser (`uv run serve`).

- [ ] **Step 4: Commit**

```bash
git add README.md docs/superpowers/specs/2026-10-09-pdf-exam-simulator-design.md
git commit -m "docs: future-review mode in README and base spec"
```
