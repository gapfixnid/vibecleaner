#!/usr/bin/env node
/**
 * Single source of truth propagation.
 *
 * Edit app.meta.json (displayName + version), then run `npm run sync-version`.
 * This writes the values into every build manifest and regenerates the runtime
 * constant modules so nothing drifts out of sync.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = join(dirname(fileURLToPath(import.meta.url)), "..");
const read = (p) => readFileSync(join(ROOT, p), "utf8");
const write = (p, s) => {
  writeFileSync(join(ROOT, p), s);
  console.log("updated", p);
};

const meta = JSON.parse(read("app.meta.json"));
const { displayName, version } = meta;
if (!displayName || !version) {
  console.error("app.meta.json must define both displayName and version");
  process.exit(1);
}

// --- JSON manifests: only touch the fields we own ---
const setJsonField = (path, mutate) => {
  const data = JSON.parse(read(path));
  mutate(data);
  write(path, JSON.stringify(data, null, 2) + "\n");
};

setJsonField("package.json", (d) => {
  d.version = version;
});
setJsonField("frontend/package.json", (d) => {
  d.version = version;
});
setJsonField("desktop/src-tauri/tauri.conf.json", (d) => {
  d.version = version;
  d.productName = displayName;
  if (d.app?.windows?.[0]) d.app.windows[0].title = displayName;
});

// --- TOML manifests: replace the version line within the relevant section ---
const setTomlVersion = (path, sectionHeader) => {
  const src = read(path);
  const re = new RegExp(
    `(\\[${sectionHeader}\\][\\s\\S]*?\\nversion\\s*=\\s*")[^"]*(")`,
  );
  if (!re.test(src)) {
    console.error(`could not find version under [${sectionHeader}] in ${path}`);
    process.exit(1);
  }
  write(path, src.replace(re, `$1${version}$2`));
};

setTomlVersion("desktop/src-tauri/Cargo.toml", "package");
setTomlVersion("pyproject.toml", "project");

// --- Generated runtime constants (imported by app code) ---
write(
  "backend/core/version.py",
  `"""App name/version constants.

Generated from app.meta.json by scripts/sync-version.mjs.
Do not edit by hand — edit app.meta.json (the single source of truth) and run
\`npm run sync-version\`.
"""

APP_NAME = ${JSON.stringify(displayName)}
__version__ = ${JSON.stringify(version)}
`,
);

write(
  "frontend/src/appMeta.ts",
  `// App name/version constants.
//
// Generated from app.meta.json by scripts/sync-version.mjs.
// Do not edit by hand — edit app.meta.json (the single source of truth) and run
// \`npm run sync-version\`.

export const APP_NAME = ${JSON.stringify(displayName)};
export const APP_VERSION = ${JSON.stringify(version)};
`,
);

console.log(`\nSynced "${displayName}" v${version} across all targets.`);
