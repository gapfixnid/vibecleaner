import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const modulePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../src/lib/backendSessionReset.ts",
);
const source = fs.readFileSync(modulePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023 },
});
const sandbox = { exports: {}, module: { exports: {} } };
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled.outputText, sandbox, { filename: modulePath });

const { resetBackendSessionState } = sandbox.module.exports;
const state = {
  activeJob: { jobId: "job-generation-1" },
  bubbles: [{ id: 1 }],
  dirty: true,
  imageVersions: { 0: 3 },
  pages: [{ page_id: "stale-generation-1" }],
  projectPath: "stale.vibecleaner",
  selectedPageIds: [0],
  warned: false,
};

resetBackendSessionState({
  hasInMemoryWork: true,
  resetProcessing: () => { state.activeJob = null; },
  resetWorkspace: () => {
    state.pages = [];
    state.bubbles = [];
    state.selectedPageIds = [];
    state.imageVersions = {};
  },
  resetProject: () => { state.projectPath = null; },
  markClean: () => { state.dirty = false; },
  warnAboutSessionLoss: () => { state.warned = true; },
});

assert.deepEqual(state.pages, []);
assert.deepEqual(state.bubbles, []);
assert.deepEqual(state.selectedPageIds, []);
assert.deepEqual(state.imageVersions, {});
assert.equal(state.activeJob, null);
assert.equal(state.projectPath, null);
assert.equal(state.dirty, false);
assert.equal(state.warned, true);
