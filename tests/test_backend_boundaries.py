from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]


def test_settings_route_does_not_import_global_config_or_service_registry():
    source = (ROOT / "backend" / "api" / "routes" / "settings.py").read_text(encoding="utf-8")

    assert ("from modules.config import " + "config") not in source
    assert "from services.service_registry import" not in source


def test_removed_singleton_modules_and_imports_stay_removed():
    backend = ROOT / "backend"

    assert not (backend / "services" / "service_registry.py").exists()
    assert not (backend / "pipeline" / ("auto_" + "typeset.py")).exists()
    assert not (backend / "domain" / "project_state.py").exists()
    assert not (backend / "modules" / "logging_config.py").exists()
    assert not (backend / "modules" / "utils" / "download.py").exists()
    assert not (backend / "modules" / "utils" / "download_file.py").exists()
    assert not (backend / "imkit").exists()
    assert not (backend / "modules" / "utils" / "image_utils.py").exists()
    assert not (backend / "modules" / "utils" / "device.py").exists()
    assert not (backend / "modules" / "utils" / "onnx.py").exists()
    assert not (backend / "modules" / "utils" / "torch_autocast.py").exists()
    assert not (backend / "modules" / "utils" / "paths.py").exists()
    assert not (backend / "modules" / "inpainting").exists()
    assert not (backend / "modules" / "inpainting_wrapper.py").exists()
    assert not (backend / "modules" / "rendering").exists()
    assert not (backend / "modules" / "utils" / "inpainting.py").exists()
    assert not (backend / "services" / "inpainting_service.py").exists()
    assert not (backend / "services" / "font_resolver_service.py").exists()
    assert not (backend / "services" / "render_service.py").exists()
    assert not (backend / "services" / "layout_planner_service.py").exists()
    assert not (backend / "services" / "typesetting_service.py").exists()
    assert not (backend / "modules" / "rendering_wrapper.py").exists()
    assert not (backend / "modules" / "utils" / "textblock.py").exists()
    assert not (backend / "modules" / "utils" / "language_utils.py").exists()
    assert not (backend / "modules" / "detection").exists()
    assert not (backend / "services" / "detection_service.py").exists()
    assert not (backend / "modules" / "ocr").exists()
    assert not (backend / "modules" / "ocr_wrapper.py").exists()

    scanned_files = [
        path
        for path in backend.rglob("*.py")
        if "__pycache__" not in path.parts
    ]
    combined = "\n".join(path.read_text(encoding="utf-8") for path in scanned_files)

    assert ("services." + "auto_" + "typeset_pipeline") not in combined
    assert ("pipeline." + "auto_" + "typeset") not in combined
    assert ("auto_" + "typeset_pipeline") not in combined
    assert ("from domain." + "project_state import " + "state") not in combined
    assert ("from domain." + "project_state import " + "ProjectState") not in combined
    assert ("legacy" + "_state") not in combined
    assert "state = ProjectState()" not in combined
    assert ("from modules.config import " + "config") not in combined
    assert "config: AppConfig = AppConfig()" not in combined
    assert "load_settings = config.load" not in combined
    assert "save_settings = config.save" not in combined
    assert "apply_adaptive_binarization = config.apply_adaptive_binarization" not in combined
    assert "from services.service_registry import" not in combined
    assert ("modules." + "logging_config") not in combined
    assert ("modules.utils." + "download") not in combined
    assert ("import " + "imkit") not in combined
    assert ("from " + "imkit") not in combined
    assert ("modules.utils." + "image_utils") not in combined
    assert ("modules.utils." + "device") not in combined
    assert ("modules.utils." + "onnx") not in combined
    assert ("modules.utils." + "torch_autocast") not in combined
    assert ("modules.utils." + "paths") not in combined
    assert ("modules." + "inpainting") not in combined
    assert ("modules.utils." + "inpainting") not in combined
    assert ("services." + "inpainting_service") not in combined
    assert ("services." + "font_resolver_service") not in combined
    assert ("services." + "render_service") not in combined
    assert ("services." + "layout_planner_service") not in combined
    assert ("services." + "typesetting_service") not in combined
    assert ("modules." + "rendering_wrapper") not in combined
    assert ("modules.utils." + "textblock") not in combined
    assert ("modules.utils." + "language_utils") not in combined
    assert ("modules." + "detection") not in combined
    assert ("services." + "detection_service") not in combined
    assert ("modules." + "ocr") not in combined


def test_pipeline_and_api_do_not_import_concrete_engines():
    backend = ROOT / "backend"
    scanned_files = list((backend / "pipeline").rglob("*.py")) + list((backend / "api").rglob("*.py"))
    combined = "\n".join(path.read_text(encoding="utf-8") for path in scanned_files)

    assert "from engines" not in combined
    assert "import engines" not in combined


def test_pipeline_does_not_import_services():
    pipeline = ROOT / "backend" / "pipeline"
    offenders = []

    for path in pipeline.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("services"):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "services" or alias.name.startswith("services."):
                        offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert offenders == []


def test_pipeline_does_not_import_legacy_modules():
    pipeline = ROOT / "backend" / "pipeline"
    offenders = []

    for path in pipeline.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("modules"):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "modules" or alias.name.startswith("modules."):
                        offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert offenders == []


def test_infrastructure_does_not_import_legacy_or_upper_layers():
    infrastructure = ROOT / "backend" / "infrastructure"
    forbidden_roots = ("modules", "services", "api", "pipeline", "engines")
    offenders = []

    for path in infrastructure.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                root = node.module.split(".")[0]
                if root in forbidden_roots:
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in forbidden_roots:
                        offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert offenders == []


def test_services_do_not_define_module_level_service_singletons():
    services = ROOT / "backend" / "services"
    offenders = []

    for path in services.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            target_names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if "service" not in target_names:
                continue
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                if node.value.func.id.endswith("Service"):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert offenders == []


def test_pipeline_does_not_create_module_level_service_instances():
    pipeline = ROOT / "backend" / "pipeline"
    offenders = []

    for path in pipeline.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.Assign):
                continue
            if not isinstance(node.value, ast.Call) or not isinstance(node.value.func, ast.Name):
                continue
            if not node.value.func.id.endswith("Service"):
                continue
            target_names = [target.id for target in node.targets if isinstance(target, ast.Name)]
            if any(name.endswith("_service") for name in target_names):
                offenders.append(f"{path.relative_to(ROOT)}:{node.lineno}")

    assert offenders == []
