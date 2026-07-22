import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const source = fs.readFileSync(
  path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../src/hooks/useProcessingTask.ts"),
  "utf8",
);

assert.match(source, /pollingGenerationRef\.current \+ 1/);
assert.match(source, /pollingGeneration !== pollingGenerationRef\.current/);
assert.match(source, /pollingGeneration === pollingGenerationRef\.current/);
assert.match(source, /taskEpochRef\.current \+= 1/);
assert.match(source, /taskEpoch === taskEpochRef\.current/);
assert.match(source, /if \(taskEpoch !== taskEpochRef\.current\) return undefined/);
