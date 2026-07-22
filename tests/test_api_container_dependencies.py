from backend.main import create_app

TEST_TOKEN = "BwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwcHBwc"


def test_app_exposes_container_and_settings_route():
    app = create_app(TEST_TOKEN)

    assert hasattr(app.state, "container")
    route_paths = {route.path for route in app.routes if hasattr(route, "path")}
    for route in app.routes:
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            route_paths.update(child.path for child in original_router.routes if hasattr(child, "path"))
    assert "/api/settings" in route_paths
    assert "/api/providers/catalog" in route_paths
    assert "/api/providers/runtime" in route_paths
    assert hasattr(app.state.container, "provider_registry")
