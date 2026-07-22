import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const sidebarPath = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../src/components/Sidebar.tsx",
);
const sidebarSource = fs.readFileSync(sidebarPath, "utf8");

assert.equal(
  sidebarSource.includes("page-status-dot"),
  true,
  "Sidebar thumbnails should render the current page status",
);
assert.equal(
  sidebarSource.includes("aria-label={pageStateLabel}"),
  true,
  "Sidebar status must expose its label to assistive technology",
);
assert.equal(
  sidebarSource.includes("title={pageStateLabel}"),
  true,
  "Sidebar status must expose a tooltip label",
);
