"""
Utility functions for Quick Asset Saver operators.
"""

import re
from pathlib import Path

import bpy

DEBUG_MODE = False

MIN_BLEND_FILE_SIZE = 100
MAX_INCREMENTAL_FILES = 9999

LARGE_SELECTION_WARNING_THRESHOLD = 25
VERY_LARGE_BUNDLE_WARNING_MB = 5000
DEFAULT_MAX_BUNDLE_SIZE_MB = 4096


def debug_print(*args, **kwargs):
    """Print debug messages only when DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        print(*args, **kwargs)


def refresh_asset_browser_deferred():
    """
    Deferred refresh callback for timer.
    Finds Asset Browser areas and forces refresh with proper context.
    Returns None to run only once.
    """
    try:
        for window in bpy.context.window_manager.windows:
            screen = window.screen
            for area in screen.areas:
                if area.type == 'FILE_BROWSER':
                    space = area.spaces.active
                    if hasattr(space, 'browse_mode') and space.browse_mode == 'ASSETS':
                        for region in area.regions:
                            if region.type == 'WINDOW':
                                with bpy.context.temp_override(
                                    window=window,
                                    screen=screen,
                                    area=area,
                                    region=region
                                ):
                                    if hasattr(bpy.ops.asset, "library_refresh"):
                                        bpy.ops.asset.library_refresh()
                                    elif hasattr(bpy.ops.asset, "refresh"):
                                        bpy.ops.asset.refresh()
                                break
                        area.tag_redraw()
    except Exception as e:
        if DEBUG_MODE:
            print(f"[QAS] Deferred refresh failed: {e}")
    return None


def refresh_asset_browser(context):
    """
    Force refresh the Asset Browser using a deferred timer.
    
    Uses bpy.app.timers to schedule refresh after operator completes,
    which ensures operator has fully finished before refresh runs.
    
    Args:
        context: Blender context (used for immediate redraw tagging)
    """
    if not bpy.app.timers.is_registered(refresh_asset_browser_deferred):
        bpy.app.timers.register(refresh_asset_browser_deferred, first_interval=0.1)
    
    try:
        for area in context.screen.areas:
            if area.type == 'FILE_BROWSER':
                area.tag_redraw()
    except Exception:
        pass


def sanitize_name(name, max_length=128):
    """
    Sanitize a filename to be cross-platform compatible.

    Removes or replaces characters that are invalid on Windows, macOS, or Linux.
    Prevents directory traversal attacks by removing path separators.

    Args:
        name (str): The original filename or path component
        max_length (int): Maximum length for the sanitized name (default: 128)

    Returns:
        str: Sanitized filename safe for all platforms
    """
    if not name or not isinstance(name, str):
        return "asset"

    name = name.replace("/", "_").replace("\\", "_")

    invalid_chars = r'[<>:"|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, "_", name)
    
    sanitized = sanitized.strip(". ")

    if not sanitized:
        sanitized = "asset"

    return sanitized[:max_length]


def build_asset_filename(base_name, prefs):
    """
    Build the final asset filename with optional prefix, suffix, and date.

    Applies user-configured naming conventions from addon preferences to
    construct a complete filename. All components are sanitized individually
    to ensure cross-platform compatibility.

    Args:
        base_name (str): The sanitized base name of the asset
        prefs: Addon preferences containing naming convention settings

    Returns:
        str: Final filename without extension
    """
    from datetime import datetime

    filename_parts = []

    if prefs.filename_prefix:
        prefix = sanitize_name(prefs.filename_prefix, max_length=32).strip("_")
        if prefix:
            filename_parts.append(prefix)

    filename_parts.append(base_name)

    if prefs.filename_suffix:
        suffix = sanitize_name(prefs.filename_suffix, max_length=32).strip("_")
        if suffix:
            filename_parts.append(suffix)

    if prefs.include_date_in_filename:
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename_parts.append(date_str)

    final_name = "_".join(filename_parts)

    return sanitize_name(final_name, max_length=200)


def increment_filename(base_path, name, extension=".blend"):
    """
    Generate an incremented filename if the base file exists.

    Creates files with numeric suffixes (e.g., name_001, name_002) to avoid
    overwriting existing files. Uses zero-padded 3-digit counters.

    Args:
        base_path (Path or str): Directory path where file will be saved
        name (str): Base filename without extension
        extension (str): File extension including dot (default: ".blend")

    Returns:
        Path: Full path with incremented filename if needed

    Raises:
        RuntimeError: If more than MAX_INCREMENTAL_FILES versions exist
        ValueError: If inputs are invalid (empty name, non-directory path)
    """
    if not name or not isinstance(name, str):
        raise ValueError("Name must be a non-empty string")

    base_path = Path(base_path)
    if not base_path.is_dir():
        raise ValueError(f"Base path is not a directory: {base_path}")

    filepath = base_path / f"{name}{extension}"

    if not filepath.exists():
        return filepath

    counter = 1
    while counter <= MAX_INCREMENTAL_FILES:
        new_name = f"{name}_{counter:03d}{extension}"
        filepath = base_path / new_name
        if not filepath.exists():
            return filepath
        counter += 1

    raise RuntimeError(
        f"Too many incremental files for '{name}' (exceeded {MAX_INCREMENTAL_FILES}). "
        "Please clean up old versions or use a different name."
    )
