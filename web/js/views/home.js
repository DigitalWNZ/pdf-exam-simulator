import * as api from '../api.js';
import { PASS_PCT } from '../config.js';
import { el } from '../dom.js';
import { markedPool, mistakePool, overallStats } from '../progress.js';
import { flush, loadBank, store } from '../store.js';
import { formatClock } from '../timer.js';

const stat = (value, label) => el('div', { class: 'stat' }, el('div', { class: 'stat-value' }, value), el('div', { class: 'stat-label' }, label));
const card = (href, title, text) => el('a', { class: 'mode-card', href }, el('h3', {}, title), el('p', {}, text));

export async function render(container) {
  const banks = await api.listBanks();
  const p = store.progress;
  const stats = overallStats(p);
  const pool = mistakePool(p);
  const marked = markedPool(p);
  const total = store.bank.questions.length;

  const select = el('select', { class: 'bank-select', onChange: async (e) => {
    await flush();
    await loadBank(e.target.value);
    document.getElementById('bank-label').textContent = store.bank.bank.title;
    render(container);
  } }, banks.map((b) => el('option', { value: b.id, selected: b.id === store.bankId }, `${b.title} (${b.question_count})`)));

  const active = p.active_exam;
  const resume = active ? el('a', { class: 'banner', href: '#/exam' },
    `▶ Resume exam in progress — ${active.items.filter((i) => i.picked.length).length}/${active.items.length} answered`) : null;

  const history = [...p.exams].reverse().slice(0, 20).map((ex) => el('tr', {
    class: 'row-link', onClick: () => { location.hash = `#/exam/result/${encodeURIComponent(ex.id)}`; },
  },
    el('td', {}, new Date(ex.finished_at).toLocaleString()),
    el('td', {}, `${ex.score}/${ex.total} (${ex.pct}%)`),
    el('td', { class: ex.pct >= PASS_PCT ? 'pass' : 'fail' }, ex.pct >= PASS_PCT ? 'PASS' : 'FAIL'),
    el('td', {}, formatClock(ex.time_used_s) + (ex.auto_submitted ? ' ⏰' : ''))));

  container.replaceChildren(
    el('section', { class: 'card' }, el('label', {}, 'Question bank: ', select)),
    ...(resume ? [resume] : []),
    el('section', { class: 'stats' },
      stat(total, 'questions'), stat(stats.attempted, 'attempted'),
      stat(stats.accuracy == null ? '—' : `${stats.accuracy}%`, 'accuracy'), stat(pool.length, 'mistakes')),
    el('section', { class: 'mode-cards' },
      card('#/exam/setup', 'Exam', 'Timed mock exam · default 50 questions / 120 min · shuffled options · results at the end'),
      card('#/practice/setup', 'Practice', 'Work through a range in order · instant feedback after each Check'),
      card('#/review', 'Review mistakes', pool.length ? `${pool.length} question${pool.length === 1 ? '' : 's'} to re-drill` : 'No mistakes recorded yet'),
      card('#/marked', 'Future review', marked.length ? `${marked.length} question${marked.length === 1 ? '' : 's'} marked` : 'Nothing marked yet')),
    el('section', { class: 'card' }, el('h2', {}, 'Exam history'),
      history.length
        ? el('table', { class: 'history' },
          el('thead', {}, el('tr', {}, el('th', {}, 'Finished'), el('th', {}, 'Score'), el('th', {}, 'Result'), el('th', {}, 'Time'))),
          el('tbody', {}, history))
        : el('p', { class: 'muted' }, 'No exams taken yet.')));
}
