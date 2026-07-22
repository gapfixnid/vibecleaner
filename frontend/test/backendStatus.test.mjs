import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const modulePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../src/lib/backendStatus.ts",
);
const source = fs.readFileSync(modulePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023 },
});
const sandbox = { exports: {}, module: { exports: {} }, Set };
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled.outputText, sandbox, { filename: modulePath });

const { mergeBackendStatus } = sandbox.module.exports;
const status = (generation, phase) => ({ generation, phase, retryable: false });

assert.equal(mergeBackendStatus(status(2, "running"), status(1, "failed")).phase, "running");
assert.equal(mergeBackendStatus(status(1, "running"), status(1, "restarting")).phase, "running");
assert.equal(mergeBackendStatus(status(1, "failed"), status(1, "restarting")).phase, "failed");
assert.equal(mergeBackendStatus(status(1, "running"), status(2, "restarting")).phase, "restarting");
assert.equal(mergeBackendStatus(status(1, "failed"), status(2, "starting")).phase, "starting");
assert.equal(mergeBackendStatus(status(2, "starting"), status(2, "running")).phase, "running");
