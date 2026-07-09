import { useEffect, useRef } from "react";
import { AlertTriangle, CheckCircle2, Info, X } from "lucide-react";
import type { ToastItem, ToastVariant } from "../hooks/useToasts";
import "./toast.css";

const VARIANT_ICONS: Record<ToastVariant, typeof Info> = {
  success: CheckCircle2,
  error: AlertTriangle,
  info: Info,
};

interface ToastCardProps {
  toast: ToastItem;
  onDismiss: (id: number) => void;
}

function ToastCard({ toast, onDismiss }: ToastCardProps) {
  const timerRef = useRef<number | null>(null);
  const remainingRef = useRef(toast.duration);
  const startedAtRef = useRef(0);

  // Auto-dismiss with pause-on-hover: the timer is stopped on pointer enter
  // and resumed with the remaining time on pointer leave.
  const stopTimer = () => {
    if (timerRef.current !== null) {
      window.clearTimeout(timerRef.current);
      timerRef.current = null;
      remainingRef.current -= Date.now() - startedAtRef.current;
    }
  };
  const startTimer = () => {
    if (timerRef.current !== null) return;
    startedAtRef.current = Date.now();
    timerRef.current = window.setTimeout(() => onDismiss(toast.id), Math.max(500, remainingRef.current));
  };

  useEffect(() => {
    startTimer();
    return stopTimer;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const Icon = VARIANT_ICONS[toast.variant];

  return (
    <div
      className={`toast-card toast-${toast.variant}`}
      onPointerEnter={stopTimer}
      onPointerLeave={startTimer}
    >
      <span className="toast-icon">
        <Icon size={16} />
      </span>
      <div className="toast-body">
        <div className="toast-title">{toast.title}</div>
        {toast.message && <div className="toast-message">{toast.message}</div>}
      </div>
      {toast.actionLabel && toast.onAction && (
        <button
          type="button"
          className="toast-action"
          onClick={() => {
            toast.onAction?.();
            onDismiss(toast.id);
          }}
        >
          {toast.actionLabel}
        </button>
      )}
      <button type="button" className="toast-close" onClick={() => onDismiss(toast.id)} aria-label="Dismiss">
        <X size={13} />
      </button>
    </div>
  );
}

interface ToastStackProps {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
}

export function ToastStack({ toasts, onDismiss }: ToastStackProps) {
  if (toasts.length === 0) return null;
  return (
    <div className="toast-stack" aria-live="polite">
      {toasts.map((toast) => (
        <ToastCard key={toast.id} toast={toast} onDismiss={onDismiss} />
      ))}
    </div>
  );
}
