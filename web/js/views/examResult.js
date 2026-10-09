import { renderFeedback } from '../components/feedback.js';
import { renderQuestionCard } from '../components/questionCard.js';
import { PASS_PCT } from '../config.js';
import { el } from '../dom.js';
import { store } from '../store.js';
import { formatClock } from '../timer.js';

const preview = (q) => {
  const t = q.stem.find((b) => b.type === 'text');
  return t ? t.text.slice(0, 90) + (t.text.length > 90 ? '…' : '') : '';
};

export async function render(container, [id]) {
  const exam = store.progress.exams.find((e) => e.id === id);
  if (!exam) {
    container.replaceChildren(el('section', { class: 'card' }, el('h2', {}, 'Exam not found'), el('a', { class: 'btn link', href: '#/' }, 'Home')));
    return;
  }
  let wrongOnly = false;
  const open = new Set();
  const pass = exam.pct >= PASS_PCT;

  const draw = () => {
    const rows = exam.items.map((it, i) => {
      if (wrongOnly && it.correct) return null;
      const q = store.byNumber.get(it.number);
      const status = it.correct ? '✓' : it.picked.length ? '✗' : '—';
      const expanded = open.has(i);
      return el('div', { class: `result-item ${it.correct ? 'ok' : 'bad'}` },
        el('button', { class: 'result-row', onClick: () => { if (expanded) open.delete(i); else open.add(i); draw(); } },
          el('span', { class: 'status' }, status),
          el('span', {}, `Q ${i + 1} · #${it.number}`),
          el('span', { class: 'muted' }, q ? preview(q) : '(question missing from bank)'),
          el('span', { class: 'chev' }, expanded ? '▾' : '▸')),
        expanded && q ? el('div', { class: 'result-detail' },
          renderQuestionCard({ question: q, bankId: store.bankId, picked: it.picked, locked: true, reveal: q.answer }),
          renderFeedback({ question: q, picked: it.picked })) : null);
    });

    container.replaceChildren(
      el('section', { class: `card result-summary ${pass ? 'pass' : 'fail'}` },
        el('h2', {}, `${exam.score} / ${exam.total} · ${exam.pct}%`),
        el('p', {}, el('strong', {}, pass ? 'PASS' : 'FAIL'), ` (pass line ${PASS_PCT}%) · time used ${formatClock(exam.time_used_s)} of ${formatClock(exam.duration_s)}`,
          exam.auto_submitted ? ' · auto-submitted when time ran out' : ''),
        el('p', { class: 'muted' }, `Finished ${new Date(exam.finished_at).toLocaleString()}`),
        el('div', { class: 'actions' },
          el('a', { class: 'btn link', href: '#/' }, 'Home'),
          el('a', { class: 'btn', href: '#/exam/setup' }, 'New exam'),
          el('label', { class: 'toggle' }, el('input', { type: 'checkbox', checked: wrongOnly, onChange: (e) => { wrongOnly = e.target.checked; draw(); } }), 'wrong only'))),
      el('section', { class: 'results' }, rows));
  };
  draw();
}
