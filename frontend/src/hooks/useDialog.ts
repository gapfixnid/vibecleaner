import { useState, useCallback } from "react";
import type { DialogOptions } from "../components/CustomDialog";

export type AlertType = "info" | "success" | "warning" | "error";

const CLOSED_DIALOG: DialogOptions = {
  isOpen: false,
  type: "info",
  title: "",
  message: "",
  onConfirm: () => {},
};

/** Centralizes the app's alert/confirm dialog state. */
export function useDialog() {
  const [dialog, setDialog] = useState<DialogOptions>(CLOSED_DIALOG);

  const showAlert = useCallback((type: AlertType, title: string, message: string) => {
    setDialog({ isOpen: true, type, title, message, onConfirm: () => {} });
  }, []);

  const showConfirm = useCallback(
    (
      title: string,
      message: string,
      onConfirm: () => void,
      confirmText?: string,
      cancelText?: string,
      destructive?: boolean
    ) => {
      setDialog({ isOpen: true, type: "confirm", title, message, onConfirm, confirmText, cancelText, destructive });
    },
    []
  );

  /** Three-button unsaved-changes prompt: Save / Don't Save / Cancel.
   *  - onSave    → confirm button (primary)
   *  - onDiscard → deny button ("Don't Save")
   *  - Cancel    → dismiss, no callback
   */
  const showUnsavedPrompt = useCallback(
    (title: string, message: string, onSave: () => void, onDiscard: () => void) => {
      setDialog({
        isOpen: true,
        type: "confirm",
        title,
        message,
        onConfirm: onSave,
        onDeny: onDiscard,
        confirmText: "Save",
        denyText: "Don't Save",
        cancelText: "Cancel",
      });
    },
    []
  );

  const closeDialog = useCallback(() => {
    setDialog((d) => ({ ...d, isOpen: false }));
  }, []);

  return { dialog, showAlert, showConfirm, showUnsavedPrompt, closeDialog };
}
