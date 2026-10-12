import { mountDrill } from '../components/drill.js';
import { renderMarkToggle } from '../components/markToggle.js';
import { renderNoteEditor } from '../components/noteEditor.js';
import { el } from '../dom.js';
import { clearMistakes, isMarked, mistakePool, recordAttempt, removeFromMistakes, setMarked } from '../progress.js';
import { store, update } from '../store.js';

export async function render(container) {
  let index = 0;
  const session = new Map();            // number → picked (checked during this visit)
  let drill;

  const remove = (s) => {
    update((p) => removeFromMistakes(p, s.q.number));
    drill.resetDraft();
    drill.draw();                       // index is kept; the next pooled question slides in
  };
  const clearAll = (s) => {
    if (!confirm(`Remove all ${s.list.length} questions from the mistakes pool?`)) return;
    update((p) => clearMistakes(p));
    drill.draw();
  };

  drill = mountDrill(container, {
    bankId: store.bankId,
    list: () => mistakePool(store.progress).map((n) => store.byNumber.get(n)).filter(Boolean),
    index: () => index,
    setIndex: (i) => { index = i; },
    checked: (number) => session.get(number) ?? null,
    onCheck: (number, picked, correct) => {
      session.set(number, picked);
      update((p) => recordAttempt(p, number, picked, correct, new Date().toISOString()));
    },
    label: (s) => `${s.list.length} mistake${s.list.length === 1 ? '' : 's'} · ${s.index + 1} of ${s.list.length}`,
    headExtras: (s) => renderMarkToggle({ number: s.q.number, onChange: () => drill.draw() }),
    onMark: (s) => { update((p) => setMarked(p, s.q.number, !isMarked(p, s.q.number))); drill.draw(); },
    footExtras: (s) => renderNoteEditor({ number: s.q.number, onChange: () => drill.draw() }),
    toolbarExtras: (s) => el('button', { class: 'btn danger', onClick: () => clearAll(s) }, 'Clear all'),
    actionExtras: (s) => [el('span', { class: 'spacer' }), el('button', { class: 'btn', onClick: () => remove(s) }, 'Remove from mistakes')],
    empty: () => el('section', { class: 'card' },
      el('h2', {}, 'Review mistakes'),
      el('p', { class: 'muted' }, 'The pool is empty. Questions you answer wrong in Exam or Practice will appear here.'),
      el('a', { class: 'btn link', href: '#/' }, 'Home')),
  });
  return drill.unbind;
}
