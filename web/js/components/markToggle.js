import { el } from '../dom.js';
import { isMarked, setMarked } from '../progress.js';
import { store, update } from '../store.js';

/**
 * "Mark for future review" checkbox for one question. Reads the flag from store.progress when
 * rendered, persists changes through store.update(), then calls onChange() so the host view can
 * redraw itself. Never redraws anything on its own.
 */
export function renderMarkToggle({ number, onChange = () => {} }) {
  const input = el('input', {
    type: 'checkbox',
    checked: isMarked(store.progress, number),
    onChange: () => { update((p) => setMarked(p, number, input.checked)); onChange(); },
  });
  return el('label', { class: 'toggle' }, input, 'Mark for future review');
}
