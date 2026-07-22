import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const rust = fs.readFileSync(
  path.resolve(testDir, "../../desktop/src-tauri/src/lib.rs"),
  "utf8",
);

assert.doesNotMatch(rust, /forward_(?:get|post|empty_post|form)(?:_class)?\(&manager/);
assert.match(rust, /let session = manager\.session_snapshot\(\)\?;/);
assert.match(
  rust,
  /forward_get\(&session, "\/api\/pages"\).*forward_get\(&session, "\/api\/settings"\)/s,
);
assert.match(
  rust,
  /async fn get_job[\s\S]*?forward_get_class\([\s\S]*?RequestClass::JobPoll/,
);
assert.match(rust, /session\.ensure_current\(\)\?;\s*let result = session\.client/);
