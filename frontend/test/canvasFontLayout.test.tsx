import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";

import { CanvasBubbleTextLayers } from "../src/components/canvas/CanvasBubbleTextLayers";
import type { BubbleInfo } from "../src/types";

test("canvas renders glyphs with the layout-computed font size", () => {
  const bubble: BubbleInfo = {
    id: 1,
    page_id: "page_1",
    text_layer_namespace: "0".repeat(32),
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
    line_height_ratio: 1.12,
    layout_area_usage: 0.67,
    writing_mode: "horizontal",
    text_direction: "ltr",
    justification: "none",
    layout_padding: {},
    layout_margin: {},
    layout_confidence: 1,
    layout_reasoning: "",
    lines: [{ text: "translated", x: 4, y: 8, width: 92, height: 20 }],
    text_layer: null,
    render_status: { status: "fallback", error_code: null },
    stroke_color: "#ffffff",
    stroke_width: 1.5,
  };

  const markup = renderToStaticMarkup(
    <CanvasBubbleTextLayers bubbles={[bubble]} selectedBubbleId={null} width={100} height={80} />,
  );

  assert.match(markup, /font-size="18"/);
  assert.doesNotMatch(markup, /font-size="28"/);
});
