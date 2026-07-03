import { Layers } from "lucide-react";

interface CanvasMultiSelectEmptyProps {
  selectedPageCount?: number;
}

export function CanvasMultiSelectEmpty({ selectedPageCount }: CanvasMultiSelectEmptyProps) {
  return (
    <div className="canvas-multi-select-empty">
      <Layers size={48} className="multi-select-icon" />
      <div className="multi-select-count">{selectedPageCount} pages selected</div>
    </div>
  );
}
