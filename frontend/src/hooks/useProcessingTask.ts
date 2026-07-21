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
   * keepBusyOnSuccess logic. Use for lightweight ops (import, save, open
   * project) that shouldn't look like heavy processing.
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

/** Live info about the job currently being polled — drives the StatusBar
 *  progress readout and the Translate→Cancel button morph. */
export interface ActiveJobInfo {
  jobId: string;
  kind: string | null;
  /** Caller-supplied label (always shown; backend message may refine it). */
  label: string;
  /** Latest backend `job.message`, unless the caller opted out. */
  message: string | null;
  /** 0-100, or null for indeterminate. */
  progress: number | null;
}

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
 *   guard, and cancellation support. Publishes `activeJob` (label/message/
 *   progress) for the StatusBar while polling.
 * - `cancelCurrentJob`: requests cancellation of the job being polled.
 */
export function useProcessingTask(
  showError: ShowError,
  t: (key: string) => string = (key) => key,
  /** Called once when a user-requested cancellation completes (e.g. show a toast). */
  notifyCancelled?: () => void
) {
  const [isProcessing, setIsProcessing] = useState(false);
  const [isWaitingForImageReload, setIsWaitingForImageReload] = useState(false);
  const [activeJob, setActiveJob] = useState<ActiveJobInfo | null>(null);

  const isMountedRef = useRef(true);
  const currentJobIdRef = useRef<string | null>(null);
  const cancelRequestedRef = useRef(false);
  /** Exposed so callers can branch after runTask returns. Reset after each runTask. */
  const wasCancelledRef = useRef(false);
  const notifyCancelledRef = useRef(notifyCancelled);

  useEffect(() => {
    notifyCancelledRef.current = notifyCancelled;
  }, [notifyCancelled]);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
    };
  }, []);

  const cancelCurrentJob = useCallback(() => {
    cancelRequestedRef.current = true;
    const jobId = currentJobIdRef.current;
    if (jobId) {
      // Best effort: the poll loop exits via cancelRequestedRef regardless.
      api.cancelJob(jobId).catch(() => {});
    }
  }, []);

  const waitForJob = useCallback(
    async (startedJob: JobStatus, fallbackStatus: string, options?: WaitForJobOptions): Promise<unknown> => {
      if (!startedJob?.job_id) {
        return startedJob;
      }
      currentJobIdRef.current = startedJob.job_id;
      cancelRequestedRef.current = false;
      const publish = (job: JobStatus) => {
        if (!isMountedRef.current) return;
        setActiveJob({
          jobId: job.job_id,
          kind: job.kind || null,
          label: fallbackStatus,
          message: options?.ignoreBackendMessage ? null : job.message || null,
          progress: typeof job.progress === "number" ? job.progress : null,
        });
      };
      publish(startedJob);
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
          if (job.status === "succeeded" || job.status === "succeeded_with_errors") {
            return job.result;
          }
          if (job.status === "failed") {
            const errorMsg = job.error || `${job.kind || "Job"} failed`;
            // Backend cancellation exceptions surface as failed+"cancelled" error.
            // Treat them as user cancellation so the i18n message is shown.
            if (errorMsg.toLowerCase().includes("cancelled")) {
              throw new Error(CANCELLED);
            }
            throw new Error(errorMsg);
          }
          if (job.status === "cancelled") {
            throw new Error(CANCELLED);
          }
          if (Date.now() > deadline) {
            throw new Error(`${job.kind || "Job"} timed out`);
          }
          await new Promise((resolve) => setTimeout(resolve, POLL_INTERVAL_MS));
          job = await api.getJob(job.job_id);
          publish(job);
          options?.onProgress?.(job);
        }
      } finally {
        currentJobIdRef.current = null;
        if (isMountedRef.current) {
          setActiveJob(null);
        }
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
          // Only notify for explicit user cancellations, not unmount aborts.
          if (cancelRequestedRef.current && isMountedRef.current) {
            notifyCancelledRef.current?.();
          }
          return undefined;
        }
        showError(options?.errorTitle || t("task.failed"), err?.response?.data?.detail || err?.message || String(e));
        if (busy) setIsProcessing(false);
        return undefined;
      }
    },
    [showError, t]
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
    activeJob,
    cancelCurrentJob,
    waitForJob,
    runTask,
    finishImageReload,
    wasCancelled: wasCancelledRef,
  } as const;
}
