#!/usr/bin/env node
/**
 * tokenstats — token usage statistics for AI coding agents.
 * Zero telemetry. Zero network. Zero data collection.
 *
 * Thin wrapper that runs the Python analyzer.
 * Requires Python 3 (installed by default on macOS and most Linux distros).
 */

import { execSync } from "child_process";
import { fileURLToPath } from "url";
import { dirname, join } from "path";

const DIR = dirname(fileURLToPath(import.meta.url));
const PYTHON_DIR = join(DIR, "..", "python");

try {
  execSync("python3 --version", { stdio: "ignore" });
} catch {
  console.error("Python 3 is required but not found.");
  console.error("Install: https://python.org");
  process.exit(1);
}

const args = process.argv.slice(2);
const cmd = `cd "${PYTHON_DIR}" && python3 -m stats ${args.map(a => `"${a}"`).join(" ")}`;

try {
  execSync(cmd, { stdio: "inherit", env: { ...process.env, PYTHONUNBUFFERED: "1" } });
} catch (e) {
  process.exit(e.status || 1);
}
