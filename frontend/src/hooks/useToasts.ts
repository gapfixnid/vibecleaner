import { useCallback, useRef, useState } from "react";

export type ToastVariant = "success" | "error" | "info";

export interface ToastItem {
  id: number;
  variant: ToastVariant;
  title: string;
  message?: string;
  /** Optional inline action (e.g. Undo). */
  actionLabel?: string;
  onAction?: () => void;
  /** Auto-dismiss delay in ms. */
  duration: number;
}

export interface ShowToastOptions {
  message?: string;
  actionLabel?: string;
  onAction?: () => void;
  duration?: number;
}

export type ShowToast = (variant: ToastVariant, title: string, options?: ShowToastOptions) => void;

const DEFAULT_DURATION_MS = 4000;
const ACTION_DURATION_MS = 6000;
const MAX_TOASTS = 3;

/**
 * Lightweight transient notifications for non-blocking feedback
 * (saved, exported, cancelled). Blocking feedback (errors, confirms)
 * stays on CustomDialog.
 */
export function useToasts() {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const nextIdRef = useRef(1);

  const dismissToast = useCallback((id: number) => {
    setToasts((current) => current.filter((toast) => toast.id !== id));
  }, []);

  const showToast: ShowToast = useCallback((variant, title, options) => {
    const id = nextIdRef.current++;
    const toast: ToastItem = {
      id,
      variant,
      title,
      message: options?.message,
      actionLabel: options?.actionLabel,
      onAction: options?.onAction,
      duration: options?.duration ?? (options?.actionLabel ? ACTION_DURATION_MS : DEFAULT_DURATION_MS),
    };
    setToasts((current) => [...current, toast].slice(-MAX_TOASTS));
  }, []);

  return { toasts, showToast, dismissToast } as const;
}
