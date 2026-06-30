import type { PageInfo } from "../types";

export type PageStatusKind =
  | "none"
  | "orange"
  | "orange-blink"
  | "green";

export interface PageStatus {
  hasBubbles: boolean;
  translated: boolean;
  kind: PageStatusKind;
  blink: boolean;
  imageVersion: number;
}

type PageTask = "translate";

export function derivePageStatus(
  page: PageInfo,
  imageVersion: number,
  processing?: PageTask | null,
): PageStatus {
  const bubbleCount = Math.max(0, page.bubble_count ?? 0);
  const translatedCount = Math.min(
    Math.max(0, page.translated_count ?? 0),
    bubbleCount,
  );

  const hasBubbles = bubbleCount > 0;
  const translated = hasBubbles && translatedCount >= bubbleCount;

  let kind: PageStatusKind = "none";
  let blink = false;

  if (processing) {
    // Any processing → orange blink
    kind = "orange-blink";
    blink = true;
  } else if (translated) {
    // Translation complete → green solid
    kind = "green";
  } else if (hasBubbles) {
    // Bubbles detected, not translated → orange solid
    kind = "orange";
  }

  return {
    hasBubbles,
    translated,
    kind,
    blink,
    imageVersion,
  };
}

export function pageStatusLabel(kind: PageStatusKind): string | null {
  switch (kind) {
    case "green":
      return "Translated";
    case "orange-blink":
      return "Processing...";
    case "orange":
      return "Bubbles detected";
    case "none":
      return null;
  }
}
