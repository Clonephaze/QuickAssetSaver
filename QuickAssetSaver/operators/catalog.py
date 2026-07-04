"""
Catalog parsing and management functions for Quick Asset Saver.
"""

import uuid
from pathlib import Path

import bpy

from .utils import debug_print

_CATALOG_ENUM_CACHE = []


def get_catalog_path_from_uuid(library_path, catalog_uuid):
    """
    Get the catalog path string from a catalog UUID.

    Args:
        library_path (str): Path to the asset library folder
        catalog_uuid (str): UUID of the catalog

    Returns:
        str: Catalog path (e.g., "Materials/Metal") or None if not found
    """
    if not catalog_uuid or catalog_uuid == "UNASSIGNED":
        return None

    try:
        uuid.UUID(catalog_uuid)
    except (ValueError, AttributeError, TypeError):
        print(f"Invalid UUID format: {catalog_uuid}")
        return None

    catalogs, _ = get_catalogs_from_cdf(library_path)

    for path, uuid_str in catalogs.items():
        if uuid_str == catalog_uuid:
            return path

    return None


def get_catalogs_from_cdf(library_path):
    """
    Parse the blender_assets.cats.txt Catalog Definition File (CDF).

    Args:
        library_path (str): Path to the asset library folder

    Returns:
        dict: Mapping of catalog paths to UUIDs, e.g., {"Materials/Metal": "uuid-string"}
        list: List of tuples for EnumProperty items: (identifier, name, description)
        
    Note:
        Items are cached in _CATALOG_ENUM_CACHE to prevent garbage collection
        before Blender can display them (known Blender API issue).
    """
    global _CATALOG_ENUM_CACHE
    
    library_path = Path(library_path)
    cdf_path = library_path / "blender_assets.cats.txt"

    catalogs = {}
    enum_items = [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

    if not cdf_path.exists():
        debug_print(f"No catalog file found at {cdf_path}")
        _CATALOG_ENUM_CACHE = enum_items
        return catalogs, _CATALOG_ENUM_CACHE

    try:
        with open(cdf_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        idx = 1
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("VERSION"):
                continue

            parts = line.split(":")
            if len(parts) >= 2:
                catalog_uuid = parts[0].strip()
                catalog_path = parts[1].strip()

                if not catalog_path:
                    print(f"Line {line_num}: Empty catalog path, skipping")
                    continue

                try:
                    uuid.UUID(catalog_uuid)
                    catalogs[catalog_path] = catalog_uuid
                    
                    # Ensure catalog path (which may contain Unicode characters) is properly handled
                    # This supports Chinese, Japanese, Korean and other non-ASCII catalog names
                    display_name = str(catalog_path)
                    
                    debug_print(f"[QAM Catalog Debug] Adding catalog {idx}: uuid={catalog_uuid}, name={display_name}")
                    
                    enum_items.append(
                        (
                            catalog_uuid,
                            display_name,
                            f"Catalog: {display_name}",
                            "ASSET_MANAGER",
                            idx,
                        )
                    )
                    idx += 1
                except ValueError:
                    print(f"Line {line_num}: Invalid UUID format: {catalog_uuid}")
                    continue
            else:
                print(
                    f"Line {line_num}: Malformed catalog entry (expected at least 2 colon-separated fields)"
                )

    except (OSError, IOError) as e:
        print(f"Error reading catalog file {cdf_path}: {e}")
    except UnicodeDecodeError as e:
        print(f"Encoding error reading catalog file {cdf_path}: {e}")

    _CATALOG_ENUM_CACHE = enum_items
    debug_print(f"[QAM Catalog Debug] Cached {len(_CATALOG_ENUM_CACHE)} catalog items")
    
    return catalogs, _CATALOG_ENUM_CACHE


def clear_and_set_tags(asset_data, tags_string):
    """
    Clear existing tags and set new ones from a comma-separated string.

    Replaces all existing tags on an asset with a new set parsed from
    the input string. Empty or whitespace-only tags are ignored.

    Args:
        asset_data: Blender asset_data object with tags collection
        tags_string (str): Comma-separated string of tags (e.g., "metal, shiny, PBR")

    Note:
        This is a helper to avoid duplicating tag management logic.
        Tags collection doesn't have a clear() method, so we remove in reverse
        to avoid index shifting issues during iteration.
        
    Example:
        >>> clear_and_set_tags(material.asset_data, "metal, shiny, chrome")
        # Results in three tags: "metal", "shiny", "chrome"
    """
    if not hasattr(asset_data, "tags"):
        return

    while len(asset_data.tags) > 0:
        asset_data.tags.remove(asset_data.tags[-1])

    if tags_string:
        tags_list = [t.strip() for t in tags_string.split(",") if t.strip()]
        for tag in tags_list:
            asset_data.tags.new(tag)


def clear_catalog_cache():
    """Clear the catalog enum cache to force re-reading from disk."""
    global _CATALOG_ENUM_CACHE
    _CATALOG_ENUM_CACHE = []


def create_catalog_entry(library_path: str, catalog_path: str) -> str:
    """
    Add a new catalog entry to the library's CDF if the path doesn't exist.
    Preserves ALL existing CDF content. Safe to call if the entry already exists
    (returns the existing UUID in that case).

    Args:
        library_path: Path to the asset library folder containing blender_assets.cats.txt
        catalog_path: Catalog path string (e.g., "Materials/Metal")

    Returns:
        str: UUID for this catalog path (existing UUID if already present, new UUID if created)
    """
    import uuid as _uuid_mod

    lib_path = Path(library_path)
    cdf_path = lib_path / "blender_assets.cats.txt"

    # Check if it already exists — reuse existing UUID
    existing_catalogs, _ = get_catalogs_from_cdf(library_path)
    if catalog_path in existing_catalogs:
        return existing_catalogs[catalog_path]

    new_uuid = str(_uuid_mod.uuid4())
    display_name = catalog_path.split("/")[-1] if "/" in catalog_path else catalog_path

    # Create the CDF with a VERSION header if it doesn't exist yet
    if not cdf_path.exists():
        try:
            cdf_path.write_text("VERSION 1\n\n", encoding="utf-8")
        except (OSError, IOError) as e:
            print(f"[QAM] Could not create catalog file at {cdf_path}: {e}")
            return new_uuid

    # Append the new entry, preserving all existing content
    try:
        with open(cdf_path, "a", encoding="utf-8") as f:
            f.write(f"{new_uuid}:{catalog_path}:{display_name}\n")
    except (OSError, IOError) as e:
        print(f"[QAM] Could not write catalog entry to {cdf_path}: {e}")
        return new_uuid

    # Invalidate the enum cache so the next rebuild picks up the new entry
    clear_catalog_cache()

    if bpy.app.debug:
        print(f"[QAM] Created catalog entry: {catalog_path} ({new_uuid})")

    return new_uuid


class QAM_OT_refresh_catalog_list(bpy.types.Operator):
    """Refresh the catalog dropdown by re-reading the library's catalog file"""

    bl_idname = "qam.refresh_catalog_list"
    bl_label = ""
    bl_description = "Re-read the catalog file from disk to pick up any changes made outside this addon"
    bl_options = {"INTERNAL"}

    def execute(self, context):
        clear_catalog_cache()
        if context.area:
            context.area.tag_redraw()
        return {"FINISHED"}


classes = (QAM_OT_refresh_catalog_list,)
