import { mountDrill } from '../components/drill.js';
import { renderMarkToggle } from '../components/markToggle.js';
import { renderNoteEditor } from '../components/noteEditor.js';
import { el } from '../dom.js';
import { clearMarked, markedPool, recordAttempt, setMarked } from '../progress.js';
import { store, update } from '../store.js';

/** Future review: drill through every question ticked "Mark for future review" until it is removed. */
export async function render(container) {
  let index = 0;
  const session = new Map();            // number → picked (checked during this visit)
  let drill;

  const dropCurrent = () => {           // the current question left the list: keep the index, the next one slides in
    drill.resetDraft();
    drill.draw();
  };
  const remove = (s) => {
    update((p) => setMarked(p, s.q.number, false));
    dropCurrent();
  };
  const clearAll = (s) => {
    if (!confirm(`Remove all ${s.list.length} questions from the future-review list?`)) return;
    update((p) => clearMarked(p));
    drill.draw();
  };

  drill = mountDrill(container, {
    bankId: store.bankId,
    list: () => markedPool(store.progress).map((n) => store.byNumber.get(n)).filter(Boolean),
    index: () => index,
    setIndex: (i) => { index = i; },
    checked: (number) => session.get(number) ?? null,
    onCheck: (number, picked, correct) => {
      session.set(number, picked);
      update((p) => recordAttempt(p, number, picked, correct, new Date().toISOString()));
    },
    label: (s) => `${s.list.length} marked · ${s.index + 1} of ${s.list.length}`,
    headExtras: (s) => renderMarkToggle({ number: s.q.number, onChange: dropCurrent }),   // box is always ticked here; unticking = remove
    onMark: remove,
    footExtras: (s) => renderNoteEditor({ number: s.q.number, onChange: () => drill.draw() }),
    toolbarExtras: (s) => el('button', { class: 'btn danger', onClick: () => clearAll(s) }, 'Clear all'),
    actionExtras: (s) => [el('span', { class: 'spacer' }), el('button', { class: 'btn', onClick: () => remove(s) }, 'Remove from list')],
    empty: () => el('section', { class: 'card' },
      el('h2', {}, 'Future review'),
      el('p', { class: 'muted' }, 'Nothing marked. Tick "Mark for future review" on any question in Practice, Review mistakes or an exam result.'),
      el('a', { class: 'btn link', href: '#/' }, 'Home')),
  });
  return drill.unbind;
}
