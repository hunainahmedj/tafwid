// Incremental reader for the plugin's activity log. Read-only: it never
// writes to the state directory.
import { closeSync, openSync, readSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import type { HookEvent, WorldEvent } from "../src/live/types";

export interface Tailer {
  /** New complete events since the previous call, oldest file first. */
  poll(): WorldEvent[];
  /** Number of malformed lines skipped so far. */
  malformed(): number;
}

const FILE_PATTERN = /^events-(\d{4}-\d{2}-\d{2})\.jsonl$/;

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** The hook names its files by local date. */
export function dayStamp(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

function isHookEvent(value: unknown): value is HookEvent {
  if (typeof value !== "object" || value === null || Array.isArray(value)) return false;
  const e = value as Record<string, unknown>;
  // Run events come only from the bridge's own run reader, never from the log.
  return (
    e.v === 1 &&
    typeof e.t === "number" &&
    Number.isFinite(e.t) &&
    typeof e.event === "string" &&
    e.event !== "run" &&
    typeof e.session === "string"
  );
}

/**
 * Tail today's and yesterday's log files in `dir`. The first poll reads both
 * from offset 0; later polls read only appended bytes. A trailing line
 * without a newline is held back until the newline arrives. After midnight
 * the previous day's file is still read to its end while the new file starts.
 */
export function createTailer(dir: string, clock: () => Date = () => new Date()): Tailer {
  const offsets = new Map<string, number>();
  let skipped = 0;

  function readFile(name: string): WorldEvent[] {
    const path = join(dir, name);
    let size: number;
    try {
      size = statSync(path).size;
    } catch {
      offsets.delete(name);
      return [];
    }
    let offset = offsets.get(name) ?? 0;
    if (size < offset) offset = 0; // truncated or replaced: start over
    if (size === offset) {
      offsets.set(name, offset);
      return [];
    }
    const buffer = Buffer.alloc(size - offset);
    let fd: number | undefined;
    let filled = 0;
    try {
      fd = openSync(path, "r");
      while (filled < buffer.length) {
        const n = readSync(fd, buffer, filled, buffer.length - filled, offset + filled);
        if (n === 0) break;
        filled += n;
      }
    } catch {
      return [];
    } finally {
      if (fd !== undefined) closeSync(fd);
    }
    const end = buffer.subarray(0, filled).lastIndexOf(0x0a);
    if (end < 0) return []; // only a partial line so far; offset stays put
    offsets.set(name, offset + end + 1);
    const events: WorldEvent[] = [];
    for (const raw of buffer.subarray(0, end).toString("utf8").split("\n")) {
      const text = raw.trim();
      if (!text) continue;
      try {
        const parsed: unknown = JSON.parse(text);
        if (isHookEvent(parsed)) events.push(parsed);
        else skipped += 1;
      } catch {
        skipped += 1;
      }
    }
    return events;
  }

  return {
    poll() {
      const now = clock();
      const yesterday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 12);
      const wanted = new Set([dayStamp(yesterday), dayStamp(now)]);
      let present: string[];
      try {
        present = readdirSync(dir);
      } catch {
        return [];
      }
      const names = present
        .filter((name) => {
          const match = FILE_PATTERN.exec(name);
          return match !== null && wanted.has(match[1]);
        })
        .sort();
      for (const name of [...offsets.keys()]) if (!names.includes(name)) offsets.delete(name);
      return names.flatMap(readFile);
    },
    malformed: () => skipped,
  };
}
