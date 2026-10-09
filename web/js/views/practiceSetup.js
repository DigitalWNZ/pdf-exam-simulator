import { el } from '../dom.js';
import { startPractice } from '../progress.js';
import { store, update } from '../store.js';

export const countInRange = (numbers, [a, b]) => numbers.filter((n) => n >= a && n <= b).length;

export async function render(container) {
  const numbers = store.bank.questions.map((q) => q.number);
  const min = Math.min(...numbers);
  const max = Math.max(...numbers);
  const prev = store.progress.practice;
  const from = el('input', { type: 'number', min, max, value: prev ? prev.range[0] : min });
  const to = el('input', { type: 'number', min, max, value: prev ? prev.range[1] : max });
  const err = el('p', { class: 'error-text' });

  const start = () => {
    const a = Number(from.value);
    const b = Number(to.value);
    if (!Number.isInteger(a) || !Number.isInteger(b) || a < min || b > max || a > b) {
      err.textContent = `Enter a range between ${min} and ${max} (from ≤ to).`;
      return;
    }
    if (!countInRange(numbers, [a, b])) { err.textContent = 'No questions in that range.'; return; }
    update((p) => startPractice(p, a, b));
    location.hash = '#/practice';
  };

  const resume = prev
    ? el('button', { class: 'btn', onClick: () => { location.hash = '#/practice'; } },
      `Resume (Q ${prev.index + 1} of ${countInRange(numbers, prev.range)}, range ${prev.range[0]}–${prev.range[1]})`)
    : null;

  container.replaceChildren(el('section', { class: 'card' },
    el('h2', {}, 'Practice'),
    el('p', { class: 'muted' }, `Questions #${min}–#${max} in PDF order. Pick a range; feedback after each Check.`),
    el('div', { class: 'form-row' }, el('label', {}, 'From #', from), el('label', {}, 'To #', to)),
    err,
    el('div', { class: 'actions' },
      el('button', { class: 'btn primary', onClick: start }, 'Start new'),
      resume,
      el('a', { class: 'btn link', href: '#/' }, 'Back'))));
}
