import os from "node:os";
import path from "node:path";

/**
 * The Tafwid home the e2e web server reads (TAFWID_HOME) and the tests write
 * into. A fixed path, so the config, the global setup and the workers agree
 * on it, and never the real ~/.tafwid.
 */
export const E2E_HOME = path.join(os.tmpdir(), "tafwid-agent-world-e2e");
