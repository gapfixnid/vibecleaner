import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import vm from "node:vm";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const modulePath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../src/services/mappers.ts",
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

const { toBubbleInfo, toBubbleUpdateDto, toPagesResponse } = sandbox.module.exports;

const plain = (value) => JSON.parse(JSON.stringify(value));

const project = {
  current_page_id: "page_2",
  pages: [
    {
      id: "page_1",
      index: 0,
      file_path: "C:/manga/001.png",
      filename: "001.png",
      width: 800,
      height: 1200,
      status: "idle",
      bubbles: [],
      problems: [],
    },
    {
      id: "page_2",
      index: 1,
      file_path: "C:/manga/002.png",
      filename: "002.png",
      width: 900,
      height: 1300,
      status: "ready_for_review",
      bubbles: [],
      problems: ["layout overflow"],
      bubble_count: 3,
      translated_count: 2,
    },
  ],
};

assert.deepEqual(plain(toPagesResponse(project)), {
  current_index: 1,
  pages: [
    {
      page_id: "page_1",
      index: 0,
      file_path: "C:/manga/001.png",
      filename: "001.png",
      width: 800,
      height: 1200,
      bubble_count: 0,
      translated_count: 0,
      has_inpaint: false,
      status: "idle",
      problems: [],
    },
    {
      page_id: "page_2",
      index: 1,
      file_path: "C:/manga/002.png",
      filename: "002.png",
      width: 900,
      height: 1300,
      bubble_count: 3,
      translated_count: 2,
      has_inpaint: true,
      status: "ready_for_review",
      problems: ["layout overflow"],
    },
  ],
});

const bubbleDto = {
  id: "bubble_42",
  bubbleBox: { x: 10, y: 20, width: 100, height: 80 },
  textBox: { x: 12, y: 22, width: 90, height: 60 },
  layoutBox: { x: 12, y: 22, width: 90, height: 60 },
  text: "こんにちは",
  translated: "안녕",
  status: "needs_review",
  style: {
    font_family: "",
    computed_font_family: "Resolved Font",
    font_size: 18,
    font_mode: "fixed",
    requested_font_size: 18,
    computed_font_size: 16,
    bold: true,
    italic: false,
    color: "#111111",
    alignment: "center",
  },
  layout: {
    overflow: false,
    writing_mode: "vertical",
    text_direction: "rtl",
    justification: "full",
    padding: { top: 1, right: 2, bottom: 3, left: 4 },
    margin: { top: 5, right: 6, bottom: 7, left: 8 },
    confidence: 0.73,
    reasoning: "writing_mode=vertical; alignment=center",
    lines: [{ text: "안녕", x: 1, y: 2, width: 30, height: 12 }],
  },
  problems: ["check translation"],
  edited: true,
  text_class: "text_bubble",
};

assert.deepEqual(plain(toBubbleInfo(bubbleDto)), {
  id: 42,
  x: 10,
  y: 20,
  width: 100,
  height: 80,
  text: "こんにちは",
  translated: "안녕",
  font_family: "",
  computed_font_family: "Resolved Font",
  font_size: 18,
  font_mode: "fixed",
  requested_font_size: 18,
  computed_font_size: 16,
  bold: true,
  italic: false,
  color: "#111111",
  alignment: "center",
  text_class: "text_bubble",
  status: "needs_review",
  problems: ["check translation"],
  edited: true,
  layout_overflow: false,
  writing_mode: "vertical",
  text_direction: "rtl",
  justification: "full",
  layout_padding: { top: 1, right: 2, bottom: 3, left: 4 },
  layout_margin: { top: 5, right: 6, bottom: 7, left: 8 },
  layout_confidence: 0.73,
  layout_reasoning: "writing_mode=vertical; alignment=center",
  text_box: { x: 12, y: 22, width: 90, height: 60 },
  lines: [{ text: "안녕", x: 1, y: 2, width: 30, height: 12 }],
});

const updateDto = toBubbleUpdateDto({
  id: 42,
  x: 10,
  y: 20,
  width: 100,
  height: 80,
  text: "こんにちは",
  translated: "안녕",
  font_family: "Pretendard Variable",
  font_size: 18,
  font_mode: "fixed",
  requested_font_size: 18,
  computed_font_size: 16,
  bold: true,
  italic: false,
  color: "#111111",
  alignment: "center",
});

assert.deepEqual(plain(updateDto), {
  id: 42,
  x: 10,
  y: 20,
  width: 100,
  height: 80,
  text: "こんにちは",
  translated: "안녕",
  font_family: "Pretendard Variable",
  font_size: 18,
  bold: true,
  italic: false,
  color: "#111111",
  alignment: "center",
});
assert.equal(
  Object.hasOwn(updateDto, "computed_font_size"),
  false,
  "bubble update DTO should not include UI-only computed_font_size",
);

const autoUpdateDto = toBubbleUpdateDto({
  ...toBubbleInfo(bubbleDto),
  font_mode: "auto",
  requested_font_size: null,
  font_size: 0,
});
assert.equal(autoUpdateDto.font_size, 0, "automatic mode should persist the legacy zero sentinel");
