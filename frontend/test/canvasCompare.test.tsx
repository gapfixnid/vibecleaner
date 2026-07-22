import assert from "node:assert/strict";
import test from "node:test";
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { JSDOM } from "jsdom";

import { CanvasImageStage } from "../src/components/canvas/CanvasImageStage";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const dom = new JSDOM("<!doctype html><html><body></body></html>");
Object.defineProperties(globalThis, {
  window: { value: dom.window, configurable: true },
  document: { value: dom.window.document, configurable: true },
  navigator: { value: dom.window.navigator, configurable: true },
});

test("compare keeps the rendered image visible until the original is decoded", async () => {
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  const imageRef = React.createRef<HTMLImageElement>();

  await act(async () => {
    root.render(
      <CanvasImageStage
        ref={React.createRef<HTMLDivElement>()}
        displayImageUrl="processed.jpg"
        originalImageUrl="original.jpg"
        showOriginal
        imageRef={imageRef}
        imageDimensions={{ w: 100, h: 120 }}
        pan={{ x: 0, y: 0 }}
        scale={1}
        isImageLoading={false}
        bubbles={[]}
        selectedBubbleId={null}
        onImageLoad={() => {}}
        onImageError={() => {}}
        onStartBubbleDrag={() => {}}
      />,
    );
  });

  const base = container.querySelector<HTMLImageElement>("img:not(.canvas-original-image)");
  const original = container.querySelector<HTMLImageElement>(".canvas-original-image");
  assert.equal(base?.getAttribute("src"), "processed.jpg");
  assert.equal(original?.classList.contains("visible"), false);

  await act(async () => {
    original?.dispatchEvent(new dom.window.Event("load"));
  });

  assert.equal(base?.getAttribute("src"), "processed.jpg");
  assert.equal(original?.classList.contains("visible"), true);

  await act(async () => { root.unmount(); });
});
