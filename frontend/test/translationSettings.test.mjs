import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const srcDir = path.resolve(testDir, "../src");
const modulePath = path.resolve(srcDir, "translationSettings.ts");
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

const {
  getTranslationProviderCapabilities,
  isLlmTranslationProvider,
  DEFAULT_TRANSLATION_OPTIONS,
} = sandbox.module.exports;

assert.equal(DEFAULT_TRANSLATION_OPTIONS.timeoutSeconds, 90);
assert.equal(DEFAULT_TRANSLATION_OPTIONS.temperature, 0.1);
assert.equal(DEFAULT_TRANSLATION_OPTIONS.topP, 0.95);
assert.equal(DEFAULT_TRANSLATION_OPTIONS.maxTokens, 4096);
assert.equal(DEFAULT_TRANSLATION_OPTIONS.maxRetries, 2);
assert.equal(DEFAULT_TRANSLATION_OPTIONS.retryBackoffSeconds, 2);

assert.equal(isLlmTranslationProvider("openai"), true);
assert.equal(isLlmTranslationProvider("claude"), true);
assert.equal(isLlmTranslationProvider("ollama"), true);
assert.equal(isLlmTranslationProvider("openai_compatible"), true);
assert.equal(isLlmTranslationProvider("google"), false);
assert.equal(isLlmTranslationProvider("deepl"), false);

assert.equal(JSON.stringify(getTranslationProviderCapabilities("google")), JSON.stringify({
  llmOptions: false,
  modelPicker: false,
  visionContext: false,
  systemPrompt: false,
}));
assert.equal(JSON.stringify(getTranslationProviderCapabilities("openai")), JSON.stringify({
  llmOptions: true,
  modelPicker: true,
  visionContext: true,
  systemPrompt: true,
}));
