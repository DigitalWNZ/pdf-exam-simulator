import { el } from '../dom.js';
import { isCorrect } from '../grading.js';

const fmt = (letters) => (letters && letters.length ? letters.join(', ') : '—');

function disputedText(q) {
  if (!q.disputed) return null;
  if (q.answer_source === 'votes') return `Disputed: the key follows the community vote (${fmt(q.answer)}); the PDF says ${fmt(q.pdf_answer)}.`;
  if (q.answer_source === 'votes_tiebreak_pdf') return `Community vote is tied — tie broken by the PDF answer (${fmt(q.answer)}).`;
  if (q.answer_source === 'votes_tie_first') return `Community vote is tied and the PDF answer (${fmt(q.pdf_answer)}) is not among the tied options — first tied option (${fmt(q.answer)}) used.`;
  return 'Disputed answer.';
}

export function renderFeedback({ question: q, picked }) {
  const correct = isCorrect(q.answer, picked);
  const votes = q.votes.length
    ? el('div', { class: 'votes' },
      el('div', { class: 'votes-title' }, 'Community vote'),
      q.votes.map((v) => el('div', { class: 'vote-row' },
        el('span', { class: 'vote-letters' }, v.letters.join('')),
        el('div', { class: 'vote-bar' }, el('div', { class: 'vote-fill', style: `width:${Math.min(100, v.pct)}%` })),
        el('span', { class: 'vote-pct' }, `${v.pct}%`))))
    : el('div', { class: 'votes-title' }, 'No community vote data — key taken from the PDF answer');
  const note = disputedText(q);
  return el('section', { class: `feedback ${correct ? 'correct' : 'wrong'}` },
    el('div', { class: 'verdict' }, correct ? '✓ Correct' : `✗ Wrong — correct answer: ${fmt(q.answer)}`),
    el('div', { class: 'muted' }, `Your answer: ${fmt(picked)} · PDF answer: ${fmt(q.pdf_answer)}`),
    votes,
    note ? el('div', { class: 'disputed' }, note) : null);
}
