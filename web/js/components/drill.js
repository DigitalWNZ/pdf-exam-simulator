import { el } from '../dom.js';
import { isCorrect } from '../grading.js';
import { bindKeys } from '../keys.js';
import { renderFeedback } from './feedback.js';
import { renderQuestionCard, togglePick } from './questionCard.js';

/**
 * Shared "pick → Check → feedback → Next" loop used by Practice and Review.
 *
 * opts:
 *   bankId                      for image URLs
 *   list()                      → current question list (re-read on every draw; Review's pool shrinks)
 *   index()                     → current index into list() (clamped on read)
 *   setIndex(i)                 record a new index
 *   checked(number)             → picked[] if already checked in this run, else null
 *   onCheck(number, picked, correct)   record a checked answer
 *   label(s)                    → progress-label text
 *   toolbarExtras(s)            → node(s) placed before "Home" (optional)
 *   actionExtras(s)             → node(s) appended to the action row (optional)
 *   headExtras(s)               → node placed at the right of the question-card header (optional)
 *   footExtras(s)               → node appended at the bottom of the question card (optional)
 *   onMark(s)                   M key pressed while a question is shown; the handler redraws (optional)
 *   empty()                     → node shown when list() is empty
 *
 * Returns { unbind, draw, resetDraft }.
 */
export function mountDrill(container, opts) {
  let draft = [];                       // selection not yet checked

  const state = () => {
    const list = opts.list();
    if (!list.length) return { list, q: null };
    const index = Math.min(Math.max(opts.index(), 0), list.length - 1);
    const q = list[index];
    const checked = opts.checked(q.number);
    const locked = Array.isArray(checked);
    const picked = locked ? checked : draft;
    return { list, index, q, locked, picked, canCheck: !locked && picked.length === q.select_count };
  };

  const go = (i) => {
    const s = state();
    if (!s.q || i < 0 || i >= s.list.length) return;
    draft = [];
    opts.setIndex(i);
    draw();
  };

  const check = () => {
    const s = state();
    if (!s.q || !s.canCheck) return;
    opts.onCheck(s.q.number, s.picked, isCorrect(s.q.answer, s.picked));
    draft = [];
    draw();
  };

  const draw = () => {
    const s = state();
    if (!s.q) { container.replaceChildren(opts.empty()); return; }
    const jump = el('input', { type: 'number', class: 'jump', placeholder: '#', onKeydown: (e) => {
      if (e.key !== 'Enter') return;
      const i = s.list.findIndex((x) => x.number === Number(jump.value));
      if (i >= 0) go(i);
    } });
    // replaceChildren() stringifies null ("null" text node) — filter optional nodes first.
    container.replaceChildren(...[
      el('div', { class: 'toolbar' },
        el('span', { class: 'progress-label' }, opts.label(s)),
        el('span', { class: 'spacer' }),
        el('label', { class: 'muted' }, 'Go to # ', jump),
        opts.toolbarExtras ? opts.toolbarExtras(s) : null,
        el('a', { class: 'btn link', href: '#/' }, 'Home')),
      renderQuestionCard({ question: s.q, bankId: opts.bankId, picked: s.picked, locked: s.locked,
        reveal: s.locked ? s.q.answer : null, onPick: (next) => { draft = next; draw(); },
        headExtras: opts.headExtras ? opts.headExtras(s) : null,
        footExtras: opts.footExtras ? opts.footExtras(s) : null }),
      s.locked ? renderFeedback({ question: s.q, picked: s.picked }) : null,
      el('div', { class: 'actions' },
        el('button', { class: 'btn', disabled: s.index === 0, onClick: () => go(s.index - 1) }, '← Prev'),
        s.locked
          ? el('button', { class: 'btn primary', disabled: s.index === s.list.length - 1, onClick: () => go(s.index + 1) }, 'Next →')
          : el('button', { class: 'btn primary', disabled: !s.canCheck, onClick: check }, 'Check'),
        s.locked ? null : el('button', { class: 'btn', disabled: s.index === s.list.length - 1, onClick: () => go(s.index + 1) }, 'Skip →'),
        el('span', { class: 'muted' }, `Keys: 1-9 / A-F pick · Enter check/next · ← →${opts.onMark ? ' · M mark' : ''}`),
        opts.actionExtras ? opts.actionExtras(s) : null),
    ].filter(Boolean));
  };

  draw();
  const unbind = bindKeys({
    onOption: (i) => {
      const s = state();
      if (!s.q || s.locked) return;
      const next = togglePick({ question: s.q, picked: s.picked }, i);
      if (next) { draft = next; draw(); }
    },
    onEnter: () => { const s = state(); if (!s.q) return; if (s.locked) go(s.index + 1); else check(); },
    onPrev: () => { const s = state(); if (s.q) go(s.index - 1); },
    onNext: () => { const s = state(); if (s.q) go(s.index + 1); },
    onMark: opts.onMark ? () => { const s = state(); if (s.q) opts.onMark(s); } : undefined,
  });
  return { unbind, draw, resetDraft: () => { draft = []; } };
}
