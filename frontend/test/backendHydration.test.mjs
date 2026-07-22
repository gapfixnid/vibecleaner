import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const bootstrap = fs.readFileSync(
  path.resolve(testDir, "../src/hooks/useBackendBootstrap.ts"),
  "utf8",
);
const pages = fs.readFileSync(
  path.resolve(testDir, "../src/hooks/usePages.ts"),
  "utf8",
);

const hydrationCommit = bootstrap.indexOf("handledRunningGenerationRef.current = generation");
const settingsHydration = bootstrap.indexOf("await loadSettingsFromServer()");
const pagesHydration = bootstrap.indexOf("await loadPagesFromServer(undefined, { throwOnError: true })");
assert.ok(settingsHydration >= 0 && pagesHydration > settingsHydration);
assert.ok(hydrationCommit > pagesHydration, "generation must be committed only after hydration succeeds");
assert.match(bootstrap, /statusRef\.current\?\.generation !== generation/);
assert.match(bootstrap, /hydratingGenerationRef\.current === merged\.generation/);
assert.match(pages, /if \(options\?\.throwOnError\) throw e/);
