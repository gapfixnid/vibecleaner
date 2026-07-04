import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const srcDir = path.resolve(testDir, "../src");
const modulePath = path.resolve(srcDir, "i18n.ts");
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
assert.equal(korean("dialog.cancel"), "취소");
assert.equal(korean("project.unsavedChanges"), "저장되지 않은 변경사항");
assert.equal(korean("export.successTitle"), "내보내기 완료");
assert.equal(korean("task.translationFailed"), "번역 실패");

const english = createTranslator("en");
assert.equal(english("toolbar.translate"), "Translate");
assert.equal(english("settings.uiLanguage"), "UI Language");
assert.equal(english("sidebar.pages"), "Pages");
assert.equal(english("inspector.noSelection"), "No Selection");
assert.equal(english("settings.recognitionRules"), "Recognition Rules");
assert.equal(english("dialog.cancel"), "Cancel");
assert.equal(english("export.successTitle"), "Export Successful");

const fallback = createTranslator("ko");
assert.equal(fallback("missing.key"), "missing.key");

function walkTsFiles(dir) {
  const entries = fs.readdirSync(dir, { withFileTypes: true });
  return entries.flatMap((entry) => {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory()) return walkTsFiles(fullPath);
    return /\.(ts|tsx)$/.test(entry.name) ? [fullPath] : [];
  });
}

const literalTranslationKeys = new Set();
for (const file of walkTsFiles(srcDir)) {
  const fileSource = fs.readFileSync(file, "utf8");
  for (const match of fileSource.matchAll(/\bt\("([^"]+)"\)/g)) {
    literalTranslationKeys.add(match[1]);
  }
}

for (const key of literalTranslationKeys) {
  assert.notEqual(
    english(key),
    key,
    `missing English translation for key ${key}`,
  );
  assert.notEqual(
    korean(key),
    key,
    `missing Korean translation for key ${key}`,
  );
}
