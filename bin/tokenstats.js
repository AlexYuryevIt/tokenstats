#!/usr/bin/env node

import { execSync } from "child_process";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { platform } from "os";

const DIR = dirname(fileURLToPath(import.meta.url));
const PYTHON_DIR = join(DIR, "..", "python");

const isWin = platform() === "win32";
const pythonCandidates = isWin ? ["python3", "python", "py -3"] : ["python3"];

let pythonCmd = null;
for (const cmd of pythonCandidates) {
  try {
    execSync(`${cmd} --version`, { stdio: "ignore" });
    pythonCmd = cmd;
    break;
  } catch {
    continue;
  }
}

if (!pythonCmd) {
  console.error("Python 3 is required but not found.");
  console.error("Install: https://python.org");
  process.exit(1);
}

const args = process.argv.slice(2);
const argsStr = args.map(a => `"${a}"`).join(" ");
const cmd = `cd "${PYTHON_DIR}" && ${pythonCmd} -m stats ${argsStr}`;

try {
  execSync(cmd, { stdio: "inherit", env: { ...process.env, PYTHONUNBUFFERED: "1" }, shell: isWin ? "cmd.exe" : true });
} catch (e) {
  process.exit(e.status || 1);
}
