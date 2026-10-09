/** Pure grading helpers (no DOM). */
export function isCorrect(answer, picked) {
  if (!Array.isArray(answer) || !Array.isArray(picked)) return false;
  if (answer.length === 0 || picked.length !== answer.length) return false;
  const a = [...answer].sort().join('');
  const b = [...new Set(picked)].sort().join('');
  return a === b;
}

export function pct(score, total) {
  return total ? Math.round((1000 * score) / total) / 10 : 0;
}

/** items: [{number, order, picked}]; byNumber: Map<number, question>. */
export function scoreExam(items, byNumber) {
  const graded = items.map((it) => {
    const q = byNumber.get(it.number);
    const picked = [...(it.picked || [])];
    return { number: it.number, order: it.order, picked, correct: q ? isCorrect(q.answer, picked) : false };
  });
  const score = graded.filter((g) => g.correct).length;
  return { items: graded, score, total: graded.length, pct: pct(score, graded.length) };
}
