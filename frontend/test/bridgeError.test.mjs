import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const modulePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../src/lib/bridgeError.ts",
);
const source = fs.readFileSync(modulePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023 },
});
const sandbox = { exports: {}, module: { exports: {} }, JSON };
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled.outputText, sandbox, { filename: modulePath });

const { normalizeBridgeError } = sandbox.module.exports;
const objectError = normalizeBridgeError({ code: "BACKEND_EXITED", message: "gone", retryable: true });
assert.equal(objectError.code, "BACKEND_EXITED");
assert.equal(objectError.message, "gone");
assert.equal(objectError.retryable, true);

const stringError = normalizeBridgeError('{"code":"BACKEND_START_FAILED","message":"nope","retryable":false}');
assert.equal(stringError.code, "BACKEND_START_FAILED");
assert.equal(stringError.message, "nope");
assert.equal(stringError.retryable, false);

const legacyError = normalizeBridgeError("legacy failure");
assert.equal(legacyError.code, "TAURI_ERROR");
assert.equal(legacyError.message, "legacy failure");
