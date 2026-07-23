"""Explicit offscreen Qt runtime and render-thread isolation.

``QGuiApplication`` and application-font registration belong to the process
main thread.  Every other Qt rendering object is created, used, and destroyed
inside :class:`QtRenderExecutor`'s single worker.
"""

from __future__ import annotations

import atexit
import os
import queue
import secrets
import threading
from concurrent.futures import Future
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Generic, TypeVar

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFontDatabase, QGuiApplication, QImage


T = TypeVar("T")
QtRenderTask = Callable[["QtWorkerState"], T]


@dataclass
class QtWorkerState:
    """State that must never leave the Qt render worker."""

    metric_device: QImage = field(init=False)
    shaped_layout_cache: dict[str, object] = field(default_factory=dict)
    raw_font_cache: dict[str, object] = field(default_factory=dict)
    glyph_alpha_cache: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.metric_device = QImage(1, 1, QImage.Format.Format_ARGB32_Premultiplied)
        self.metric_device.setDevicePixelRatio(1.0)

    def clear(self) -> None:
        self.shaped_layout_cache.clear()
        self.raw_font_cache.clear()
        self.glyph_alpha_cache.clear()


class QtRenderExecutor:
    """Single worker that owns all render-time Qt objects."""

    def __init__(self) -> None:
        self._queue: queue.Queue[tuple[QtRenderTask[object] | None, Future[object] | None]] = queue.Queue()
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="vibecleaner-qt-render", daemon=True)
        self._thread.start()

    @property
    def thread_id(self) -> int | None:
        return self._thread.ident

    def is_worker_thread(self) -> bool:
        return threading.get_ident() == self._thread.ident

    def submit(self, task: QtRenderTask[T]) -> Future[T]:
        if self._closed:
            raise RuntimeError("Qt render executor is shut down")
        future: Future[T] = Future()
        self._queue.put((task, future))
        return future

    def run(self, task: QtRenderTask[T]) -> T:
        if self.is_worker_thread():
            raise RuntimeError("Nested synchronous Qt render task would deadlock")
        return self.submit(task).result()

    def shutdown(self, *, drain: bool = True) -> None:
        if self._closed:
            return
        self._closed = True
        if not drain:
            while True:
                try:
                    _task, future = self._queue.get_nowait()
                except queue.Empty:
                    break
                if future is not None:
                    future.cancel()
        self._queue.put((None, None))
        self._thread.join(timeout=30)
        if self._thread.is_alive():
            raise RuntimeError("Qt render executor did not stop")

    def _run(self) -> None:
        state = QtWorkerState()
        while True:
            task, future = self._queue.get()
            if task is None:
                break
            if future is None or not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(task(state))
            except BaseException as exc:  # propagate task failures to caller
                future.set_exception(exc)
        state.clear()


class QtRuntime:
    """Main-thread owner of the process-wide QGuiApplication."""

    _instance: "QtRuntime | None" = None
    _lock = threading.Lock()

    def __init__(self, app: QGuiApplication, font_ids: tuple[int, ...]) -> None:
        self.app = app
        self.font_ids = font_ids
        self.cache_namespace = secrets.token_hex(16)
        self.executor = QtRenderExecutor()
        self._shutdown = False

    @classmethod
    def initialize_on_main_thread(cls) -> "QtRuntime":
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("QtRuntime must be initialized on the process main thread")
        with cls._lock:
            if cls._instance is not None and not cls._instance._shutdown:
                return cls._instance
            app = QGuiApplication.instance()
            if app is None:
                app = QGuiApplication(["vibecleaner-backend", "-platform", "offscreen"])
            font_ids: list[int] = []
            assets = Path(__file__).resolve().parents[1] / "assets" / "fonts"
            for font_path in sorted(assets.glob("*.ttf")) + sorted(assets.glob("*.otf")):
                font_id = QFontDatabase.addApplicationFont(str(font_path))
                if font_id >= 0:
                    font_ids.append(font_id)
            cls._instance = cls(app, tuple(font_ids))
            return cls._instance

    @classmethod
    def instance(cls) -> "QtRuntime | None":
        return cls._instance

    def shutdown_on_main_thread(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("QtRuntime must be shut down on the process main thread")
        if self._shutdown:
            return
        self.executor.shutdown(drain=True)
        for font_id in self.font_ids:
            QFontDatabase.removeApplicationFont(font_id)
        self.app.quit()
        self._shutdown = True


def get_qt_runtime() -> QtRuntime:
    runtime = QtRuntime.instance()
    if runtime is None or runtime._shutdown:
        runtime = QtRuntime.initialize_on_main_thread()
    return runtime


def _shutdown_at_exit() -> None:
    runtime = QtRuntime.instance()
    if runtime is not None and not runtime._shutdown and threading.current_thread() is threading.main_thread():
        runtime.shutdown_on_main_thread()


atexit.register(_shutdown_at_exit)
