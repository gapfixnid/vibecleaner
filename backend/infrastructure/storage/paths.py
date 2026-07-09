from __future__ import annotations

import os
import platform

from ...core.version import APP_NAME


def get_user_data_dir(app_name: str = APP_NAME) -> str:
    """
    Returns the platform-specific user data directory for the application.

    Windows: %LOCALAPPDATA%/<app_name>
    macOS: ~/Library/Application Support/<app_name>
    Linux: $XDG_DATA_HOME/<app_name> or ~/.local/share/<app_name>
    """
    system = platform.system()

    if system == "Windows":
        base_dir = os.getenv("LOCALAPPDATA")
        if not base_dir:
            base_dir = os.path.join(os.path.expanduser("~"), "AppData", "Local")
    elif system == "Darwin":
        base_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base_dir = os.getenv("XDG_DATA_HOME")
        if not base_dir:
            base_dir = os.path.join(os.path.expanduser("~"), ".local", "share")

    return os.path.join(base_dir, app_name)


def get_default_project_autosave_dir(folder_name: str = APP_NAME) -> str:
    """Return a user-facing default folder for project auto-save files."""
    return os.path.join(os.path.expanduser("~"), "Documents", folder_name)


def get_app_data_dir(app_name: str = APP_NAME) -> str:
    """
    Returns the OS-specific roaming application data directory.

    Windows: %APPDATA%/<app_name>
    macOS: ~/Library/Application Support/<app_name>
    Linux: ~/.config/<app_name>
    """
    if platform.system() == "Windows":
        base_dir = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base_dir, app_name)
    if platform.system() == "Darwin":
        return os.path.expanduser(f"~/Library/Application Support/{app_name}")
    return os.path.expanduser(f"~/.config/{app_name}")


def get_settings_file_path(app_name: str = APP_NAME) -> str:
    """Return the canonical settings.json path inside the roaming app-data dir."""
    return os.path.join(get_app_data_dir(app_name), "settings.json")