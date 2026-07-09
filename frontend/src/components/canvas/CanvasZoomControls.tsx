import { Maximize, Minus, Plus } from "lucide-react";
import "./zoomcontrols.css";

interface CanvasZoomControlsProps {
  scale: number;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onZoomReset: () => void;
  onZoomFit: () => void;
  t?: (key: string) => string;
}

export function CanvasZoomControls({
  scale,
  onZoomIn,
  onZoomOut,
  onZoomReset,
  onZoomFit,
  t = (key) => key,
}: CanvasZoomControlsProps) {
  return (
    <div className="canvas-zoom-controls">
      <button
        type="button"
        onClick={onZoomOut}
        data-tooltip={t("canvas.zoomOut")}
        data-tooltip-pos="top"
        aria-label={t("canvas.zoomOut")}
      >
        <Minus size={13} />
      </button>
      <button
        type="button"
        className="zoom-readout"
        onClick={onZoomReset}
        data-tooltip={t("canvas.zoomActual")}
        data-tooltip-pos="top"
        aria-label={t("canvas.zoomActual")}
      >
        {Math.round(scale * 100)}%
      </button>
      <button
        type="button"
        onClick={onZoomIn}
        data-tooltip={t("canvas.zoomIn")}
        data-tooltip-pos="top"
        aria-label={t("canvas.zoomIn")}
      >
        <Plus size={13} />
      </button>
      <div className="zoom-divider" />
      <button
        type="button"
        onClick={onZoomFit}
        data-tooltip={t("canvas.zoomFit")}
        data-tooltip-pos="top"
        aria-label={t("canvas.zoomFit")}
      >
        <Maximize size={12} />
      </button>
    </div>
  );
}
