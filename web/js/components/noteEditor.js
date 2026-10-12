import { el } from '../dom.js';
import { getComment, setComment } from '../progress.js';
import { store, update } from '../store.js';

/**
 * Per-question note ("Add note") rendered at the bottom of a question card.
 * Closed: the saved note (if any) + "Edit note" / "✎ Add note". Open: textarea + Save / Cancel / Delete.
 * Open editors and their unsaved text live in `drafts` (module state keyed by question number), so a
 * host redraw re-renders the editor with the draft intact and typing never triggers a redraw.
 * Saves go through store.update(); the host is asked to redraw via onChange(). Never redraws itself.
 */
const drafts = new Map();                                   // number → { text, focus }

export function renderNoteEditor({ number, onChange = () => {} }) {
  const saved = getComment(store.progress, number);
  const draft = drafts.get(number);

  if (!draft) {
    const open = () => { drafts.set(number, { text: saved, focus: true }); onChange(); };
    return el('div', { class: 'note' },
      saved ? el('div', { class: 'note-text' }, saved) : null,
      el('button', { class: 'btn link', onClick: open }, saved ? 'Edit note' : '✎ Add note'));
  }

  const close = () => { drafts.delete(number); onChange(); };
  const save = () => { update((p) => setComment(p, number, textarea.value)); close(); };
  const remove = () => { update((p) => setComment(p, number, '')); close(); };
  const textarea = el('textarea', {
    class: 'note-input', rows: 3, placeholder: 'Your note for this question…',
    onInput: () => { draft.text = textarea.value; },
    onKeydown: (e) => {
      if (e.key === 'Escape') { e.preventDefault(); close(); }
      else if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); save(); }
    },
  }, draft.text);
  if (draft.focus) {                                        // focus once, when the editor was just opened
    draft.focus = false;
    setTimeout(() => { textarea.focus(); textarea.setSelectionRange(textarea.value.length, textarea.value.length); }, 0);
  }
  return el('div', { class: 'note editing' },
    textarea,
    el('div', { class: 'actions' },
      el('button', { class: 'btn primary', onClick: save }, 'Save'),
      el('button', { class: 'btn', onClick: close }, 'Cancel'),
      saved ? el('button', { class: 'btn danger', onClick: remove }, 'Delete') : null));
}
