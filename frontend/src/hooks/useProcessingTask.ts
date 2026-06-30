import { useState, useCallback, useRef, useEffect } from "react";
import * as api from "../services/api";
import type { JobStatus } from "../types";

export type ShowError = (title: string, message: string) => void;

export interface RunTaskOptions {
  /** Title used for the error dialog if the task throws. */
  errorTitle?: string;
  /**
   * Keep `isProcessing` active after a successful run. Used by
   * tasks that must stay "busy" until a follow-up event (e.g. the canvas image
   * finishing reload). On failure the busy state is always cleared.
   */
  keepBusyOnSuccess?: boolean;
  /**
   * Skip toggling `isProcessing`. The task still gets error handling and
   * keepBusyOnSuccess logic, but the status bar won't show "Working...".
   * Use for lightweight ops (import, save, open project) that shouldn't
   * look like heavy processing.
   */
  skipBusy?: boolean;
}

export type RunTask = <T>(
  label: string,
  fn: () => Promise<T>,
  options?: RunTaskOptions
) => Promise<T | undefined>;

export interface WaitForJobOptions {
  /**
   * Ignore the backend's `job.message` during polling and display only the
   * caller-supplied `fallbackStatus`. Used for batch operations where the
   * backend reports absolute page counts that confuse the user.
   */
  ignoreBackendMessage?: boolean;
  /** Called after each poll tick with the latest job data. */
  onProgress?: (job: JobStatus) => void;
}

export type WaitForJob = (
  startedJob: JobStatus,
  fallbackStatus: string,
  options?: WaitForJobOptions,
) => Promise<unknown>;

/** Safety cap so a stuck/dead backend job can't poll forever. */
const MAX_WAIT_MS = 10 * 60 * 1000;
const POLL_INTERVAL_MS = 500;

/** Sentinel error for user-initiated cancellation (not a real failure). */
const CANCELLED = "__job_cancelled__";

/**
 * Owns the global processing state and provides:
 * - `runTask`: a wrapper that toggles busy state and surfaces failures through
 *   a single error dialog (fixes inconsistent error handling).
 * - `waitForJob`: polls a backend job to completion with a timeout, an unmount
 *   guard, and cancellation support.
 */
export function useProcessingTask(showError: ShowError) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [isWaitingForImageReload, setIsWaitingForImageReload] = useState(false);

  const isMountedRef = useRef(true);
  const currentJobIdRef = useRef<string | null>(null);
  const cancelRequestedRef = useRef(false);
  /** Exposed so callers can branch after runTask returns. Reset after each runTask. */
  const wasCancelledRef = useRef(false);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const waitForJob = useCallback(
    async (startedJob: JobStatus, _fallbackStatus: string, _options?: WaitForJobOptions): Promise<unknown> => {
      if (!startedJob?.job_id) {
        return startedJob;
      }
      currentJobIdRef.current = startedJob.job_id;
      cancelRequestedRef.current = false;
      const deadline = Date.now() + MAX_WAIT_MS;
      try {
        let job = startedJob;
        while (true) {
          if (!isMountedRef.current) {
            throw new Error(CANCELLED);
          }
          if (cancelRequestedRef.current) {
            throw new Error(CANCELLED);
          }
          if (job.status === "succeeded") {
            return job.result;
          }
          if (job.status === "failed") {
            throw new Error(job.error || `${job.kind || "Job"} failed`);
          }
          if (job.status === "cancelled") {
            throw new Error(CANCELLED);
          }
          if (Date.now() > deadline) {
            throw new Error(`${job.kind || "Job"} timed out`);
          }
          await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
          job = await api.getJob(job.job_id);
          _options?.onProgress?.(job);
        }
      } finally {
        currentJobIdRef.current = null;
      }
    },
    []
  );

  const runTask = useCallback(
    async <T,>(_label: string, fn: () => Promise<T>, options?: RunTaskOptions): Promise<T | undefined> => {
      const busy = !options?.skipBusy;
      wasCancelledRef.current = false;
      if (busy) setIsProcessing(true);
      try {
        const result = await fn();
        if (busy && !options?.keepBusyOnSuccess) {
          setIsProcessing(false);
        }
        return result;
      } catch (e) {
        const err = e as { response?: { data?: { detail?: string } }; message?: string };
        // User-initiated cancellation is a normal stop, not an error.
        if (err?.message === CANCELLED) {
          wasCancelledRef.current = true;
          if (busy) setIsProcessing(false);
          return undefined;
        }
        showError(options?.errorTitle || "Task Failed", err?.response?.data?.detail || err?.message || String(e));
        if (busy) setIsProcessing(false);
        return undefined;
      }
    },
    [showError]
  );

  /** Called when the canvas finishes (re)loading an image after a busy task. */
  const finishImageReload = useCallback(() => {
    setIsWaitingForImageReload((waiting) => {
      if (waiting) {
        setIsProcessing(false);
      }
      return false;
    });
  }, []);

  return {
    isProcessing,
    setIsProcessing,
    isWaitingForImageReload,
    setIsWaitingForImageReload,
    waitForJob,
    runTask,
    finishImageReload,
    wasCancelled: wasCancelledRef,
  } as const;
}
