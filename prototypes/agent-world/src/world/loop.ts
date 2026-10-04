/**
 * How the world drives its frames. Animation frames by default: the browser
 * pauses them for a truly hidden tab, so the world never needs to check
 * `document.hidden` itself. Some hosts (an embedded browser pane, for one)
 * report the page hidden while they keep painting it and running frames, and
 * the world must still draw there. Only the hidden-render debug mode, used for
 * evidence capture in a background tab, falls back to a timer.
 */
export function loopDriver(hidden: boolean, renderHidden: boolean): "frames" | "timer" {
  return hidden && renderHidden ? "timer" : "frames";
}

/** True when every component is a finite number. */
export function finite(v: readonly number[]): boolean {
  return v.every(Number.isFinite);
}

/** A console warning that is logged once per key. */
export function warnOnce() {
  const seen = new Set<string>();
  return (key: string, message: string) => {
    if (seen.has(key)) return;
    seen.add(key);
    console.warn(message);
  };
}
