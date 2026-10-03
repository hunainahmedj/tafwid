/** Tiny element builder. Text is always set via textContent, never parsed as HTML. */
export function h<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  props: Record<string, string | boolean | undefined> = {},
  ...children: (Node | string | null | undefined | false)[]
): HTMLElementTagNameMap[K] {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (v === undefined || v === false) continue;
    if (k === "class") el.className = String(v);
    else if (k === "text") el.textContent = String(v);
    else el.setAttribute(k, v === true ? "" : String(v));
  }
  for (const c of children) if (c !== null && c !== undefined && c !== false) el.append(c);
  return el;
}

export function formatElapsed(minutes: number | null): string {
  if (minutes === null) return "No active task";
  if (minutes < 1) return "Just started";
  return `${minutes}m elapsed`;
}

/**
 * Makes `parent`'s children exactly `wanted`, in order, moving only the nodes
 * that are out of place. Moving or removing a node drops its keyboard focus,
 * so a focused row that is already where it belongs is never touched.
 */
export function reconcile(parent: Element, wanted: Node[]): void {
  wanted.forEach((node, i) => {
    if (parent.childNodes[i] !== node) parent.insertBefore(node, parent.childNodes[i] ?? null);
  });
  while (parent.childNodes.length > wanted.length) parent.lastChild!.remove();
}

/** A project's display name; an empty project (no working directory known) has none. */
export const projectName = (project: string) => project || "Unknown project";
