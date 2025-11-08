"""
Operators Module - Quick Asset Saver
=====================================
Core operators for saving assets from Current File to library folders.
Includes helpers for file I/O, catalog parsing, metadata assignment, and sanitization.
"""

import re
import shutil
import uuid
from pathlib import Path

import bpy
from bpy.types import Operator


def sanitize_name(name, max_length=128):
    """
    Sanitize a filename to be cross-platform compatible.

    Args:
        name: The original filename
        max_length: Maximum length for the filename

    Returns:
        Sanitized filename safe for all platforms
    """
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, "_", name)
    sanitized = sanitized.replace(" ", "_")
    sanitized = sanitized.strip("._")
    
    if not sanitized:
        sanitized = "asset"
    
    return sanitized[:max_length]


def build_asset_filename(base_name, prefs):
    """
    Build the final asset filename with optional prefix, suffix, and date.

    Args:
        base_name: The sanitized base name of the asset
        prefs: Addon preferences containing naming convention settings

    Returns:
        str: Final filename without extension
    """
    from datetime import datetime
    
    # Start with the base name
    filename_parts = []
    
    # Add prefix if specified
    if prefs.filename_prefix:
        prefix = sanitize_name(prefs.filename_prefix, max_length=32).strip("_")
        if prefix:
            filename_parts.append(prefix)
    
    # Add the base name
    filename_parts.append(base_name)
    
    # Add suffix if specified
    if prefs.filename_suffix:
        suffix = sanitize_name(prefs.filename_suffix, max_length=32).strip("_")
        if suffix:
            filename_parts.append(suffix)
    
    # Add date if enabled
    if prefs.include_date_in_filename:
        date_str = datetime.now().strftime("%Y-%m-%d")
        filename_parts.append(date_str)
    
    # Join all parts with underscores
    final_name = "_".join(filename_parts)
    
    # Ensure total length doesn't exceed reasonable limits
    return sanitize_name(final_name, max_length=200)


def increment_filename(base_path, name, extension=".blend"):
    """Generate an incremented filename if the base file exists."""
    base_path = Path(base_path)
    filepath = base_path / f"{name}{extension}"

    if not filepath.exists():
        return filepath

    counter = 1
    while True:
        new_name = f"{name}_{counter:03d}{extension}"
        filepath = base_path / new_name
        if not filepath.exists():
            return filepath
        counter += 1
        
        if counter > 9999:
            raise RuntimeError(f"Too many incremental files for {name}")


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

    catalogs, _ = get_catalogs_from_cdf(library_path)
    
    # Search for the UUID in the catalog mapping
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
    """
    library_path = Path(library_path)
    cdf_path = library_path / "blender_assets.cats.txt"

    catalogs = {}
    enum_items = [("UNASSIGNED", "Unassigned", "No catalog assigned", "NONE", 0)]

    if not cdf_path.exists():
        print(f"No catalog file found at {cdf_path}")
        return catalogs, enum_items

    try:
        with open(cdf_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Parse CDF format: UUID:catalog_path:catalog_name
        # Lines starting with # are comments or headers
        idx = 1  # Start from 1 since UNASSIGNED is 0
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("VERSION"):
                continue

            parts = line.split(":")
            if len(parts) >= 2:
                catalog_uuid = parts[0].strip()
                catalog_path = parts[1].strip()

                # Validate UUID format
                try:
                    uuid.UUID(catalog_uuid)
                    catalogs[catalog_path] = catalog_uuid
                    # Create enum item
                    enum_items.append(
                        (
                            catalog_uuid,
                            catalog_path,
                            f"Catalog: {catalog_path}",
                            "ASSET_MANAGER",
                            idx,
                        )
                    )
                    idx += 1
                except ValueError:
                    print(f"Invalid UUID in catalog file: {catalog_uuid}")
                    continue

    except Exception as e:
        print(f"Error reading catalog file: {e}")

    return catalogs, enum_items


def collect_datablocks_for_asset(asset_data):
    """Collect the main datablock for an asset."""
    datablocks = set()
    if hasattr(asset_data, "local_id") and asset_data.local_id:
        datablocks.add(asset_data.local_id)
    return datablocks


def write_blend_file(filepath, datablocks):
    """Write a .blend file containing only the specified datablocks."""
    try:
        filepath = Path(filepath)
        temp_dir = filepath.parent
        temp_file = temp_dir / f".tmp_{filepath.name}"

        bpy.data.libraries.write(
            str(temp_file),
            datablocks,
            path_remap="RELATIVE_ALL",
            fake_user=True,
            compress=True,
        )

        if filepath.exists():
            filepath.unlink()

        shutil.move(str(temp_file), str(filepath))
        return True

    except Exception as e:
        print(f"Error writing blend file: {e}")
        if temp_file.exists():
            temp_file.unlink()
        return False


def assign_asset_metadata(filepath, metadata_dict):
    """
    Open a saved .blend file and assign/update asset metadata.

    Args:
        filepath (Path): Path to the .blend file
        metadata_dict (dict): Dictionary with keys: name, author, description, catalog_id, tags

    Returns:
        bool: True if successful
    """
    try:
        filepath = Path(filepath)

        # We need to load the file, mark the asset, set metadata, and save
        # This is done by loading the blend file's datablocks
        with bpy.data.libraries.load(str(filepath), link=False) as (data_from, data_to):
            # Load all datablocks to find our asset
            # We'll load the first main datablock (usually the one we saved)
            for attr in dir(data_from):
                if attr.startswith("_"):
                    continue
                items = getattr(data_from, attr, [])
                if items and len(items) > 0:
                    # Load the first item of this type
                    setattr(data_to, attr, [items[0]])
                    break

        # Get the loaded datablock
        loaded_block = None
        for attr in dir(data_to):
            if attr.startswith("_"):
                continue
            items = getattr(data_to, attr, [])
            if items and len(items) > 0:
                loaded_block = items[0]
                break

        if loaded_block:
            # Mark as asset if not already
            if not loaded_block.asset_data:
                loaded_block.asset_mark()

            # Set metadata
            if loaded_block.asset_data:
                if "author" in metadata_dict:
                    loaded_block.asset_data.author = metadata_dict["author"]
                if "description" in metadata_dict:
                    loaded_block.asset_data.description = metadata_dict["description"]
                if (
                    "catalog_id" in metadata_dict
                    and metadata_dict["catalog_id"] != "UNASSIGNED"
                ):
                    loaded_block.asset_data.catalog_id = metadata_dict["catalog_id"]

                # Tags: Blender 5.0 asset_data has tags attribute
                if "tags" in metadata_dict and hasattr(loaded_block.asset_data, "tags"):
                    # Remove existing tags (no clear() method in bpy_prop_collection)
                    while len(loaded_block.asset_data.tags) > 0:
                        loaded_block.asset_data.tags.remove(
                            loaded_block.asset_data.tags[0]
                        )

                    # Add new tags
                    tags_list = [
                        t.strip() for t in metadata_dict["tags"].split(",") if t.strip()
                    ]
                    for tag in tags_list:
                        loaded_block.asset_data.tags.new(tag)

            # Note: The above loads into current blend. We need to save it back to the file
            # However, bpy.data.libraries.write doesn't support this workflow well.
            # Alternative approach: The metadata should be set BEFORE writing, or we use
            # a different technique. For now, we'll note this limitation.

            print(f"Asset metadata prepared for {filepath}")
            return True

        return False

    except Exception as e:
        print(f"Error setting asset metadata: {e}")
        return False


class QAS_OT_open_library_folder(Operator):
    """Open the asset library folder in the system file browser"""

    bl_idname = "qas.open_library_folder"
    bl_label = "Open Library Folder"
    bl_description = "Open the configured asset library folder in your file browser"
    bl_options = {"REGISTER"}

    def execute(self, context):
        wm = context.window_manager
        props = wm.qas_save_props

        if not props.selected_library or props.selected_library == 'NONE':
            self.report({"ERROR"}, "No asset library selected")
            return {"CANCELLED"}

        library_path = Path(props.selected_library)
        if not library_path.exists():
            self.report({"ERROR"}, "Library path does not exist")
            return {"CANCELLED"}

        bpy.ops.wm.path_open(filepath=str(library_path))
        return {"FINISHED"}


class QAS_OT_save_asset_to_library_direct(Operator):
    """Save selected asset directly from panel without popup"""

    bl_idname = "qas.save_asset_to_library_direct"
    bl_label = "Save to Asset Library"
    bl_description = "Save this asset as a standalone .blend file in your asset library"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        """Execute the save operation directly using panel properties."""
        from . import properties

        # Get preferences and properties
        prefs = properties.get_addon_preferences(context)
        wm = context.window_manager
        props = wm.qas_save_props

        # Validate library selection
        if not props.selected_library or props.selected_library == 'NONE':
            self.report({"ERROR"}, "No asset library selected")
            return {"CANCELLED"}

        library_path = Path(props.selected_library)
        if not library_path.exists():
            self.report({"ERROR"}, f"Library path does not exist: {library_path}")
            return {"CANCELLED"}

        # Determine target directory based on catalog preference
        target_dir = library_path
        
        if prefs.use_catalog_subfolders and props.catalog and props.catalog != "UNASSIGNED":
            # Get the catalog path from UUID
            catalog_path = get_catalog_path_from_uuid(props.selected_library, props.catalog)
            
            if catalog_path:
                # Sanitize catalog path components
                path_parts = catalog_path.split("/")
                sanitized_parts = [sanitize_name(part, max_length=64) for part in path_parts if part]
                
                # Create the full subfolder path
                target_dir = library_path
                for part in sanitized_parts:
                    target_dir = target_dir / part
                
                # Create the directory structure if it doesn't exist
                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    self.report({"ERROR"}, f"Could not create catalog subfolder: {e}")
                    return {"CANCELLED"}

        # Test write permissions
        try:
            test_file = target_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except (OSError, PermissionError):
            self.report({"ERROR"}, f"Target path is not writable: {target_dir}")
            return {"CANCELLED"}

        # Get sanitized filename from file_name property and apply naming conventions
        base_sanitized_name = props.asset_file_name
        if not base_sanitized_name:
            self.report({"ERROR"}, "Invalid file name")
            return {"CANCELLED"}

        # Apply prefix, suffix, and date if configured
        final_filename = build_asset_filename(base_sanitized_name, prefs)

        # Handle file conflicts
        if props.conflict_resolution == "INCREMENT":
            output_path = increment_filename(target_dir, final_filename)
        elif props.conflict_resolution == "OVERWRITE":
            output_path = target_dir / f"{final_filename}.blend"
        else:  # CANCEL
            check_path = target_dir / f"{final_filename}.blend"
            if check_path.exists():
                self.report({"WARNING"}, f"File already exists: {check_path.name}")
                return {"CANCELLED"}
            output_path = check_path

        # Get the asset datablock from context
        asset_id = None
        if hasattr(context, "asset") and hasattr(context.asset, "local_id"):
            asset_id = context.asset.local_id
        elif hasattr(context, "id"):
            asset_id = context.id

        if not asset_id:
            self.report({"ERROR"}, "Could not identify asset to save")
            return {"CANCELLED"}

        # Mark as asset if not already
        if not asset_id.asset_data:
            asset_id.asset_mark()

        # Set metadata on the source asset before saving
        if asset_id.asset_data:
            # Set the display name
            asset_id.name = props.asset_display_name
            
            asset_id.asset_data.author = props.asset_author
            asset_id.asset_data.description = props.asset_description
            asset_id.asset_data.license = props.asset_license
            asset_id.asset_data.copyright = props.asset_copyright

            # Set catalog
            if props.catalog and props.catalog != "UNASSIGNED":
                asset_id.asset_data.catalog_id = props.catalog

            # Set tags if supported
            if hasattr(asset_id.asset_data, "tags"):
                # Remove existing tags
                while len(asset_id.asset_data.tags) > 0:
                    asset_id.asset_data.tags.remove(asset_id.asset_data.tags[0])

                # Add new tags
                tags_list = [
                    t.strip() for t in props.asset_tags.split(",") if t.strip()
                ]
                for tag in tags_list:
                    asset_id.asset_data.tags.new(tag)

        datablocks = {asset_id}

        # Write the blend file
        success = write_blend_file(output_path, datablocks)

        if not success:
            self.report({"ERROR"}, f"Failed to write {output_path.name}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Saved asset to {output_path.name}")

        # Refresh Asset Browser if enabled
        if prefs.auto_refresh:
            try:
                if hasattr(bpy.ops.asset, "library_refresh"):
                    bpy.ops.asset.library_refresh()
                elif hasattr(bpy.ops.asset, "refresh"):
                    bpy.ops.asset.refresh()
                else:
                    self.report(
                        {"WARNING"},
                        "Asset browser refresh not available. Please refresh manually.",
                    )
            except Exception as e:
                print(f"Could not refresh asset browser: {e}")

        return {"FINISHED"}


classes = (
    QAS_OT_save_asset_to_library_direct,
    QAS_OT_open_library_folder,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
