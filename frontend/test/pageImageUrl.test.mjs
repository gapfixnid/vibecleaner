import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const modulePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../src/lib/pageImageUrl.ts",
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
  URLSearchParams,
};
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled.outputText, sandbox, { filename: modulePath });

const { buildPageImageUrl } = sandbox.module.exports;

const backendUrl = "http://127.0.0.1:8000";
const firstProjectPage = {
  page_id: "page_old",
  index: 0,
  has_inpaint: false,
};
const nextProjectPage = {
  page_id: "page_new",
  index: 0,
  has_inpaint: false,
};

const firstUrl = buildPageImageUrl({
  backendUrl,
  page: firstProjectPage,
  pageVersion: 0,
});
const nextUrl = buildPageImageUrl({
  backendUrl,
  page: nextProjectPage,
  pageVersion: 0,
});
const inpaintedUrl = buildPageImageUrl({
  backendUrl,
  page: { ...nextProjectPage, has_inpaint: true },
  pageVersion: 2,
  preview: false,
});

assert.notEqual(firstUrl, nextUrl, "new project pages with the same index must not share an image URL");
assert.match(nextUrl, /\/api\/pages\/page_new\/image/, "URL cache key must include the stable page id");
assert.match(nextUrl, /v=0/, "URL cache key must include the page image version");
assert.match(inpaintedUrl, /type=inpainted/, "inpainted pages should request the inpainted image");
assert.match(inpaintedUrl, /preview=false/, "full resolution requests should disable preview");
