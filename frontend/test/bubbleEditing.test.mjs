import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const modulePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../src/hooks/useBubbleEditing.ts",
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
        useState: (initial) => [initial, () => undefined],
      };
    }
    throw new Error(`Unexpected require: ${specifier}`);
  },
};
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled.outputText, sandbox, { filename: modulePath });

const {
  hasBubbleTextEdits,
  shouldUpdateBubbleField,
  applyBubbleFieldUpdate,
} = sandbox.module.exports;

const bubble = {
  id: 7,
  text: "original",
  translated: "translated",
  font_size: 18,
  computed_font_size: 16,
  color: "#000000",
};

assert.equal(
  hasBubbleTextEdits(bubble, "original", "translated"),
  false,
  "unchanged text drafts should not trigger a save",
);
assert.equal(
  hasBubbleTextEdits(bubble, "changed", "translated"),
  true,
  "changed original text should trigger a save",
);
assert.equal(
  hasBubbleTextEdits(bubble, "original", "changed"),
  true,
  "changed translated text should trigger a save",
);
assert.equal(
  shouldUpdateBubbleField(bubble, "font_size", 18),
  false,
  "unchanged style fields should not trigger an update",
);
assert.equal(
  shouldUpdateBubbleField(bubble, "font_size", 20),
  true,
  "changed style fields should trigger an update",
);

const automatic = applyBubbleFieldUpdate(bubble, "font_size", 0);
assert.equal(automatic.font_mode, "auto");
assert.equal(automatic.requested_font_size, null);

const fixed = applyBubbleFieldUpdate(automatic, "font_size", 24);
assert.equal(fixed.font_mode, "fixed");
assert.equal(fixed.requested_font_size, 24);
