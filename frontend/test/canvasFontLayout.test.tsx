import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CanvasBubbleTextOverlay } from "../src/components/canvas/CanvasBubbleTextOverlay";
import type { BubbleInfo } from "../src/types";

test("canvas renders glyphs with the layout-computed font size", () => {
  const bubble: BubbleInfo = {
    id: 1,
    x: 0,
    y: 0,
    width: 100,
    height: 80,
    text: "source",
    translated: "translated",
    font_family: "Arial",
    computed_font_family: "Arial",
    font_size: 28,
    font_mode: "fixed",
    requested_font_size: 28,
    computed_font_size: 18,
    bold: false,
    italic: false,
    color: "#000000",
    alignment: "center",
    text_class: "text_bubble",
    status: "ok",
    problems: [],
    edited: false,
    layout_overflow: false,
    writing_mode: "horizontal",
    text_direction: "ltr",
    justification: "none",
    layout_padding: {},
    layout_margin: {},
    layout_confidence: 1,
    layout_reasoning: "",
    lines: [{ text: "translated", x: 4, y: 8, width: 92, height: 20 }],
  };

  const markup = renderToStaticMarkup(
    <CanvasBubbleTextOverlay bubbles={[bubble]} selectedBubbleId={null} />,
  );

  assert.match(markup, /font-size:18px/);
  assert.doesNotMatch(markup, /font-size:28px/);
});
