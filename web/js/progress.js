/** Pure reducers over the progress document (spec §6). Never mutate; always return new objects. */
import { scoreExam } from './grading.js';

export function emptyProgress(bankId) {
  return { version: 1, bank_id: bankId, updated_at: null, questions: {}, exams: [], active_exam: null, practice: null };
}

const EMPTY_STAT = { attempts: 0, correct: 0, wrong: 0, last_result: null, last_answer: null, last_at: null, in_mistakes: false };

export function recordAttempt(p, number, picked, correct, atIso) {
  const key = String(number);
  const prev = p.questions[key] || EMPTY_STAT;
  const stat = {
    ...prev,
    attempts: prev.attempts + 1,
    correct: prev.correct + (correct ? 1 : 0),
    wrong: prev.wrong + (correct ? 0 : 1),
    last_result: correct ? 'correct' : 'wrong',
    last_answer: [...picked],
    last_at: atIso,
    in_mistakes: prev.in_mistakes || !correct,
  };
  return { ...p, questions: { ...p.questions, [key]: stat } };
}

export function removeFromMistakes(p, number) {
  const key = String(number);
  const stat = p.questions[key];
  if (!stat || !stat.in_mistakes) return p;
  return { ...p, questions: { ...p.questions, [key]: { ...stat, in_mistakes: false } } };
}

export function clearMistakes(p) {
  const questions = {};
  for (const [k, v] of Object.entries(p.questions)) questions[k] = v.in_mistakes ? { ...v, in_mistakes: false } : v;
  return { ...p, questions };
}

export function mistakePool(p) {
  return Object.entries(p.questions)
    .filter(([, v]) => v.in_mistakes)
    .map(([k]) => Number(k))
    .sort((a, b) => a - b);
}

export function overallStats(p) {
  let attempted = 0, attempts = 0, correct = 0;
  for (const v of Object.values(p.questions)) {
    if (v.attempts > 0) attempted++;
    attempts += v.attempts;
    correct += v.correct;
  }
  return { attempted, attempts, correct, accuracy: attempts ? Math.round((100 * correct) / attempts) : null };
}

// ---- exam ----
export function startExam(p, numbers, orders, durationS, nowIso) {
  const items = numbers.map((number, i) => ({ number, order: orders[i], picked: [], flagged: false }));
  return { ...p, active_exam: { id: nowIso, started_at: nowIso, duration_s: durationS, current: 0, items } };
}

function withActive(p, fn) {
  return p.active_exam ? { ...p, active_exam: fn(p.active_exam) } : p;
}

function withItem(active, index, fn) {
  const items = active.items.slice();
  items[index] = fn(items[index]);
  return { ...active, items };
}

export const setExamPick = (p, index, picked) =>
  withActive(p, (a) => withItem(a, index, (it) => ({ ...it, picked: [...picked] })));
export const toggleExamFlag = (p, index) =>
  withActive(p, (a) => withItem(a, index, (it) => ({ ...it, flagged: !it.flagged })));
export const setExamCurrent = (p, index) => withActive(p, (a) => ({ ...a, current: index }));
export const discardExam = (p) => ({ ...p, active_exam: null });

export function finishExam(p, active, byNumber, nowIso, autoSubmitted = false) {
  const graded = scoreExam(active.items, byNumber);
  const elapsed = Math.round((Date.parse(nowIso) - Date.parse(active.started_at)) / 1000);
  const exam = {
    id: active.id,
    started_at: active.started_at,
    finished_at: nowIso,
    duration_s: active.duration_s,
    time_used_s: Math.min(active.duration_s, Math.max(0, elapsed)),
    auto_submitted: autoSubmitted,
    items: graded.items,
    score: graded.score,
    total: graded.total,
    pct: graded.pct,
  };
  let next = p;
  for (const it of graded.items) next = recordAttempt(next, it.number, it.picked, it.correct, nowIso);
  return { ...next, exams: [...next.exams, exam], active_exam: null };
}

// ---- practice ----
export const startPractice = (p, from, to) => ({ ...p, practice: { range: [from, to], index: 0, picks: {} } });
export const setPracticeIndex = (p, index) => (p.practice ? { ...p, practice: { ...p.practice, index } } : p);

export function checkPractice(p, number, picked, correct, nowIso) {
  const next = recordAttempt(p, number, picked, correct, nowIso);
  if (!next.practice) return next;
  return { ...next, practice: { ...next.practice, picks: { ...next.practice.picks, [String(number)]: [...picked] } } };
}
