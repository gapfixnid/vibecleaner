/** True when the keyboard focus is inside a text-editing element, so global
 *  shortcuts must not fire (shared by app-chrome and canvas shortcut hooks). */
export function isTextInputFocused(): boolean {
  const active = document.activeElement as HTMLElement | null;
  if (!active) return false;
  const tag = active.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || tag === "select" || active.isContentEditable;
}
