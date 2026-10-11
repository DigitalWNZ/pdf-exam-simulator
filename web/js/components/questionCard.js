import { imageUrl } from '../api.js';
import { el } from '../dom.js';

export function renderBlocks(blocks, bankId) {
  return blocks.map((b) => (b.type === 'image'
    ? el('img', { class: 'block-image', src: imageUrl(bankId, b.src), alt: 'question image', loading: 'lazy' })
    : el('p', { class: 'block-text' }, b.text)));
}

function displayLetters(question, order) {
  return order || question.options.map((o) => o.letter);
}

/**
 * order: original letters in display order (null = PDF order). picked: original letters.
 * reveal: key letters to highlight after checking (null while answering).
 */
export function renderQuestionCard({ question, bankId, order = null, picked = [], locked = false, reveal = null, onPick = () => {}, headExtras = null }) {
  const letters = displayLetters(question, order);
  const byLetter = new Map(question.options.map((o) => [o.letter, o]));
  const multi = question.select_count > 1;
  const full = multi && picked.length >= question.select_count;

  const rows = letters.map((orig, i) => {
    const opt = byLetter.get(orig);
    if (!opt) return null;
    const display = String.fromCharCode(65 + i);
    const isPicked = picked.includes(orig);
    const classes = ['option'];
    if (isPicked) classes.push('picked');
    if (reveal) {
      if (reveal.includes(orig)) classes.push('is-key');
      else if (isPicked) classes.push('is-wrong-pick');
    }
    const input = el('input', {
      type: multi ? 'checkbox' : 'radio', name: `q${question.number}`, value: orig,
      checked: isPicked, disabled: locked || (full && !isPicked),
      onChange: () => {
        if (!multi) return onPick([orig]);
        if (input.checked) return onPick([...picked, orig]);
        return onPick(picked.filter((l) => l !== orig));
      },
    });
    return el('label', { class: classes.join(' '), dataset: { letter: orig, index: String(i) } },
      input, el('span', { class: 'letter' }, `${display}.`), el('div', { class: 'content' }, renderBlocks(opt.content, bankId)));
  });

  return el('article', { class: 'question-card' },
    el('header', { class: 'question-head' },
      el('span', { class: 'qnum' }, `#${question.number}`),
      multi ? el('span', { class: 'hint' }, `Choose ${question.select_count}`) : null,
      headExtras ? [el('span', { class: 'spacer' }), headExtras] : null),
    el('div', { class: 'stem' }, renderBlocks(question.stem, bankId)),
    el('div', { class: 'options' }, rows));
}

/** Keyboard toggle of the option at display index i. Returns the next picked[] or null if not allowed. */
export function togglePick({ question, order = null, picked = [] }, i) {
  const orig = displayLetters(question, order)[i];
  if (!orig) return null;
  if (question.select_count <= 1) return [orig];
  if (picked.includes(orig)) return picked.filter((l) => l !== orig);
  if (picked.length >= question.select_count) return null;
  return [...picked, orig];
}
