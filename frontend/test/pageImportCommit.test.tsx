import assert from "node:assert/strict";
import test from "node:test";
import React, { act, useRef } from "react";
import { createRoot, type Root } from "react-dom/client";
import { JSDOM } from "jsdom";

import { usePages } from "../src/hooks/usePages";
import { CanvasEmptyState } from "../src/components/canvas/CanvasEmptyState";
import type { PageInfo, PagesResponse } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const dom = new JSDOM("<!doctype html><html><body></body></html>");
Object.defineProperties(globalThis, {
  React: { value: React, configurable: true },
  window: { value: dom.window, configurable: true },
  document: { value: dom.window.document, configurable: true },
  navigator: { value: dom.window.navigator, configurable: true },
});

const page: PageInfo = {
  page_id: "new-page",
  index: 0,
  file_path: "C:/images/new.png",
  filename: "new.png",
  width: 100,
  height: 120,
  bubble_count: 0,
  translated_count: 0,
  has_inpaint: false,
  status: "idle",
  problems: [],
};

test("page snapshot is current before an imported page is activated", async () => {
  let hook!: ReturnType<typeof usePages>;
  const activatedPageIds: string[] = [];

  const Harness = () => {
    const currentIndexRef = useRef(-1);
    const pagesRef = useRef<PageInfo[]>([]);
    hook = usePages({
      currentIndexRef,
      pagesRef,
      runTask: async () => undefined,
      showError: () => {},
      showConfirm: () => {},
      onPageActivated: (index) => {
        activatedPageIds.push(pagesRef.current[index]?.page_id ?? "missing");
      },
      onPagesCleared: () => {},
      markDirty: () => {},
      markPagesDeleted: () => {},
    });
    return null;
  };

  const container = document.createElement("div");
  document.body.append(container);
  let root!: Root;
  await act(async () => {
    root = createRoot(container);
    root.render(<Harness />);
  });

  const response: PagesResponse = { pages: [page], current_index: 0 };
  await act(async () => {
    hook.commitPagesFromServer(response);
  });

  assert.deepEqual(activatedPageIds, ["new-page"]);
  assert.equal(hook.currentIndex, 0);
  assert.equal(hook.pages[0]?.page_id, "new-page");

  await act(async () => { root.unmount(); });
});

test("image import stays disabled until the backend bootstrap finishes", async () => {
  let imports = 0;
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);

  await act(async () => {
    root.render(
      <CanvasEmptyState
        onImportImages={() => { imports += 1; }}
        onOpenProject={() => {}}
        isBackendReady={false}
        t={(key) => key}
      />,
    );
  });

  const button = container.querySelector<HTMLButtonElement>(".canvas-empty-primary");
  assert.equal(button?.disabled, true);
  button?.click();
  assert.equal(imports, 0);

  await act(async () => { root.unmount(); });
});
