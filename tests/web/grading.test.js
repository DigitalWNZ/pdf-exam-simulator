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
