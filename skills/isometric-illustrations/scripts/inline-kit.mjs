import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const kitPath = join(dirname(fileURLToPath(import.meta.url)), "..", "kit");
const sourceOf = (file) => readFileSync(join(kitPath, file), "utf8").replace(/^export /gm, "");

export function kitScript() {
  return sourceOf("iso-kit.mjs");
}

export function glScript() {
  return sourceOf("gl.mjs");
}
