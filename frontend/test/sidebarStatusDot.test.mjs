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
  false,
  "Sidebar thumbnails should not render status dots",
);
assert.equal(
  sidebarSource.includes("derivePageStatus"),
  false,
  "Sidebar should not derive thumbnail status after dot removal",
);
assert.equal(
  sidebarSource.includes("pageStatusLabel"),
  false,
  "Sidebar should not create thumbnail status labels after dot removal",
);
