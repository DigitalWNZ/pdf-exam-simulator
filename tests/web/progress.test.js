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
