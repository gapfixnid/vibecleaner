import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const modulePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../src/hooks/useAutoTypeset.ts",
);
const source = fs.readFileSync(modulePath, "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: {
    module: ts.ModuleKind.CommonJS,
    target: ts.ScriptTarget.ES2023,
  },
});

const sandbox = {
  exports: {},
  module: { exports: {} },
  require: (specifier) => {
    if (specifier === "react") {
      return {
        useCallback: (fn) => fn,
        useEffect: () => undefined,
        useRef: (initial) => ({ current: initial }),
      };
    }
    if (specifier === "../services/api") {
      return {};
    }
    throw new Error(`Unexpected require: ${specifier}`);
  },
};
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled.outputText, sandbox, { filename: modulePath });

const {
  resolveAutoTypesetDisplayIndex,
  sortAutoTypesetPageIds,
} = sandbox.module.exports;

const plain = (value) => JSON.parse(JSON.stringify(value));

assert.deepEqual(
  plain(sortAutoTypesetPageIds([4, 1, 3])),
  [1, 3, 4],
  "batch translation should process selected pages in ascending page order",
);
assert.equal(
  resolveAutoTypesetDisplayIndex([1, 3, 4], 3),
  3,
  "batch translation should keep the active page visible when it was selected",
);
assert.equal(
  resolveAutoTypesetDisplayIndex([1, 3, 4], 2),
  1,
  "batch translation should show the first selected page when the active page was not selected",
);
assert.equal(
  resolveAutoTypesetDisplayIndex([], 2),
  null,
  "empty batch selections should not select a display page",
);
