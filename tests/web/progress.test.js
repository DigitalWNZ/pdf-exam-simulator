import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  checkPractice, clearMarked, clearMistakes, discardExam, emptyProgress, finishExam, isMarked, markedPool,
  mistakePool, overallStats, recordAttempt, removeFromMistakes, setExamCurrent, setExamPick, setMarked,
  setPracticeIndex, startExam, startPractice, toggleExamFlag,
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
    attempts: 1, correct: 0, wrong: 1, last_result: 'wrong', last_answer: ['B'], last_at: T, in_mistakes: true, marked: false,
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
