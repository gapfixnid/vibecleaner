from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_settings_route_does_not_import_global_config_or_service_registry():
    source = (ROOT / "backend" / "api" / "routes" / "settings.py").read_text(encoding="utf-8")

    assert "from modules.config import config" not in source
    assert "from services.service_registry import" not in source


def test_removed_singleton_modules_and_imports_stay_removed():
    backend = ROOT / "backend"

    assert not (backend / "services" / "service_registry.py").exists()

    scanned_files = [
        path
        for path in backend.rglob("*.py")
        if "__pycache__" not in path.parts
        and path.relative_to(backend).as_posix() != "core/container.py"
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in scanned_files)

    assert "services.auto_typeset_pipeline" not in combined
    assert "from domain.project_state import state" not in combined
    assert "state = ProjectState()" not in combined
    assert "from services.service_registry import" not in combined


def test_pipeline_and_api_do_not_import_concrete_engines():
    backend = ROOT / "backend"
    scanned_files = list((backend / "pipeline").rglob("*.py")) + list((backend / "api").rglob("*.py"))
    combined = "\n".join(path.read_text(encoding="utf-8") for path in scanned_files)

    assert "from engines" not in combined
    assert "import engines" not in combined
