import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const modulePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../src/lib/textLayerUrl.ts",
);
const source = fs.readFileSync(modulePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2023 },
});
const sandbox = {
  exports: {},
  module: { exports: {} },
  window: {
    __TAURI_INTERNALS__: {
      convertFileSrc: (filePath, protocol) => `http://${protocol}.localhost/${encodeURIComponent(filePath)}`,
    },
  },
};
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled.outputText, sandbox, { filename: modulePath });
const { buildTextLayerUrl } = sandbox.module.exports;

const namespace = "0123456789abcdef0123456789abcdef";
const key = "0123456789abcdef01234567";
const url = buildTextLayerUrl(namespace, "page_1", 3, key);
assert.match(url, /^http:\/\/vibecleaner-image\.localhost\//);
assert.equal(
  decodeURIComponent(new URL(url).pathname.slice(1)),
  `/api/text-layers/${namespace}/page_1/3/${key}.png`,
);
assert.equal(buildTextLayerUrl(namespace, "page_1", 0, key), "");
assert.equal(buildTextLayerUrl("bad", "page_1", 1, key), "");
assert.equal(buildTextLayerUrl(namespace, "page_1", 1, "bad"), "");

