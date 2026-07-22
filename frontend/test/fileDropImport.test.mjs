import assert from "node:assert/strict";
import test from "node:test";

import { splitImagePaths } from "../src/hooks/useFileDropImport.ts";

test("dropped images use natural ascending filename order regardless of drag anchor", () => {
  const result = splitImagePaths([
    "C:\\manga\\page10.png",
    "C:\\manga\\page2.png",
    "C:\\manga\\page1.png",
  ]);

  assert.deepEqual(result.images, [
    "C:\\manga\\page1.png",
    "C:\\manga\\page2.png",
    "C:\\manga\\page10.png",
  ]);
  assert.equal(result.skipped, 0);
});

test("drop sorting keeps filtering and uses the full path as a stable tie breaker", () => {
  const result = splitImagePaths([
    "D:\\second\\cover.JPG",
    "C:\\first\\cover.jpg",
    "C:\\first\\notes.txt",
  ]);

  assert.deepEqual(result.images, [
    "C:\\first\\cover.jpg",
    "D:\\second\\cover.JPG",
  ]);
  assert.equal(result.skipped, 1);
});
