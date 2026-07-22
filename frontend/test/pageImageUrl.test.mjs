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
  window: {
    __TAURI_INTERNALS__: {
      convertFileSrc: (path, protocol) =>
        `http://${protocol}.localhost/${encodeURIComponent(path)}`,
    },
  },
};
sandbox.exports = sandbox.module.exports;
vm.runInNewContext(compiled.outputText, sandbox, { filename: modulePath });

const { buildPageImageUrl } = sandbox.module.exports;

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
  page: firstProjectPage,
  pageVersion: 0,
});
const nextUrl = buildPageImageUrl({
  page: nextProjectPage,
  pageVersion: 0,
});
const inpaintedUrl = buildPageImageUrl({
  page: { ...nextProjectPage, has_inpaint: true },
  pageVersion: 2,
  preview: false,
});

assert.notEqual(firstUrl, nextUrl, "new project pages with the same index must not share an image URL");
assert.match(nextUrl, /^http:\/\/vibecleaner-image\.localhost\//, "images must use the custom protocol");
assert.doesNotMatch(nextUrl, /127\.0\.0\.1|localhost:\d+/, "images must not expose the backend port");
const decodedNextUrl = decodeURIComponent(new URL(nextUrl).pathname.slice(1));
const decodedInpaintedUrl = decodeURIComponent(new URL(inpaintedUrl).pathname.slice(1));
assert.match(decodedNextUrl, /\/api\/pages\/page_new\/image/, "URL cache key must include the stable page id");
assert.match(decodedNextUrl, /v=0/, "URL cache key must include the page image version");
assert.match(decodedInpaintedUrl, /type=inpainted/, "inpainted pages should request the inpainted image");
assert.match(decodedInpaintedUrl, /preview=false/, "full resolution requests should disable preview");
