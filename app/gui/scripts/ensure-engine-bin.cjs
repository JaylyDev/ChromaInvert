// Ensures the per-platform engine-bin staging dirs exist before packaging.
// `electron-builder` copies `engine-bin/${os}` via `extraResources`; creating
// the (possibly empty) dirs here keeps packaging green when no binary was
// staged yet. Run by every `dist*` npm script.
const { mkdirSync } = require("node:fs");
const { join } = require("node:path");

for (const platform of ["win", "mac", "linux"]) {
  mkdirSync(join(__dirname, "..", "engine-bin", platform), { recursive: true });
}
console.log("engine-bin dirs ready");
