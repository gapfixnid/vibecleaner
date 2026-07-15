from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from threading import BoundedSemaphore
from typing import Iterator


class ResourceClass(StrEnum):
    CPU = "cpu"
    GPU = "gpu"
    IO = "io"
    NETWORK = "network"


@dataclass(frozen=True)
class ResourceBudget:
    cpu: int = 1
    gpu: int = 1
    io: int = 4
    network: int = 4

    def limit(self, resource: ResourceClass) -> int:
        value = getattr(self, resource.value)
        if value < 1:
            raise ValueError(f"Resource budget for {resource.value} must be positive")
        return value


class ResourceManager:
    """Bounded resource admission for pipeline stages."""

    def __init__(self, budget: ResourceBudget | None = None) -> None:
        budget = budget or ResourceBudget()
        self._semaphores = {
            resource: BoundedSemaphore(budget.limit(resource))
            for resource in ResourceClass
        }

    def acquire(self, resource: ResourceClass) -> Iterator[None]:
        semaphore = self._semaphores[resource]

        class Lease:
            def __enter__(self_nonlocal) -> None:
                semaphore.acquire()

            def __exit__(self_nonlocal, exc_type, exc, tb) -> None:
                semaphore.release()

        return Lease()
