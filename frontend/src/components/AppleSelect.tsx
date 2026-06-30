import { useState, useRef, useEffect, useCallback, type ReactNode } from "react";
import { createPortal } from "react-dom";

interface AppleSelectOption {
  value: string;
  label: ReactNode;
}

interface AppleSelectProps {
  value: string;
  onChange: (value: string) => void;
  options: AppleSelectOption[];
  disabled?: boolean;
}

interface DropdownRect {
  top: number;
  left: number;
  width: number;
}

/**
 * Custom dropdown that replaces the native <select> to avoid the
 * "closes on scroll" bug when used inside a scrollable container.
 *
 * The dropdown is rendered via createPortal into document.body so
 * it never triggers scrollbars in the parent container.
 */
export function AppleSelect({ value, onChange, options, disabled = false }: AppleSelectProps) {
  const [open, setOpen] = useState(false);
  const [rect, setRect] = useState<DropdownRect | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const dropdownRef = useRef<HTMLUListElement>(null);

  const selectedOption = options.find((o) => o.value === value);
  const selectedLabel = selectedOption?.label ?? value;

  // Measure trigger button position when dropdown opens
  useEffect(() => {
    if (!open || !triggerRef.current) return;
    const bbox = triggerRef.current.getBoundingClientRect();
    setRect({
      top: bbox.bottom + window.scrollY + 2,
      left: bbox.left + window.scrollX,
      width: bbox.width,
    });
  }, [open]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        containerRef.current &&
        !containerRef.current.contains(target) &&
        !(dropdownRef.current && dropdownRef.current.contains(target))
      ) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open]);

  const handleSelect = useCallback(
    (optValue: string) => {
      onChange(optValue);
      setOpen(false);
    },
    [onChange],
  );

  // Keyboard navigation within the dropdown
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLButtonElement>) => {
      if (e.key === "ArrowDown" && !open) {
        e.preventDefault();
        setOpen(true);
      } else if (e.key === "ArrowDown" && open) {
        e.preventDefault();
        const idx = options.findIndex((o) => o.value === value);
        const next = options[(idx + 1) % options.length];
        if (next) handleSelect(next.value);
      } else if (e.key === "ArrowUp" && open) {
        e.preventDefault();
        const idx = options.findIndex((o) => o.value === value);
        const prev = options[(idx - 1 + options.length) % options.length];
        if (prev) handleSelect(prev.value);
      } else if (e.key === "Enter" && !open) {
        e.preventDefault();
        setOpen(true);
      } else if (e.key === " " && !open) {
        e.preventDefault();
        setOpen(true);
      }
    },
    [open, options, value, handleSelect],
  );

  const triggerStyle: React.CSSProperties = {
    width: "100%",
    maxWidth: 250,
    appearance: "none",
    WebkitAppearance: "none",
    backgroundColor: "var(--field-bg)",
    backgroundImage: `url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='%23999' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='6 9 12 15 18 9'/%3E%3C/svg%3E")`,
    backgroundRepeat: "no-repeat",
    backgroundPosition: "right 10px center",
    border: `1px solid ${open ? "var(--border-focus)" : "var(--border-color)"}`,
    borderRadius: "var(--radius-md)",
    color: "var(--text-primary)",
    padding: "var(--space-3) var(--space-10) var(--space-3) var(--space-4)",
    fontSize: "12.5px",
    fontFamily: "var(--font-family)",
    outline: "none",
    cursor: disabled ? "not-allowed" : "pointer",
    transition: "background-color 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease",
    textAlign: "left" as const,
    display: "flex",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 8,
  };

  const dropdownContent = (
    <ul
      ref={dropdownRef}
      style={{
        position: "absolute",
        top: rect?.top ?? 0,
        left: rect?.left ?? 0,
        width: rect?.width ?? 250,
        maxHeight: 220,
        overflowY: "auto",
        backgroundColor: "var(--bg-panel)",
        border: "1px solid var(--border-color)",
        borderRadius: "var(--radius-md)",
        boxShadow: "0 8px 30px rgba(0,0,0,0.12)",
        padding: "4px 0",
        margin: 0,
        listStyle: "none",
        zIndex: 9999,
      }}
    >
      {options.map((opt) => {
        const isActive = opt.value === value;
        return (
          <li
            key={opt.value}
            role="option"
            aria-selected={isActive}
            onClick={() => handleSelect(opt.value)}
            style={{
              padding: "6px 12px",
              fontSize: "12.5px",
              fontFamily: "var(--font-family)",
              color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
              backgroundColor: isActive ? "var(--bg-input-focus)" : "transparent",
              cursor: "pointer",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {opt.label}
          </li>
        );
      })}
    </ul>
  );

  return (
    <div ref={containerRef} style={{ position: "relative", display: "block", width: "100%", maxWidth: 250 }}>
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        onKeyDown={handleKeyDown}
        style={triggerStyle}
      >
        <span style={{ overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{selectedLabel}</span>
      </button>

      {open && rect && typeof document !== "undefined" && createPortal(dropdownContent, document.body)}
    </div>
  );
}
