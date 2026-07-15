import pytest

from backend.pipeline.resources import ResourceBudget, ResourceClass, ResourceManager


def test_resource_budget_exposes_named_limits():
    budget = ResourceBudget(cpu=2, gpu=3, io=4, network=5)
    assert [budget.limit(resource) for resource in ResourceClass] == [2, 3, 4, 5]


def test_resource_budget_rejects_zero_or_negative_values():
    with pytest.raises(ValueError, match="positive"):
        ResourceBudget(cpu=0).limit(ResourceClass.CPU)


def test_resource_manager_releases_lease_after_exception():
    manager = ResourceManager(ResourceBudget(cpu=1))
    with pytest.raises(RuntimeError):
        with manager.acquire(ResourceClass.CPU):
            raise RuntimeError("stage failure")
    with manager.acquire(ResourceClass.CPU):
        pass
