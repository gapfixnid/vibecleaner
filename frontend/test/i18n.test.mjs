import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const modulePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../src/i18n.ts",
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
};
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled.outputText, sandbox, { filename: modulePath });

const { createTranslator, normalizeUiLanguage } = sandbox.module.exports;

assert.equal(normalizeUiLanguage("ko"), "ko");
assert.equal(normalizeUiLanguage("en"), "en");
assert.equal(normalizeUiLanguage("unsupported"), "en");
assert.equal(normalizeUiLanguage(undefined), "en");

const korean = createTranslator("ko");
assert.equal(korean("toolbar.translate"), "번역");
assert.equal(korean("settings.uiLanguage"), "UI 언어");
assert.equal(korean("sidebar.pages"), "페이지");
assert.equal(korean("sidebar.filterPages"), "페이지 필터...");
assert.equal(korean("inspector.typographyDesign"), "타이포그래피 및 디자인");
assert.equal(korean("inspector.noSelection"), "선택 없음");
assert.equal(korean("settings.recognitionRules"), "인식 규칙");
assert.equal(korean("settings.inpaintingOptions"), "인페인팅 옵션");

const english = createTranslator("en");
assert.equal(english("toolbar.translate"), "Translate");
assert.equal(english("settings.uiLanguage"), "UI Language");
assert.equal(english("sidebar.pages"), "Pages");
assert.equal(english("inspector.noSelection"), "No Selection");
assert.equal(english("settings.recognitionRules"), "Recognition Rules");

const fallback = createTranslator("ko");
assert.equal(fallback("missing.key"), "missing.key");
