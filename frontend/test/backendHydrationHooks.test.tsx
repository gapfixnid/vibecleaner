import assert from "node:assert/strict";
import test from "node:test";
import React, { act, type Dispatch, type SetStateAction } from "react";
import { createRoot, type Root } from "react-dom/client";
import { JSDOM } from "jsdom";
import { useBackendBootstrap } from "../src/hooks/useBackendBootstrap";
import type { PagesResponse, Settings } from "../src/types";
import type { BackendStatus } from "../src/types/backend";

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
  const promise = new Promise<T>((resolvePromise) => { resolve = resolvePromise; });
  return { promise, resolve };
}

const tick = () => new Promise((resolve) => setTimeout(resolve, 0));
const ignoreError = () => {};
async function waitUntil(predicate: () => boolean) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    if (predicate()) return;
    await act(async () => { await tick(); });
  }
  assert.fail("condition was not reached");
}

function captureSettings(target: Settings[]): Dispatch<SetStateAction<Settings>> {
  return (value) => {
    if (typeof value === "function") throw new Error("unexpected settings updater");
    target.push(value);
  };
}
const status = (generation: number, phase: BackendStatus["phase"]): BackendStatus => ({
  generation,
  phase,
  running: phase === "running",
  error: null,
  pid: phase === "running" ? 1000 + generation : null,
});

test("hydration does not commit settings or pages after its generation changes", async () => {
  const pages = deferred<PagesResponse>();
  const committedSettings: Settings[] = [];
  const committedPages: PagesResponse[] = [];
  const setSettings = captureSettings(committedSettings);
  const commitPagesFromServer = (value: PagesResponse) => { committedPages.push(value); };
  const onBackendGenerationChange = () => {};
  const fetchSettingsFromServer = async () => ({ source_language: "generation-1" } as Settings);
  const fetchPagesFromServer = () => pages.promise;
  let emitStatus!: (value: BackendStatus) => void;
  const backendTransport = {
    getBackendStatus: async () => status(1, "running"),
    retryBackend: async () => status(2, "running"),
    onBackendStatusChanged: async (handler: (value: BackendStatus) => void) => {
      emitStatus = handler;
      return () => {};
    },
  };
  const Harness = () => {
    useBackendBootstrap({
      setSettings,
      fetchSettingsFromServer,
      fetchPagesFromServer,
      commitPagesFromServer,
      onBackendGenerationChange,
      backendTransport,
      reportError: ignoreError,
    });
    return null;
  };
  let root!: Root;
  await act(async () => {
    root = mount(<Harness />);
    await tick();
  });
  await act(async () => {
    emitStatus(status(2, "starting"));
    pages.resolve({ pages: [], current_index: -1 });
    await tick();
  });

  assert.deepEqual(committedSettings, []);
  assert.deepEqual(committedPages, []);
  await act(async () => { root.unmount(); });
});

test("failed hydration can retry the same running generation", async () => {
  let settingsAttempts = 0;
  const committedSettings: Settings[] = [];
  const committedPages: PagesResponse[] = [];
  const setSettings = captureSettings(committedSettings);
  const commitPagesFromServer = (value: PagesResponse) => { committedPages.push(value); };
  const onBackendGenerationChange = () => {};
  let emitStatus!: (value: BackendStatus) => void;
  let hook!: ReturnType<typeof useBackendBootstrap>;
  const running = status(3, "running");
  const backendTransport = {
    getBackendStatus: async () => running,
    retryBackend: async () => running,
    onBackendStatusChanged: async (handler: (value: BackendStatus) => void) => {
      emitStatus = handler;
      return () => {};
    },
  };
  const fetchSettingsFromServer = async () => {
    settingsAttempts += 1;
    if (settingsAttempts === 1) throw new Error("temporary settings failure");
    return { source_language: "retry" } as Settings;
  };
  const fetchPagesFromServer = async () => ({ pages: [], current_index: -1 });
  const Harness = () => {
    hook = useBackendBootstrap({
      setSettings,
      fetchSettingsFromServer,
      fetchPagesFromServer,
      commitPagesFromServer,
      onBackendGenerationChange,
      backendTransport,
      reportError: ignoreError,
    });
    return null;
  };
  let root!: Root;
  await act(async () => {
    root = mount(<Harness />);
    await tick();
  });
  await waitUntil(() => hook.backendError?.code === "unreachable");
  assert.equal(hook.backendError?.code, "unreachable");
  assert.equal(settingsAttempts, 1);

  await act(async () => {
    emitStatus(running);
    await tick();
  });
  assert.equal(settingsAttempts, 2);
  assert.equal(committedSettings.length, 1);
  assert.equal(committedPages.length, 1);
  assert.equal(hook.backendError, null);
  assert.equal(hook.isBootstrapping, false);
  await act(async () => { root.unmount(); });
});
