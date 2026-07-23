import React, { useEffect, useMemo, useRef, useState } from "react";
import type { BubbleInfo, TextLayerRefDto } from "../../types";
import { buildTextLayerUrl } from "../../lib/textLayerUrl";

interface Props {
  bubbles: BubbleInfo[];
  selectedBubbleId: number | null;
  width: number;
  height: number;
}

interface DisplayedTile {
  ref: TextLayerRefDto;
  url: string;
}

function BubbleSvgText({ bubble, hidden = false }: { bubble: BubbleInfo; hidden?: boolean }) {
  return (
    <g opacity={hidden ? 0 : 1} data-bubble-text={bubble.id}>
      {bubble.lines.map((line, lineIndex) => {
        const runs = line.runs?.length ? line.runs : [{
          text: line.text,
          origin_x: line.origin_x ?? line.x,
          font_family: bubble.computed_font_family || bubble.font_family,
          font_pixel_size: bubble.computed_font_size,
          is_rtl: bubble.text_direction === "rtl",
        }];
        return (
          <text
            key={`${bubble.id}-${lineIndex}`}
            x={line.origin_x ?? line.x}
            y={line.baseline_y ?? (line.y + line.height * 0.8)}
            textAnchor="start"
            fontWeight={bubble.bold ? 700 : 400}
            fontStyle={bubble.italic ? "italic" : "normal"}
            fill={bubble.color}
            stroke={bubble.stroke_color}
            strokeWidth={bubble.stroke_width}
            strokeLinejoin="round"
            paintOrder="stroke fill"
            direction={bubble.text_direction === "rtl" ? "rtl" : "ltr"}
          >
            {runs.map((run, runIndex) => (
              <tspan
                key={runIndex}
                x={run.origin_x}
                fontFamily={run.font_family || bubble.computed_font_family || bubble.font_family}
                fontSize={run.font_pixel_size || bubble.computed_font_size}
                direction={run.is_rtl ? "rtl" : "ltr"}
              >
                {run.text}
              </tspan>
            ))}
          </text>
        );
      })}
    </g>
  );
}

export const CanvasBubbleTextLayers = React.memo(({ bubbles, selectedBubbleId, width, height }: Props) => {
  const [displayed, setDisplayed] = useState<Record<number, DisplayedTile>>({});
  const displayedRef = useRef<Record<number, DisplayedTile>>({});
  const [failedKeys, setFailedKeys] = useState<Set<string>>(new Set());
  const [overlayReadyKey, setOverlayReadyKey] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const liveIds = new Set(bubbles.map((bubble) => bubble.id));
    const pruned = Object.fromEntries(
      Object.entries(displayedRef.current).filter(([id]) => liveIds.has(Number(id))),
    );
    if (Object.keys(pruned).length !== Object.keys(displayedRef.current).length) {
      displayedRef.current = pruned;
      setDisplayed(pruned);
    }
    for (const bubble of bubbles) {
      const ref = bubble.text_layer;
      if (!ref || bubble.render_status.status !== "ready") continue;
      const resolvedUrl = buildTextLayerUrl(
        bubble.text_layer_namespace,
        bubble.page_id,
        bubble.id,
        ref.cache_key,
      );
      if (!resolvedUrl || displayedRef.current[bubble.id]?.ref.cache_key === ref.cache_key) continue;
      const image = new Image();
      image.decoding = "async";
      image.onload = () => {
        void image.decode().catch(() => undefined).finally(() => {
          if (cancelled) return;
          setDisplayed((current) => {
            const next = { ...current, [bubble.id]: { ref, url: resolvedUrl } };
            displayedRef.current = next;
            return next;
          });
        });
      };
      image.onerror = () => {
        if (!cancelled) setFailedKeys((current) => new Set(current).add(`${bubble.id}:${ref.cache_key}`));
      };
      image.src = resolvedUrl;
    }
    return () => { cancelled = true; };
  }, [bubbles]);

  const selected = useMemo(
    () => bubbles.find((bubble) => bubble.id === selectedBubbleId) ?? null,
    [bubbles, selectedBubbleId],
  );
  const selectedFontKey = useMemo(() => {
    if (!selected) return null;
    const fonts = selected.lines.flatMap((line) => line.runs?.map((run) => (
      `${run.font_pixel_size}:${run.font_family}`
    )) ?? []);
    if (fonts.length === 0) {
      fonts.push(`${selected.computed_font_size}:${selected.computed_font_family || selected.font_family}`);
    }
    return `${selected.id}:${fonts.join("|")}`;
  }, [selected]);

  useEffect(() => {
    let cancelled = false;
    if (!selected || !selectedFontKey) return;
    const fonts = new Set<string>();
    selected.lines.forEach((line) => line.runs?.forEach((run) => {
      if (run.font_family) fonts.add(`${run.font_pixel_size}px "${run.font_family}"`);
    }));
    const timeout = new Promise<void>((resolve) => window.setTimeout(resolve, 500));
    const ready = Promise.all(Array.from(fonts, (font) => document.fonts.load(font))).then(() => undefined);
    void Promise.race([ready, timeout]).then(() => requestAnimationFrame(() => {
      if (!cancelled) setOverlayReadyKey(selectedFontKey);
    }));
    return () => { cancelled = true; };
  }, [selected, selectedFontKey]);

  return (
    <svg
      className="canvas-text-layer"
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      style={{ position: "absolute", inset: 0, pointerEvents: "none", overflow: "hidden" }}
    >
      {bubbles.map((bubble) => {
        if (!bubble.translated) return null;
        const tile = displayed[bubble.id];
        const isSelected = bubble.id === selectedBubbleId;
        const failed = bubble.text_layer
          ? failedKeys.has(`${bubble.id}:${bubble.text_layer.cache_key}`)
          : true;
        const showDom = failed || bubble.render_status.status === "fallback" || !tile || isSelected;
        const domReady = !isSelected || overlayReadyKey === selectedFontKey;
        return (
          <g key={bubble.id}>
            {tile && (
              <image
                href={tile.url}
                x={tile.ref.crop_x}
                y={tile.ref.crop_y}
                width={tile.ref.width}
                height={tile.ref.height}
                opacity={showDom && domReady ? 0 : 1}
              />
            )}
            {showDom && <BubbleSvgText bubble={bubble} hidden={isSelected && !domReady} />}
          </g>
        );
      })}
    </svg>
  );
});

CanvasBubbleTextLayers.displayName = "CanvasBubbleTextLayers";
