import { test } from 'node:test';
import assert from 'node:assert/strict';
import { formatClock, remainingSeconds } from '../../web/js/timer.js';

test('remainingSeconds counts down from started_at using wall-clock time', () => {
  const start = '2026-01-01T00:00:00.000Z';
  const t0 = Date.parse(start);
  assert.equal(remainingSeconds(start, 120, t0), 120);
  assert.equal(remainingSeconds(start, 120, t0 + 30_000), 90);
  assert.equal(remainingSeconds(start, 120, t0 + 119_400), 1);
  assert.equal(remainingSeconds(start, 120, t0 + 120_000), 0);
  assert.equal(remainingSeconds(start, 120, t0 + 999_000), 0);
});

test('formatClock renders mm:ss and allows minutes above 99', () => {
  assert.equal(formatClock(0), '00:00');
  assert.equal(formatClock(65), '01:05');
  assert.equal(formatClock(7200), '120:00');
});
