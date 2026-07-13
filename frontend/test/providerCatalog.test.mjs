import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const testDir = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(testDir, "..");
const workspaceDir = path.resolve(frontendDir, "..");

const types = fs.readFileSync(path.join(frontendDir, "src/types/provider.ts"), "utf8");
const client = fs.readFileSync(path.join(frontendDir, "src/api/tauriClient.ts"), "utf8");
const rust = fs.readFileSync(path.join(workspaceDir, "desktop/src-tauri/src/lib.rs"), "utf8");

assert.match(types, /interface ProviderCatalogDto/);
assert.match(types, /config_schema: ProviderConfigFieldDto\[\]/);
assert.match(client, /callTauri<ProviderCatalogDto>\("get_provider_catalog"\)/);
assert.match(rust, /forward_get\(port_state\.0, "\/api\/providers\/catalog"\)/);
assert.match(rust, /get_provider_catalog,/);
