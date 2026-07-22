import assert from "node:assert/strict";
import test from "node:test";
import React, { act } from "react";
import { createRoot, type Root } from "react-dom/client";
import { JSDOM } from "jsdom";
import { useProcessingTask } from "../src/hooks/useProcessingTask";
import type { JobStatus } from "../src/types";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;
const dom = new JSDOM("<!doctype html><html><body></body></html>");
Object.defineProperties(globalThis, {
  window: { value: dom.window, configurable: true },
  document: { value: dom.window.document, configurable: true },
  navigator: { value: dom.window.navigator, configurable: true },
});

function mount(element: React.ReactNode): Root {
  const container = document.createElement("div");
  document.body.append(container);
  const root = createRoot(container);
  root.render(element);
  return root;
}

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<T>((resolvePromise, rejectPromise) => {
    resolve = resolvePromise;
    reject = rejectPromise;
  });
  return { promise, resolve, reject };
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));

test("an obsolete poll cannot clear the active job owned by a newer poll", async () => {
  const oldResponse = deferred<JobStatus>();
  const newResponse = deferred<JobStatus>();
  const runtime = {
    getJob: (jobId: string) => jobId === "old-job" ? oldResponse.promise : newResponse.promise,
    cancelJob: async () => ({ status: "cancelled" }),
    pollIntervalMs: 0,
  };
  let hook!: ReturnType<typeof useProcessingTask>;
  const Harness = () => {
    hook = useProcessingTask(() => {}, (key) => key, undefined, runtime);
    return null;
  };
  let root!: Root;
  await act(async () => { root = mount(<Harness />); });

  let oldWait!: Promise<unknown>;
  await act(async () => {
    oldWait = hook.waitForJob({ job_id: "old-job", status: "running" }, "old");
    await tick();
  });
  let newWait!: Promise<unknown>;
  await act(async () => {
    newWait = hook.waitForJob({ job_id: "new-job", status: "running" }, "new");
    await tick();
  });
  assert.equal(hook.activeJob?.jobId, "new-job");

  await act(async () => {
    oldResponse.resolve({ job_id: "old-job", status: "succeeded", result: "old" });
    await assert.rejects(oldWait, /__job_cancelled__/);
  });
  assert.equal(hook.activeJob?.jobId, "new-job");

  await act(async () => {
    newResponse.resolve({ job_id: "new-job", status: "succeeded", result: "new" });
    assert.equal(await newWait, "new");
  });
  assert.equal(hook.activeJob, null);
  await act(async () => { root.unmount(); });
});

test("an obsolete task rejection cannot clear a newer session's busy state", async () => {
  const oldTask = deferred<string>();
  const newTask = deferred<string>();
  const errors: string[] = [];
  const runtime = {
    getJob: async () => ({ job_id: "unused", status: "succeeded" as const }),
    cancelJob: async () => ({ status: "cancelled" }),
    pollIntervalMs: 0,
  };
  let hook!: ReturnType<typeof useProcessingTask>;
  const Harness = () => {
    hook = useProcessingTask((_title, message) => errors.push(message), (key) => key, undefined, runtime);
    return null;
  };
  let root!: Root;
  await act(async () => { root = mount(<Harness />); });

  let oldRun!: Promise<string | undefined>;
  await act(async () => {
    oldRun = hook.runTask("old", () => oldTask.promise);
  });
  await act(async () => {
    hook.resetForBackendRestart();
  });
  let newRun!: Promise<string | undefined>;
  await act(async () => {
    newRun = hook.runTask("new", () => newTask.promise);
  });
  assert.equal(hook.isProcessing, true);

  await act(async () => {
    oldTask.reject(new Error("old backend failed"));
    assert.equal(await oldRun, undefined);
  });
  assert.equal(hook.isProcessing, true);
  assert.deepEqual(errors, []);

  await act(async () => {
    newTask.resolve("done");
    assert.equal(await newRun, "done");
  });
  assert.equal(hook.isProcessing, false);
  await act(async () => { root.unmount(); });
});
