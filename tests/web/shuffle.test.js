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
