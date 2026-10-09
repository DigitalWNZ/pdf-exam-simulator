import { EXAM_DEFAULTS, EXAM_LIMITS } from '../config.js';
import { el } from '../dom.js';
import { discardExam, startExam } from '../progress.js';
import { fisherYates, sampleWithoutReplacement } from '../shuffle.js';
import { store, update } from '../store.js';

export async function render(container) {
  const qs = store.bank.questions;
  const active = store.progress.active_exam;
  const count = el('input', { type: 'number', min: 1, max: qs.length, value: Math.min(EXAM_DEFAULTS.count, qs.length) });
  const minutes = el('input', { type: 'number', min: EXAM_LIMITS.minMinutes, max: EXAM_LIMITS.maxMinutes, value: EXAM_DEFAULTS.minutes });
  const err = el('p', { class: 'error-text' });

  const start = () => {
    const n = Number(count.value);
    const m = Number(minutes.value);
    if (!Number.isInteger(n) || n < 1 || n > qs.length) { err.textContent = `Question count must be between 1 and ${qs.length}.`; return; }
    if (!Number.isInteger(m) || m < EXAM_LIMITS.minMinutes || m > EXAM_LIMITS.maxMinutes) {
      err.textContent = `Minutes must be between ${EXAM_LIMITS.minMinutes} and ${EXAM_LIMITS.maxMinutes}.`;
      return;
    }
    const chosen = sampleWithoutReplacement(qs, n);
    const numbers = chosen.map((q) => q.number);
    const orders = chosen.map((q) => fisherYates(q.options.map((o) => o.letter)));
    update((p) => startExam(p, numbers, orders, m * 60, new Date().toISOString()));
    location.hash = '#/exam';
  };

  const discard = () => {
    if (!confirm('Discard the exam in progress? It will not be scored.')) return;
    update((p) => discardExam(p));
    render(container);
  };

  container.replaceChildren(el('section', { class: 'card' },
    el('h2', {}, 'Exam'),
    active ? el('div', { class: 'banner warn' }, 'An exam is already in progress. ',
      el('a', { class: 'btn', href: '#/exam' }, 'Resume it'), ' ',
      el('button', { class: 'btn danger', onClick: discard }, 'Discard')) : null,
    el('div', { class: 'form-row' }, el('label', {}, 'Questions', count), el('label', {}, 'Minutes', minutes)),
    el('p', { class: 'muted' }, `${qs.length} questions in this bank. Random draw, shuffled options, no feedback until you finish. Unanswered questions count as wrong.`),
    err,
    el('div', { class: 'actions' },
      el('button', { class: 'btn primary', disabled: !!active, onClick: start }, 'Start exam'),
      el('a', { class: 'btn link', href: '#/' }, 'Back'))));
}
