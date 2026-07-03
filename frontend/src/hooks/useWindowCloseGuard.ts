import { useEffect, useRef } from "react";
import * as desktop from "../services/desktop";

export function useWindowCloseGuard(isDirty: boolean, guardUnsaved: (proceed: () => void) => void) {
  const isDirtyRef = useRef(false);
  const closingRef = useRef(false);
  const guardUnsavedRef = useRef(guardUnsaved);

  useEffect(() => {
    isDirtyRef.current = isDirty;
  }, [isDirty]);

  useEffect(() => {
    guardUnsavedRef.current = guardUnsaved;
  }, [guardUnsaved]);

  useEffect(() => {
    let unlisten: () => void = () => {};
    let active = true;
    desktop
      .onWindowCloseRequested((event) => {
        console.log("[close-guard] close requested. dirty=", isDirtyRef.current, "closing=", closingRef.current);
        if (closingRef.current || !isDirtyRef.current) {
          return;
        }
        event.preventDefault();
        try {
          guardUnsavedRef.current(() => {
            closingRef.current = true;
            desktop.destroyWindow();
          });
        } catch (e) {
          console.error("[close-guard] prompt failed; forcing close", e);
          closingRef.current = true;
          desktop.destroyWindow();
        }
      })
      .then((fn) => {
        if (active) unlisten = fn;
        else fn();
      });
    return () => {
      active = false;
      unlisten();
    };
  }, []);
}
