// frontend/src/components/NumberStepper.tsx
import React, { useEffect, useState, useCallback } from "react";
import { ChevronUp, ChevronDown } from "lucide-react";

interface NumberStepperProps {
  value: number;
  min: number;
  max: number;
  step?: number;
  /** Optional unit shown after the value (e.g. "s"). */
  unit?: string;
  /** Accessible name for the control (e.g. "Request timeout"). */
  label: string;
  /** Called with a clamped, committed value (on step, blur, or Enter). */
  onChange: (value: number) => void;
}

const clamp = (v: number, min: number, max: number) => Math.min(max, Math.max(min, v));

/**
 * Apple-style numeric stepper: a value field with always-visible up/down
 * buttons. Replaces the native (hover-only, off-theme) number spinner.
 * Typing is allowed and committed on blur/Enter; arrow keys also work.
 */
export const NumberStepper: React.FC<NumberStepperProps> = ({
  value,
  min,
  max,
  step = 1,
  unit,
  label,
  onChange,
}) => {
  const [draft, setDraft] = useState<string>(String(value));

  // Keep the visible draft in sync when the external value changes.
  useEffect(() => {
    setDraft(String(value));
  }, [value]);

  const commit = useCallback(() => {
    const parsed = parseInt(draft, 10);
    const next = clamp(Number.isNaN(parsed) ? value : parsed, min, max);
    setDraft(String(next));
    if (next !== value) onChange(next);
  }, [draft, value, min, max, onChange]);

  const stepBy = useCallback(
    (dir: 1 | -1) => {
      const next = clamp(value + dir * step, min, max);
      if (next !== value) onChange(next);
    },
    [value, step, min, max, onChange]
  );

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.currentTarget.blur();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      stepBy(1);
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      stepBy(-1);
    }
  };

  return (
    <div className="number-stepper">
      <input
        type="text"
        inputMode="numeric"
        className="number-stepper-input"
        value={draft}
        aria-label={label}
        onChange={(e) => setDraft(e.target.value.replace(/[^0-9]/g, ""))}
        onBlur={commit}
        onKeyDown={handleKeyDown}
      />
      {unit && <span className="number-stepper-unit">{unit}</span>}
      <div className="number-stepper-buttons">
        <button
          type="button"
          className="number-stepper-btn"
          aria-label={`Increase ${label}`}
          disabled={value >= max}
          onClick={() => stepBy(1)}
        >
          <ChevronUp size={12} />
        </button>
        <button
          type="button"
          className="number-stepper-btn"
          aria-label={`Decrease ${label}`}
          disabled={value <= min}
          onClick={() => stepBy(-1)}
        >
          <ChevronDown size={12} />
        </button>
      </div>
    </div>
  );
};
