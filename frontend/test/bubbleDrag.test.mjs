import assert from "node:assert/strict";
import test from "node:test";

import {
  bubbleGeometryChanged,
  canStartBubbleDrag,
} from "../src/lib/bubbleDrag.ts";

test("a bubble can move only after it is already selected", () => {
  assert.equal(canStartBubbleDrag(null, 1, "move"), false);
  assert.equal(canStartBubbleDrag(2, 1, "move"), false);
  assert.equal(canStartBubbleDrag(1, 1, "move"), true);
  assert.equal(canStartBubbleDrag(1, 1, "resize"), true);
});

test("returning to the original geometry does not persist a drag", () => {
  const initial = { x: 10, y: 20, width: 100, height: 60 };
  assert.equal(bubbleGeometryChanged({ ...initial, id: 1 }, initial), false);
  assert.equal(bubbleGeometryChanged({ ...initial, id: 1, x: 11 }, initial), true);
});
