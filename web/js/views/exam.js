import { renderNavigator } from '../components/navigator.js';
import { renderQuestionCard, togglePick } from '../components/questionCard.js';
import { TIMER_WARN_S } from '../config.js';
import { el } from '../dom.js';
import { bindKeys } from '../keys.js';
import { finishExam, setExamCurrent, setExamPick, toggleExamFlag } from '../progress.js';
import { flush, store, update } from '../store.js';
import { formatClock, remainingSeconds } from '../timer.js';

export async function render(container) {
  if (!store.progress.active_exam) { location.hash = '#/exam/setup'; return; }
  let finished = false;

  const finish = async (auto) => {
    if (finished) return;
    finished = true;
    const active = store.progress.active_exam;
    update((p) => finishExam(p, active, store.byNumber, new Date().toISOString(), auto));
    await flush();
    location.hash = `#/exam/result/${encodeURIComponent(active.id)}`;
  };

  const first = store.progress.active_exam;
  if (remainingSeconds(first.started_at, first.duration_s) <= 0) { await finish(true); return; }

  const clock = el('span', { class: 'clock' });
  const tick = () => {
    const a = store.progress.active_exam;
    if (!a || finished) return;
    const s = remainingSeconds(a.started_at, a.duration_s);
    clock.textContent = formatClock(s);
    clock.classList.toggle('warn', s <= TIMER_WARN_S);
    if (s <= 0) finish(true);
  };
  const interval = setInterval(tick, 500);

  const state = () => {
    const a = store.progress.active_exam;
    const i = Math.min(Math.max(a.current, 0), a.items.length - 1);
    return { a, i, item: a.items[i], q: store.byNumber.get(a.items[i].number) };
  };
  const go = (i) => { const { a } = state(); if (i < 0 || i >= a.items.length) return; update((p) => setExamCurrent(p, i)); draw(); };
  const pick = (next) => { const { i } = state(); update((p) => setExamPick(p, i, next)); draw(); };
  const flag = () => { const { i } = state(); update((p) => toggleExamFlag(p, i)); draw(); };
  const confirmFinish = () => {
    const { a } = state();
    const unanswered = a.items.filter((it) => !it.picked.length).length;
    const msg = unanswered
      ? `${unanswered} question${unanswered === 1 ? ' is' : 's are'} unanswered and will count as wrong. Finish anyway?`
      : 'Finish the exam and see your results?';
    if (confirm(msg)) finish(false);
  };

  const draw = () => {
    if (finished || !store.progress.active_exam) return;
    const { a, i, item, q } = state();
    tick();
    container.replaceChildren(
      el('div', { class: 'toolbar' },
        el('span', { class: 'progress-label' }, `Q ${i + 1} / ${a.items.length}`),
        clock,
        el('span', { class: 'spacer' }),
        el('button', { class: `btn${item.flagged ? ' active' : ''}`, onClick: flag }, item.flagged ? '⚑ Flagged' : '⚐ Flag'),
        el('button', { class: 'btn danger', onClick: confirmFinish }, 'Finish')),
      q ? renderQuestionCard({ question: q, bankId: store.bankId, order: item.order, picked: item.picked, onPick: pick })
        : el('section', { class: 'card' }, `Question #${item.number} is missing from this bank.`),
      el('div', { class: 'actions' },
        el('button', { class: 'btn', disabled: i === 0, onClick: () => go(i - 1) }, '← Prev'),
        el('button', { class: 'btn primary', disabled: i === a.items.length - 1, onClick: () => go(i + 1) }, 'Next →'),
        el('span', { class: 'muted' }, 'Keys: 1-9 / A-F pick · F flag · Enter next · ← →')),
      renderNavigator({ items: a.items, current: i, onJump: go }));
  };
  draw();

  const unbind = bindKeys({
    onOption: (k) => { const { item, q } = state(); if (!q) return; const next = togglePick({ question: q, order: item.order, picked: item.picked }, k); if (next) pick(next); },
    onEnter: () => go(state().i + 1),
    onPrev: () => go(state().i - 1),
    onNext: () => go(state().i + 1),
    onFlag: flag,
  });
  return () => { clearInterval(interval); unbind(); };
}
