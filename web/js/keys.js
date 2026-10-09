/**
 * Keyboard shortcuts for question screens. Ignores typing in text/number inputs and
 * lets focused buttons/links handle Enter themselves (avoids double actions).
 *  1-9 / A-I → onOption(displayIndex) · F → onFlag (if given, else F is option 6)
 *  Enter → onEnter · ArrowLeft → onPrev · ArrowRight → onNext
 */
export function bindKeys({ onOption, onEnter, onPrev, onNext, onFlag } = {}) {
  const handler = (e) => {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
    const target = e.target || {};
    const tag = target.tagName || '';
    if (tag === 'TEXTAREA' || tag === 'SELECT') return;
    if (tag === 'INPUT' && target.type !== 'radio' && target.type !== 'checkbox') return;
    const k = e.key;
    if (k === 'Enter' && (tag === 'BUTTON' || tag === 'A')) return;
    if ((k === 'f' || k === 'F') && onFlag) { onFlag(); e.preventDefault(); return; }
    if (/^[1-9]$/.test(k) && onOption) { onOption(Number(k) - 1); e.preventDefault(); return; }
    if (/^[a-iA-I]$/.test(k) && onOption) { onOption(k.toUpperCase().charCodeAt(0) - 65); e.preventDefault(); return; }
    if (k === 'Enter' && onEnter) { onEnter(); e.preventDefault(); return; }
    if (k === 'ArrowLeft' && onPrev) { onPrev(); e.preventDefault(); return; }
    if (k === 'ArrowRight' && onNext) { onNext(); e.preventDefault(); }
  };
  document.addEventListener('keydown', handler);
  return () => document.removeEventListener('keydown', handler);
}
