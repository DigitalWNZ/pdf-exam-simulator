import { mountDrill } from '../components/drill.js';
import { el } from '../dom.js';
import { checkPractice, setPracticeIndex } from '../progress.js';
import { store, update } from '../store.js';

export async function render(container) {
  const run = store.progress.practice;
  if (!run) { location.hash = '#/practice/setup'; return; }
  const list = store.bank.questions
    .filter((q) => q.number >= run.range[0] && q.number <= run.range[1])
    .sort((a, b) => a.number - b.number);
  if (!list.length) { location.hash = '#/practice/setup'; return; }

  const drill = mountDrill(container, {
    bankId: store.bankId,
    list: () => list,
    index: () => store.progress.practice.index,
    setIndex: (i) => update((p) => setPracticeIndex(p, i)),
    checked: (number) => store.progress.practice.picks[String(number)] ?? null,
    onCheck: (number, picked, correct) => update((p) => checkPractice(p, number, picked, correct, new Date().toISOString())),
    label: (s) => `Q ${s.index + 1} of ${s.list.length} · range ${run.range[0]}–${run.range[1]}`,
    empty: () => el('section', { class: 'card' }, 'No questions in this range.'),
  });
  return drill.unbind;
}
