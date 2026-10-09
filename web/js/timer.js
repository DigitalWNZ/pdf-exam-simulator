/** Remaining whole seconds, computed from wall-clock time so refresh/sleep cannot drift it. */
export function remainingSeconds(startedAtIso, durationS, nowMs = Date.now()) {
  const elapsed = (nowMs - Date.parse(startedAtIso)) / 1000;
  return Math.max(0, Math.ceil(durationS - elapsed));
}

export function formatClock(totalSeconds) {
  const s = Math.max(0, Math.floor(totalSeconds));
  const m = Math.floor(s / 60);
  const r = s % 60;
  return `${String(m).padStart(2, '0')}:${String(r).padStart(2, '0')}`;
}
