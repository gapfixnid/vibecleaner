import threading

from backend.core.providers.concurrency import ProviderConcurrencyGate, ProviderQueueFullError


def test_provider_gate_rejects_when_active_and_queue_are_full():
    gate = ProviderConcurrencyGate(max_concurrency=1, queue_capacity=0)
    errors = []

    def contender():
        try:
            with gate.slot():
                pass
        except Exception as exc:
            errors.append(exc)

    with gate.slot():
        thread = threading.Thread(target=contender)
        thread.start()
        thread.join(timeout=1)
        assert gate.status()["active"] == 1

    assert len(errors) == 1
    assert isinstance(errors[0], ProviderQueueFullError)
    assert gate.status() == {"active": 0, "waiting": 0, "rejected": 1}


def test_provider_gate_releases_slot_after_failure():
    gate = ProviderConcurrencyGate(max_concurrency=1, queue_capacity=1)
    try:
        with gate.slot():
            raise RuntimeError("provider failed")
    except RuntimeError:
        pass
    with gate.slot():
        assert gate.status()["active"] == 1
