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

from .properties import get_addon_preferences

# Debug mode - set to True for verbose logging
DEBUG_MODE = False

# File and size validation constants
MIN_BLEND_FILE_SIZE = 100  # Minimum size in bytes for a valid .blend file
MAX_INCREMENTAL_FILES = 9999  # Maximum number of incremental file versions (e.g., file_0001.blend)

# Asset bundling thresholds
LARGE_SELECTION_WARNING_THRESHOLD = 25  # Warn user when selecting more than this many assets
VERY_LARGE_BUNDLE_WARNING_MB = 5000  # Warn for bundles larger than this (in MB)
DEFAULT_MAX_BUNDLE_SIZE_MB = 4096  # Default maximum bundle size (4GB)

# Cache for catalog enum items to prevent garbage collection
# Blender's EnumProperty callbacks can have strings GC'd before display
_CATALOG_ENUM_CACHE = []


def debug_print(*args, **kwargs):
    """Print debug messages only when DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        print(*args, **kwargs)


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

    Note:
        - Removes path separators (/ and \\) to prevent directory traversal
        - Replaces invalid characters (<>:"|?*) with underscores
        - Replaces spaces with underscores for better compatibility
        - Strips leading/trailing dots and underscores
        - Returns "asset" as fallback for empty or invalid inputs
    """
    if not name or not isinstance(name, str):
        return "asset"

    # Remove any path separators to prevent directory traversal
    name = name.replace("/", "_").replace("\\", "_")

    # Remove invalid characters for cross-platform compatibility
    # Windows: < > : " | ? * and control characters (\x00-\x1f)
    invalid_chars = r'[<>:"|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, "_", name)
    sanitized = sanitized.replace(" ", "_")
    sanitized = sanitized.strip("._")

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
        str: Final filename without extension (e.g., "PREFIX_AssetName_SUFFIX_2025-12-24")
        
    Note:
        The returned filename is further sanitized to ensure total length
        doesn't exceed filesystem limits (200 characters).
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
        
    Examples:
        >>> increment_filename(Path("/assets"), "MyAsset", ".blend")
        Path("/assets/MyAsset.blend")  # if doesn't exist
        
        >>> increment_filename(Path("/assets"), "MyAsset", ".blend")
        Path("/assets/MyAsset_001.blend")  # if MyAsset.blend exists
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

    # Validate UUID format to prevent injection attacks
    try:
        uuid.UUID(catalog_uuid)
    except (ValueError, AttributeError, TypeError):
        print(f"Invalid UUID format: {catalog_uuid}")
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

        # Parse CDF format: UUID:catalog_path:catalog_name
        # Lines starting with # are comments or headers
        idx = 1  # Start from 1 since UNASSIGNED is 0
        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("VERSION"):
                continue

            parts = line.split(":")
            if len(parts) >= 2:
                catalog_uuid = parts[0].strip()
                catalog_path = parts[1].strip()

                # Skip empty paths
                if not catalog_path:
                    print(f"Line {line_num}: Empty catalog path, skipping")
                    continue

                # Validate UUID format
                try:
                    uuid.UUID(catalog_uuid)
                    catalogs[catalog_path] = catalog_uuid
                    
                    # Use catalog path as display name (Unicode is supported)
                    display_name = catalog_path
                    
                    debug_print(f"[QAS Catalog Debug] Adding catalog {idx}: uuid={catalog_uuid}, name={display_name}")
                    
                    # Create enum item with UUID as identifier (ASCII-safe)
                    enum_items.append(
                        (
                            catalog_uuid,           # UUID is ASCII-safe identifier
                            display_name,           # Display name - Unicode OK!
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

    # Cache items to prevent garbage collection before Blender displays them
    _CATALOG_ENUM_CACHE = enum_items
    debug_print(f"[QAS Catalog Debug] Cached {len(_CATALOG_ENUM_CACHE)} catalog items")
    
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

    # Remove existing tags (iterate backwards to avoid index issues)
    while len(asset_data.tags) > 0:
        asset_data.tags.remove(asset_data.tags[-1])

    # Add new tags
    if tags_string:
        tags_list = [t.strip() for t in tags_string.split(",") if t.strip()]
        for tag in tags_list:
            asset_data.tags.new(tag)


def collect_external_dependencies(datablock):
    """
    Collect all external file dependencies used by a datablock.

    Recursively traverses materials, node trees, modifiers, and other
    components to find all datablocks that reference external files
    and should be packed with the asset.

    Collects:
    - Images (textures, HDRIs, etc.)
    - Fonts (used in text objects)
    - Sounds (audio files)
    - Movie Clips (video files)
    - Volumes (OpenVDB files)

    Args:
        datablock: Blender datablock (Object, Material, NodeTree, etc.)

    Returns:
        dict: Dictionary with keys 'images', 'fonts', 'sounds', 'movieclips', 'volumes'
              containing sets of respective datablock types
    
    Note:
        Libraries (linked .blend files) are noted but not packed.
        Volume files (.vdb) cannot be packed and will generate warnings.
    """
    dependencies = {
        'images': set(),
        'fonts': set(),
        'sounds': set(),
        'movieclips': set(),
        'volumes': set(),
    }

    def collect_from_node_tree(node_tree):
        """Collect dependencies from a node tree."""
        if not node_tree:
            return
        for node in node_tree.nodes:
            # Image texture nodes
            if hasattr(node, 'image') and node.image:
                dependencies['images'].add(node.image)
            # Movie clip nodes
            if hasattr(node, 'clip') and node.clip:
                dependencies['movieclips'].add(node.clip)
            # IES texture nodes (light profiles stored as images)
            if node.type == 'TEX_IES' and hasattr(node, 'ies') and node.ies:
                # IES files are stored differently, but check for image reference
                pass
            # Nested node groups
            if hasattr(node, 'node_tree') and node.node_tree:
                collect_from_node_tree(node.node_tree)

    def collect_from_material(material):
        """Collect dependencies from a material."""
        if not material:
            return
        # Node-based materials
        if material.use_nodes and material.node_tree:
            collect_from_node_tree(material.node_tree)
        # Legacy texture slots (for older .blend files)
        if hasattr(material, 'texture_slots'):
            for slot in material.texture_slots:
                if slot and slot.texture:
                    if hasattr(slot.texture, 'image') and slot.texture.image:
                        dependencies['images'].add(slot.texture.image)

    def collect_from_object(obj):
        """Collect dependencies from an object and its modifiers."""
        if not obj:
            return

        # Check object data for materials
        if obj.data:
            if hasattr(obj.data, 'materials'):
                for mat in obj.data.materials:
                    collect_from_material(mat)

            # Text objects use fonts
            if obj.type == 'FONT' and hasattr(obj.data, 'font'):
                if obj.data.font:
                    dependencies['fonts'].add(obj.data.font)
                # Also check font_bold, font_italic, font_bold_italic
                for font_attr in ['font_bold', 'font_italic', 'font_bold_italic']:
                    font = getattr(obj.data, font_attr, None)
                    if font:
                        dependencies['fonts'].add(font)

        # Check material slots
        if hasattr(obj, 'material_slots'):
            for slot in obj.material_slots:
                if slot.material:
                    collect_from_material(slot.material)

        # Check modifiers for external dependencies
        if hasattr(obj, 'modifiers'):
            for mod in obj.modifiers:
                # Volume modifiers (Mesh to Volume, Volume Displace, etc.)
                if hasattr(mod, 'texture') and mod.texture:
                    if hasattr(mod.texture, 'image') and mod.texture.image:
                        dependencies['images'].add(mod.texture.image)
                
                # Ocean modifier bake files (image sequences)
                if mod.type == 'OCEAN' and hasattr(mod, 'filepath') and mod.filepath:
                    # Ocean bakes are cached files, not typically packed
                    pass

        # Check geometry nodes for volumes/images
        if hasattr(obj, 'modifiers'):
            for mod in obj.modifiers:
                if mod.type == 'NODES' and hasattr(mod, 'node_group') and mod.node_group:
                    collect_from_node_tree(mod.node_group)

    # Handle different datablock types
    if hasattr(datablock, 'type'):  # It's likely an Object
        collect_from_object(datablock)
    elif hasattr(datablock, 'data') and datablock.data:
        # Object wrapper - check the data
        obj_data = datablock.data
        if hasattr(obj_data, 'materials'):
            for mat in obj_data.materials:
                collect_from_material(mat)

    # Check materials directly on the datablock
    if hasattr(datablock, 'materials'):
        for mat in datablock.materials:
            collect_from_material(mat)

    # Check material slots for objects
    if hasattr(datablock, 'material_slots'):
        for slot in datablock.material_slots:
            if slot.material:
                collect_from_material(slot.material)

    # If datablock is a material itself
    if isinstance(datablock, bpy.types.Material):
        collect_from_material(datablock)

    # If datablock is a node tree (geometry nodes, compositor, etc.)
    if isinstance(datablock, bpy.types.NodeTree):
        collect_from_node_tree(datablock)

    # If datablock is a world
    if isinstance(datablock, bpy.types.World):
        if datablock.use_nodes and datablock.node_tree:
            collect_from_node_tree(datablock.node_tree)

    # If datablock is a light
    if isinstance(datablock, bpy.types.Light):
        if datablock.use_nodes and hasattr(datablock, 'node_tree') and datablock.node_tree:
            collect_from_node_tree(datablock.node_tree)

    # If datablock is a scene (check world, compositor nodes)
    if isinstance(datablock, bpy.types.Scene):
        if datablock.world:
            if datablock.world.use_nodes and datablock.world.node_tree:
                collect_from_node_tree(datablock.world.node_tree)
        if datablock.use_nodes and datablock.node_tree:
            collect_from_node_tree(datablock.node_tree)
        # Check sequence editor for sounds/movies
        if hasattr(datablock, 'sequence_editor') and datablock.sequence_editor:
            for seq in datablock.sequence_editor.sequences_all:
                if hasattr(seq, 'sound') and seq.sound:
                    dependencies['sounds'].add(seq.sound)
                if hasattr(seq, 'clip') and seq.clip:
                    dependencies['movieclips'].add(seq.clip)

    # If datablock is a speaker (uses sounds)
    if isinstance(datablock, bpy.types.Speaker):
        if datablock.sound:
            dependencies['sounds'].add(datablock.sound)

    # If datablock is a Volume (OpenVDB)
    if hasattr(bpy.types, 'Volume') and isinstance(datablock, bpy.types.Volume):
        dependencies['volumes'].add(datablock)

    return dependencies


def collect_selected_asset_files(context):
    """Collect absolute Paths to selected asset .blend files in the active Asset Browser.

    Returns a tuple (asset_paths, active_library) where active_library is the
    Blender preferences library object for the current Asset Browser context (or None).
    """
    asset_paths = []
    asset_blend_files = set()

    # Try to resolve the active library similar to bundler logic
    prefs = context.preferences
    active_library = None
    params = getattr(context.space_data, "params", None)
    if params is not None:
        asset_lib_ref = None
        if hasattr(params, "asset_library_reference"):
            asset_lib_ref = params.asset_library_reference
        if not asset_lib_ref and hasattr(params, "asset_library_ref"):
            asset_lib_ref = params.asset_library_ref
        if asset_lib_ref and hasattr(prefs, "filepaths") and hasattr(prefs.filepaths, "asset_libraries"):
            for lib in prefs.filepaths.asset_libraries:
                if getattr(lib, "name", None) == asset_lib_ref:
                    active_library = lib
                    break

    library_path = Path(active_library.path) if active_library and getattr(active_library, "path", None) else None

    # Gather selected asset files from context using multiple API forms
    asset_files = None
    if hasattr(context, "selected_asset_files") and context.selected_asset_files is not None:
        asset_files = context.selected_asset_files
    elif hasattr(context, "selected_assets") and context.selected_assets is not None:
        asset_files = context.selected_assets
    elif hasattr(context.space_data, "files"):
        try:
            asset_files = [f for f in context.space_data.files if getattr(f, "select", False)]
        except (AttributeError, TypeError, RuntimeError):
            asset_files = None

    if not asset_files:
        return [], active_library

    for asset_file in asset_files:
        asset_path = None
        if hasattr(asset_file, "full_library_path") and asset_file.full_library_path:
            asset_path = Path(asset_file.full_library_path)
        elif hasattr(asset_file, "full_path") and asset_file.full_path:
            asset_path = Path(asset_file.full_path)
        elif hasattr(asset_file, "relative_path") and library_path:
            asset_path = library_path / asset_file.relative_path
        elif hasattr(asset_file, "name") and library_path:
            name = asset_file.name
            asset_path = library_path / (name if name.endswith(".blend") else f"{name}.blend")

        if asset_path and asset_path.exists() and asset_path.is_file() and asset_path.suffix.lower() == ".blend":
            # sanity size check
            try:
                if asset_path.stat().st_size > 100:
                    asset_blend_files.add(asset_path)
            except Exception:
                pass

    asset_paths = list(asset_blend_files)
    return asset_paths, active_library


def write_blend_file(filepath, datablocks):
    """
    Write a .blend file containing only the specified datablocks.

    Automatically packs all external dependencies (images, fonts, sounds, etc.)
    used by the datablocks to ensure the asset is self-contained.

    Args:
        filepath: Path to the destination .blend file
        datablocks: Set of Blender datablocks to write

    Returns:
        bool: True if successful, False otherwise
    """
    temp_file = None
    # Track what we packed so we can restore state after saving
    packed_items = {
        'images': [],
        'fonts': [],
        'sounds': [],
        'movieclips': [],
        'volumes': [],
    }

    try:
        filepath = Path(filepath)
        temp_dir = filepath.parent
        temp_file = temp_dir / f".tmp_{filepath.name}"

        # Collect all external dependencies from the datablocks
        all_dependencies = {
            'images': set(),
            'fonts': set(),
            'sounds': set(),
            'movieclips': set(),
            'volumes': set(),
        }
        
        for datablock in datablocks:
            deps = collect_external_dependencies(datablock)
            for key in all_dependencies:
                all_dependencies[key].update(deps[key])

        # Pack images that have external sources
        for image in all_dependencies['images']:
            if image and image.source == 'FILE' and not image.packed_file:
                try:
                    packed_items['images'].append(image)
                    image.pack()
                    debug_print(f"Packed image: {image.name}")
                except Exception as e:
                    print(f"Warning: Could not pack image '{image.name}': {e}")

        # Pack fonts that have external sources
        for font in all_dependencies['fonts']:
            if font and not font.packed_file:
                # Skip built-in font "Bfont"
                if font.filepath and font.filepath != '<builtin>':
                    try:
                        packed_items['fonts'].append(font)
                        font.pack()
                        debug_print(f"Packed font: {font.name}")
                    except Exception as e:
                        print(f"Warning: Could not pack font '{font.name}': {e}")

        # Pack sounds that have external sources
        for sound in all_dependencies['sounds']:
            if sound and not sound.packed_file:
                try:
                    packed_items['sounds'].append(sound)
                    sound.pack()
                    debug_print(f"Packed sound: {sound.name}")
                except Exception as e:
                    print(f"Warning: Could not pack sound '{sound.name}': {e}")

        # Pack movie clips (if supported)
        for clip in all_dependencies['movieclips']:
            if clip and hasattr(clip, 'packed_file') and not clip.packed_file:
                try:
                    packed_items['movieclips'].append(clip)
                    clip.pack()
                    debug_print(f"Packed movie clip: {clip.name}")
                except Exception as e:
                    print(f"Warning: Could not pack movie clip '{clip.name}': {e}")

        # Note: Volumes (OpenVDB) cannot be packed in Blender, just log a warning
        for volume in all_dependencies['volumes']:
            if volume and hasattr(volume, 'filepath') and volume.filepath:
                print(f"Warning: Volume '{volume.name}' has external file '{volume.filepath}' which cannot be packed. "
                      "Consider placing the VDB file in a location accessible from the asset library.")

        bpy.data.libraries.write(
            str(temp_file),
            datablocks,
            path_remap="RELATIVE_ALL",
            fake_user=True,
            compress=True,
        )

        # Restore unpacked state for all items in current session
        for image in packed_items['images']:
            try:
                if image.packed_file:
                    image.unpack(method='USE_ORIGINAL')
            except Exception as e:
                debug_print(f"Could not restore image '{image.name}': {e}")

        for font in packed_items['fonts']:
            try:
                if font.packed_file:
                    font.unpack(method='USE_ORIGINAL')
            except Exception as e:
                debug_print(f"Could not restore font '{font.name}': {e}")

        for sound in packed_items['sounds']:
            try:
                if sound.packed_file:
                    sound.unpack(method='USE_ORIGINAL')
            except Exception as e:
                debug_print(f"Could not restore sound '{sound.name}': {e}")

        for clip in packed_items['movieclips']:
            try:
                if hasattr(clip, 'packed_file') and clip.packed_file:
                    clip.unpack(method='USE_ORIGINAL')
            except Exception as e:
                debug_print(f"Could not restore movie clip '{clip.name}': {e}")

        if filepath.exists():
            filepath.unlink()

        shutil.move(str(temp_file), str(filepath))
        return True

    except (OSError, IOError) as e:
        print(f"Error writing blend file: {e}")
        _restore_packed_items(packed_items)
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except OSError as cleanup_error:
                print(f"Failed to clean up temp file: {cleanup_error}")
        return False
    except (RuntimeError, ValueError) as e:
        print(f"Blender API error writing blend file: {e}")
        _restore_packed_items(packed_items)
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
            except OSError as cleanup_error:
                print(f"Failed to clean up temp file: {cleanup_error}")
        return False


def _restore_packed_items(packed_items):
    """
    Restore unpacked state for all temporarily packed items.
    
    Called after saving to restore the session state, or on error to clean up.
    Silently handles individual failures to ensure all items are attempted.
    
    Args:
        packed_items (dict): Dictionary with keys matching dependency types,
                           each containing a list of datablocks to restore
    """
    for image in packed_items.get('images', []):
        try:
            if image.packed_file:
                image.unpack(method='USE_ORIGINAL')
        except (RuntimeError, AttributeError):
            pass
    
    for font in packed_items.get('fonts', []):
        try:
            if font.packed_file:
                font.unpack(method='USE_ORIGINAL')
        except (RuntimeError, AttributeError):
            pass
    
    for sound in packed_items.get('sounds', []):
        try:
            if sound.packed_file:
                sound.unpack(method='USE_ORIGINAL')
        except (RuntimeError, AttributeError):
            pass
    
    for clip in packed_items.get('movieclips', []):
        try:
            if hasattr(clip, 'packed_file') and clip.packed_file:
                clip.unpack(method='USE_ORIGINAL')
        except (RuntimeError, AttributeError):
            pass


class QAS_OT_open_library_folder(Operator):
    """Open the asset library folder in the system file browser"""

    bl_idname = "qas.open_library_folder"
    bl_label = "Open Library Folder"
    bl_description = "Open the configured asset library folder in your file browser"
    bl_options = {"REGISTER"}

    def execute(self, context):
        """
        Execute the operator to open the library folder.

        Returns:
            set: {'FINISHED'} if successful, {'CANCELLED'} otherwise
        """
        from .properties import get_library_by_identifier

        wm = context.window_manager
        props = wm.qas_save_props

        if not props.selected_library or props.selected_library == "NONE":
            self.report({"ERROR"}, "No asset library selected")
            return {"CANCELLED"}

        # Get the actual path from library identifier
        library_name, library_path_str = get_library_by_identifier(props.selected_library)
        if not library_path_str:
            self.report({"ERROR"}, f"Could not find library: {props.selected_library}")
            return {"CANCELLED"}

        library_path = Path(library_path_str)
        if not library_path.exists():
            self.report({"ERROR"}, "Library path does not exist")
            return {"CANCELLED"}

        bpy.ops.wm.path_open(filepath=str(library_path))
        return {"FINISHED"}





class QAS_OT_move_selected_to_library(Operator):
    """Move selected asset files to another library and optionally assign a catalog."""

    bl_idname = "qas.move_selected_to_library"
    bl_label = "Move Assets"
    bl_description = "Move selected assets to the target library and assign the chosen catalog"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return (
            hasattr(context, "space_data")
            and context.space_data.type == "FILE_BROWSER"
            and getattr(context.space_data, "browse_mode", None) == "ASSETS"
        )

    def execute(self, context):
        from .properties import get_library_by_identifier

        prefs = get_addon_preferences()
        wm = context.window_manager
        manage = getattr(wm, "qas_manage_props", None)
        if not manage:
            self.report({"ERROR"}, "Internal properties missing")
            return {"CANCELLED"}

        selected_paths, active_library = collect_selected_asset_files(context)
        if not selected_paths:
            self.report({"WARNING"}, "No assets selected")
            return {"CANCELLED"}

        # Resolve target library path from identifier
        if not manage.move_target_library or manage.move_target_library == "NONE":
            self.report({"ERROR"}, "Please choose a target library")
            return {"CANCELLED"}

        target_name, target_path_str = get_library_by_identifier(manage.move_target_library)
        if not target_path_str:
            self.report({"ERROR"}, "Target library path not found")
            return {"CANCELLED"}

        target_root = Path(target_path_str)
        if not target_root.exists():
            try:
                target_root.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.report({"ERROR"}, f"Cannot access target library: {e}")
                return {"CANCELLED"}

        # Determine target catalog UUID
        target_catalog_uuid = manage.move_target_catalog if manage.move_target_catalog else "UNASSIGNED"
        
        # Build destination directory with optional catalog subfolders
        dest_base = target_root
        if prefs and prefs.use_catalog_subfolders and target_catalog_uuid != "UNASSIGNED":
            catalog_path = get_catalog_path_from_uuid(str(target_root), target_catalog_uuid)
            if catalog_path:
                for part in [p for p in catalog_path.split("/") if p]:
                    dest_base = dest_base / sanitize_name(part, max_length=64)

        try:
            dest_base.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.report({"ERROR"}, f"Could not create destination folders: {e}")
            return {"CANCELLED"}

        moved = 0
        skipped = 0
        catalog_updated = 0
        
        for src in selected_paths:
            try:
                # First update catalog inside the source file BEFORE moving
                # This way we modify the file in its original location
                if target_catalog_uuid != "UNASSIGNED":
                    if self._update_catalog_in_blend(src, target_catalog_uuid):
                        catalog_updated += 1
                
                # Build destination path
                dest = dest_base / src.name
                
                # Check if source and destination are the same location
                same_location = False
                try:
                    same_location = src.resolve() == dest.resolve()
                except Exception:
                    pass
                    
                if same_location:
                    # Same location - catalog already updated above, just skip the move
                    skipped += 1
                    continue
                
                # Create destination folder structure
                dest.parent.mkdir(parents=True, exist_ok=True)
                
                # Check for conflicts ONLY if a different file exists at destination
                if dest.exists():
                    mode = manage.move_conflict_resolution
                    if mode == "INCREMENT":
                        # Only increment if there's actually a different file there
                        dest = increment_filename(dest.parent, dest.stem, dest.suffix)
                    elif mode == "CANCEL":
                        skipped += 1
                        continue
                    elif mode == "OVERWRITE":
                        # Remove existing file before move
                        dest.unlink()
                
                # Move the file
                shutil.move(str(src), str(dest))
                moved += 1
            except Exception as e:
                print(f"Failed to move {src.name}: {e}")
                skipped += 1

        # Force refresh asset browser
        try:
            if hasattr(bpy.ops.asset, "library_refresh"):
                bpy.ops.asset.library_refresh()
            # Also try triggering a general refresh
            for area in context.screen.areas:
                if area.type == 'FILE_BROWSER':
                    area.tag_redraw()
        except Exception:
            pass

        msg = f"Moved {moved} file(s)"
        if catalog_updated:
            msg += f", catalog set on {catalog_updated}"
        if skipped:
            msg += f", skipped {skipped}"
        self.report({"INFO"}, msg)
        return {"FINISHED"}

    def _update_catalog_in_blend(self, blend_path, catalog_uuid):
        """
        Open a .blend file, set catalog_id on all asset datablocks, and save.
        
        Args:
            blend_path: Path to the .blend file
            catalog_uuid: UUID string for the target catalog
            
        Returns:
            bool: True if successful
        """
        # We need to import assets, modify them, then write back
        # This is tricky because we can't directly edit external files
        # Strategy: load datablocks, modify catalog_id, write to temp, replace original
        
        try:
            # Collections to check for assets
            datablock_collections = [
                'objects', 'materials', 'node_groups', 'worlds', 'collections',
                'meshes', 'curves', 'armatures', 'actions', 'brushes',
            ]
            
            # First pass: get the names we're about to import
            names_to_import = {}  # collection_name -> list of names
            with bpy.data.libraries.load(str(blend_path), link=False, assets_only=False) as (data_from, data_to):
                for collection_name in datablock_collections:
                    if hasattr(data_from, collection_name):
                        source = getattr(data_from, collection_name)
                        if source:
                            names_to_import[collection_name] = list(source)
            
            # Temporarily rename any existing datablocks that would conflict
            renamed_existing = []  # List of (datablock, original_name)
            for collection_name, names in names_to_import.items():
                if hasattr(bpy.data, collection_name):
                    collection = getattr(bpy.data, collection_name)
                    for name in names:
                        if name in collection:
                            existing_db = collection[name]
                            temp_name = f"__QAS_TEMP_{name}_{id(existing_db)}"
                            original_name = existing_db.name
                            existing_db.name = temp_name
                            renamed_existing.append((existing_db, original_name))
            
            # Now import - datablocks will get their original names without incrementing
            imported_datablocks = {}  # original_name -> datablock
            asset_datablocks = set()
            
            with bpy.data.libraries.load(str(blend_path), link=False, assets_only=False) as (data_from, data_to):
                for collection_name in datablock_collections:
                    if hasattr(data_from, collection_name):
                        source = getattr(data_from, collection_name)
                        if source:
                            setattr(data_to, collection_name, list(source))
            
            # Process imported datablocks and update catalog
            for collection_name in names_to_import.keys():
                if hasattr(data_to, collection_name):
                    for db in getattr(data_to, collection_name):
                        if db is not None:
                            imported_datablocks[db.name] = db
                            
                            # Check if it's marked as an asset
                            if hasattr(db, 'asset_data') and db.asset_data:
                                db.asset_data.catalog_id = catalog_uuid
                                asset_datablocks.add(db)
            
            if not asset_datablocks:
                # No assets found, clean up and return
                for db in imported_datablocks.values():
                    self._remove_datablock(db)
                # Restore renamed datablocks
                for existing_db, original_name in renamed_existing:
                    try:
                        existing_db.name = original_name
                    except Exception:
                        pass
                return False
            
            # Write modified datablocks back to the file
            temp_path = blend_path.parent / f".tmp_{blend_path.name}"
            
            bpy.data.libraries.write(
                str(temp_path),
                asset_datablocks,
                path_remap="RELATIVE_ALL",
                fake_user=True,
                compress=True,
            )
            
            # Clean up imported datablocks from current session
            for db in imported_datablocks.values():
                self._remove_datablock(db)
            
            # Restore renamed existing datablocks back to their original names
            for existing_db, original_name in renamed_existing:
                try:
                    existing_db.name = original_name
                except Exception:
                    pass
            
            # Replace original with temp
            if temp_path.exists():
                if blend_path.exists():
                    blend_path.unlink()
                shutil.move(str(temp_path), str(blend_path))
                return True
                
        except (RuntimeError, IOError, OSError) as e:
            print(f"Failed to update catalog in {blend_path.name}: {e}")
            # Try to clean up temp file
            try:
                temp_path = blend_path.parent / f".tmp_{blend_path.name}"
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
        
        return False
    
    def _remove_datablock(self, datablock):
        """
        Remove a datablock from the current session.
        
        Handles different datablock types and silently ignores removal failures.
        Used during cleanup of temporarily imported assets.
        
        Args:
            datablock: Blender datablock to remove
        """
        try:
            if isinstance(datablock, bpy.types.Object):
                bpy.data.objects.remove(datablock)
            elif isinstance(datablock, bpy.types.Material):
                bpy.data.materials.remove(datablock)
            elif isinstance(datablock, bpy.types.NodeTree):
                bpy.data.node_groups.remove(datablock)
            elif isinstance(datablock, bpy.types.World):
                bpy.data.worlds.remove(datablock)
            elif isinstance(datablock, bpy.types.Collection):
                bpy.data.collections.remove(datablock)
            elif isinstance(datablock, bpy.types.Mesh):
                bpy.data.meshes.remove(datablock)
            elif isinstance(datablock, bpy.types.Curve):
                bpy.data.curves.remove(datablock)
            elif isinstance(datablock, bpy.types.Armature):
                bpy.data.armatures.remove(datablock)
            elif isinstance(datablock, bpy.types.Action):
                bpy.data.actions.remove(datablock)
            elif isinstance(datablock, bpy.types.Brush):
                bpy.data.brushes.remove(datablock)
        except (RuntimeError, ReferenceError):
            # Datablock may already be removed or invalid reference
            pass


class QAS_OT_delete_selected_assets(Operator):
    """Permanently delete selected asset files - THIS CANNOT BE UNDONE!"""

    bl_idname = "qas.delete_selected_assets"
    bl_label = "Delete Selected Assets"
    bl_description = "Permanently delete the selected asset files from disk"
    bl_options = {"REGISTER"}

    def invoke(self, context, event):
        # Centered properties dialog with custom warning text
        return context.window_manager.invoke_props_dialog(self, width=420)

    def draw(self, context):
        layout = self.layout
        layout.alert = True
        box = layout.box()
        box.alert = True
        col = box.column(align=True)
        col.label(text="Delete Selected Assets?", icon="ERROR")
        col.label(text="This is PERMANENT and CAN'T be undone!")

    @classmethod
    def poll(cls, context):
        return (
            hasattr(context, "space_data")
            and context.space_data.type == "FILE_BROWSER"
            and getattr(context.space_data, "browse_mode", None) == "ASSETS"
        )

    def execute(self, context):
        prefs = get_addon_preferences()
        selected_paths, active_library = collect_selected_asset_files(context)
        if not selected_paths:
            self.report({"WARNING"}, "No assets selected")
            return {"CANCELLED"}

        deleted = 0
        failed = 0

        for p in selected_paths:
            try:
                p.unlink()
                deleted += 1
            except (OSError, PermissionError) as e:
                print(f"Failed to delete {p.name}: {e}")
                failed += 1

        # Refresh asset browser
        if prefs and prefs.auto_refresh:
            try:
                if hasattr(bpy.ops.asset, "library_refresh"):
                    bpy.ops.asset.library_refresh()
                elif hasattr(bpy.ops.asset, "refresh"):
                    bpy.ops.asset.refresh()
            except (RuntimeError, AttributeError):
                pass

        if failed:
            self.report({"WARNING"}, f"Deleted {deleted}, failed {failed}")
        else:
            self.report({"INFO"}, f"Deleted {deleted} file(s)")
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
        from .properties import get_library_by_identifier

        # Get preferences and properties
        prefs = properties.get_addon_preferences(context)
        wm = context.window_manager
        props = wm.qas_save_props

        # Validate library selection
        if not props.selected_library or props.selected_library == "NONE":
            self.report({"ERROR"}, "No asset library selected")
            return {"CANCELLED"}

        # Get the actual path from library identifier
        library_name, library_path_str = get_library_by_identifier(props.selected_library)
        
        
        # Debug: print what we got
        debug_print(f"[QAS Debug] Selected library identifier: {props.selected_library}")
        debug_print(f"[QAS Debug] Resolved library name: {library_name}")
        debug_print(f"[QAS Debug] Resolved library path: {library_path_str}")
        
        if not library_path_str:
            self.report({"ERROR"}, f"Could not find library for: {props.selected_library}. Please re-select the library.")
            return {"CANCELLED"}

        library_path = Path(library_path_str)
        if not library_path.exists():
            self.report({"ERROR"}, f"Library path does not exist: {library_path}")
            return {"CANCELLED"}

        # Determine target directory based on catalog preference
        target_dir = library_path

        if (
            prefs.use_catalog_subfolders
            and props.catalog
            and props.catalog != "UNASSIGNED"
        ):
            # Get the catalog path from UUID
            catalog_path = get_catalog_path_from_uuid(
                library_path_str, props.catalog
            )

            if catalog_path:
                # Sanitize catalog path components to prevent directory traversal
                # Note: sanitize_name removes path separators and invalid chars
                path_parts = catalog_path.split("/")
                sanitized_parts = [
                    sanitize_name(part, max_length=64) for part in path_parts if part
                ]

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

            # Set tags using helper function
            clear_and_set_tags(asset_id.asset_data, props.asset_tags)

        datablocks = {asset_id}

        # Write the blend file
        success = write_blend_file(output_path, datablocks)

        if not success:
            self.report({"ERROR"}, f"Failed to write {output_path.name}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Saved asset to {output_path.name}")
        
        # Show success message in panel
        props.show_success_message = True

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
            except (RuntimeError, AttributeError) as e:
                print(f"Could not refresh asset browser: {e}")

        return {"FINISHED"}


# ============================================================================
# QUICK ASSET BUNDLER OPERATOR
# ============================================================================


class QAS_OT_bundle_assets(Operator):
    """Bundle selected assets from a user library into a single .blend file."""

    bl_idname = "qas.bundle_assets"
    bl_label = "Bundle Selected Assets"
    bl_description = "Combine selected assets into a single shareable .blend file"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Only enable when in Asset Browser with a user-configured library."""
        if not context.space_data or context.space_data.type != "FILE_BROWSER":
            return False

        if not hasattr(context.space_data, "browse_mode"):
            return False

        if context.space_data.browse_mode != "ASSETS":
            return False

        params = context.space_data.params
        if not hasattr(params, "asset_library_reference"):
            return False

        asset_lib_ref = params.asset_library_reference

        # Exclude built-in and special libraries
        excluded_refs = ["LOCAL", "CURRENT", "ALL", "ESSENTIALS"]
        if asset_lib_ref in excluded_refs:
            return False

        # Also check the newer API attribute if it exists
        if hasattr(params, "asset_library_ref"):
            newer_ref = params.asset_library_ref
            if newer_ref in excluded_refs:
                return False

        # Verify this is actually a user-configured library
        prefs = context.preferences
        if hasattr(prefs, "filepaths") and hasattr(prefs.filepaths, "asset_libraries"):
            for lib in prefs.filepaths.asset_libraries:
                if hasattr(lib, "name") and lib.name == asset_lib_ref:
                    return True

        return False

    def execute(self, context):
        """
        Execute the bundling operation.

        This method:
        1. Collects selected assets from the active library
        2. Validates RAM availability
        3. Imports all assets into current file
        4. Saves as a new bundle file
        5. Optionally copies catalog file

        Returns:
            set: {'FINISHED'} if successful, {'CANCELLED'} otherwise
        """
        from datetime import datetime

        wm = context.window_manager
        props = wm.qas_bundler_props

        selected_assets = self._collect_selected_assets(context)

        if not selected_assets:
            self.report({"WARNING"}, "No assets selected")
            return {"CANCELLED"}

        active_library = self._get_active_library(context)
        if not active_library:
            self.report({"ERROR"}, "Could not determine active asset library")
            return {"CANCELLED"}

        library_path = Path(active_library.path)
        save_path = Path(props.save_path) if props.save_path else Path.home()

        try:
            if save_path.resolve().is_relative_to(library_path.resolve()):
                self.report(
                    {"WARNING"},
                    "Saving bundle inside asset library directory - this may cause issues",
                )
        except (ValueError, OSError):
            pass

        if len(selected_assets) > LARGE_SELECTION_WARNING_THRESHOLD:
            self.report(
                {"INFO"},
                f"Bundling {len(selected_assets)} assets - this may take several minutes",
            )

        total_size_mb = self._calculate_total_size(selected_assets)
        preferences = get_addon_preferences()
        max_bundle_size_mb = preferences.max_bundle_size_mb if preferences else DEFAULT_MAX_BUNDLE_SIZE_MB

        print(f"Total asset size: {total_size_mb:.1f} MB")
        print(f"Max bundle size: {max_bundle_size_mb} MB")

        if total_size_mb > max_bundle_size_mb:
            self.report(
                {"ERROR"},
                f"Bundle too large: {total_size_mb:.0f}MB exceeds limit of {max_bundle_size_mb}MB. "
                f"Try selecting fewer assets or increase the limit in addon preferences.",
            )
            return {"CANCELLED"}

        if total_size_mb > VERY_LARGE_BUNDLE_WARNING_MB:
            self.report(
                {"WARNING"},
                f"Very large selection ({total_size_mb / 1024:.1f}GB). "
                "This may take a very long time and use significant RAM.",
            )

        output_name = props.output_name if props.output_name else "AssetBundle"
        output_name = sanitize_name(output_name)
        date_str = datetime.now().strftime("%Y-%m-%d")

        try:
            save_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.report({"ERROR"}, f"Could not create output directory: {e}")
            return {"CANCELLED"}

        target_path = increment_filename(
            save_path, f"{output_name}_{date_str}", ".blend"
        )

        duplicate_mode = props.duplicate_mode
        total_assets = len(selected_assets)

        print(f"Importing {total_assets} asset files...")

        wm.progress_begin(0, total_assets)
        
        # Track import statistics
        imported_count = 0
        skipped_count = 0
        error_count = 0

        try:
            for i, asset_path in enumerate(selected_assets):
                wm.progress_update(i)
                try:
                    result = self._import_asset_file(asset_path, duplicate_mode)
                    # _import_asset_file returns None for skipped files
                    if result is None or result is False:
                        skipped_count += 1
                    else:
                        imported_count += 1
                except (RuntimeError, OSError, IOError, MemoryError) as e:
                    error_count += 1
                    print(f"  ✗ Fatal error importing '{asset_path.name}': {e}")
                    # Continue with remaining files instead of stopping
                    continue
            
            # Print summary
            print("\nImport Summary:")
            print(f"  Successfully imported: {imported_count} files")
            if skipped_count > 0:
                print(f"  Skipped (incompatible): {skipped_count} files")
            if error_count > 0:
                print(f"  Failed with errors: {error_count} files")
                
        except (RuntimeError, OSError, MemoryError) as e:
            wm.progress_end()
            self.report({"ERROR"}, f"Failed to import assets: {e}")
            import traceback

            traceback.print_exc()
            return {"CANCELLED"}
        finally:
            wm.progress_end()

        try:
            print(f"Saving bundle to: {target_path}")
            bpy.ops.wm.save_as_mainfile(filepath=str(target_path), copy=True)
            print("Bundle saved successfully")
        except (RuntimeError, OSError) as e:
            self.report({"ERROR"}, f"Failed to save bundle: {e}")
            return {"CANCELLED"}

        if props.copy_catalog:
            self._copy_catalog_file(library_path, target_path, output_name)

        # Create appropriate success message based on what happened
        if skipped_count > 0 and imported_count > 0:
            self.report(
                {"WARNING"}, 
                f"Bundle saved: {target_path.name} ({imported_count} imported, {skipped_count} skipped due to version incompatibility)"
            )
            props.show_success_message = True
        elif skipped_count > 0 and imported_count == 0:
            self.report(
                {"ERROR"},
                f"No assets could be imported - all {skipped_count} files are incompatible with this Blender version"
            )
            return {"CANCELLED"}
        else:
            self.report({"INFO"}, f"Bundle saved: {target_path.name} ({imported_count} assets)")
            props.show_success_message = True
        
        return {"FINISHED"}

    def _calculate_total_size(self, asset_paths):
        """
        Calculate the total size of all asset files in megabytes.

        Args:
            asset_paths: List of Path objects for asset .blend files

        Returns:
            float: Total size in MB
        """
        total_bytes = 0
        for asset_path in asset_paths:
            try:
                if asset_path.exists():
                    total_bytes += asset_path.stat().st_size
            except (OSError, PermissionError) as e:
                print(f"Could not get size of {asset_path.name}: {e}")
            except Exception as e:
                print(f"Unexpected error getting size of {asset_path.name}: {e}")

        return total_bytes / (1024 * 1024)  # Convert to MB

    def _collect_selected_assets(self, context):
        """
        Collect absolute paths of selected asset files.

        Supports multiple Blender versions by trying different API methods
        to access selected assets (selected_asset_files, selected_assets,
        or space_data.files).

        Args:
            context: Blender context object

        Returns:
            list: List of Path objects for selected asset .blend files
        """
        selected_assets = []
        asset_blend_files = set()  # Track unique .blend files

        active_library = self._get_active_library(context)
        if not active_library:
            debug_print("Could not get active library")
            return selected_assets

        library_path = Path(active_library.path)
        debug_print(f"Library path: {library_path}")

        # Try different methods to get selected assets (Blender 4.2+ compatibility)
        asset_files = None

        if hasattr(context, "selected_asset_files"):
            asset_files = context.selected_asset_files
            debug_print(f"Using selected_asset_files: {len(asset_files)} items")
        elif hasattr(context, "selected_assets"):
            asset_files = context.selected_assets
            debug_print(f"Using selected_assets: {len(asset_files)} items")
        elif hasattr(context.space_data, "files"):
            # Fallback: get selected files from file browser
            try:
                asset_files = [f for f in context.space_data.files if f.select]
                debug_print(f"Using space_data.files: {len(asset_files)} items")
            except (AttributeError, TypeError) as e:
                print(f"Error getting files: {e}")

        if not asset_files:
            debug_print("No asset files found")
            return selected_assets

        for asset_file in asset_files:
            asset_path = None

            # Use Blender's knowledge of where the asset is located
            if hasattr(asset_file, "full_library_path"):
                # This gives us the full path to the .blend file containing the asset
                full_path = asset_file.full_library_path
                if full_path:
                    asset_path = Path(full_path)
                    debug_print(f"Using full_library_path: {asset_path}")

            # Fallback to full_path if available
            if not asset_path and hasattr(asset_file, "full_path"):
                full_path = asset_file.full_path
                if full_path:
                    asset_path = Path(full_path)
                    debug_print(f"Using full_path: {asset_path}")

            # Fallback to relative_path construction
            if not asset_path and hasattr(asset_file, "relative_path"):
                asset_path = library_path / asset_file.relative_path
                debug_print(f"Using relative_path: {asset_file.relative_path}")

            # Last resort: try name-based construction
            if not asset_path and hasattr(asset_file, "name"):
                file_name = asset_file.name
                debug_print(f"Fallback: trying name-based path for: {file_name}")

                # Try with .blend extension
                if not file_name.endswith(".blend"):
                    asset_path = library_path / f"{file_name}.blend"
                else:
                    asset_path = library_path / file_name

            if asset_path:
                debug_print(f"Checking path: {asset_path}")

                # Validate the path more thoroughly
                if asset_path.exists():
                    if asset_path.is_file() and asset_path.suffix.lower() == ".blend":
                        # Additional validation: check file size
                        try:
                            file_size = asset_path.stat().st_size
                            if file_size > MIN_BLEND_FILE_SIZE:
                                asset_blend_files.add(asset_path)
                                debug_print(f"✓ Added asset: {asset_path.name} ({file_size} bytes)")
                            else:
                                print(f"⚠ Skipping {asset_path.name}: File too small ({file_size} bytes, minimum {MIN_BLEND_FILE_SIZE})")
                        except OSError as e:
                            print(f"⚠ Cannot access {asset_path.name}: {e}")
                    elif asset_path.is_dir():
                        debug_print(f"✗ Is a directory, not a file: {asset_path}")
                    else:
                        debug_print(f"✗ Not a .blend file: {asset_path.suffix}")
                else:
                    debug_print(f"✗ Path does not exist: {asset_path}")
                    # Try to check if parent directory exists to help diagnose the issue
                    if asset_path.parent.exists():
                        debug_print(f"   Parent directory exists: {asset_path.parent}")
                        # List what's actually in the parent directory
                        try:
                            actual_files = list(asset_path.parent.glob("*.blend"))
                            if actual_files:
                                debug_print(f"   Found {len(actual_files)} .blend files in parent directory")
                        except OSError:
                            pass

        selected_assets = list(asset_blend_files)
        debug_print(f"Total unique .blend files found: {len(selected_assets)}")

        return selected_assets

    def _get_active_library(self, context):
        """
        Get the active asset library object.

        Handles different Blender API versions by checking both
        asset_library_reference and asset_library_ref attributes.

        Args:
            context: Blender context object

        Returns:
            Library object or None if not found
        """
        prefs = context.preferences

        if not hasattr(prefs, "filepaths"):
            debug_print("No filepaths in preferences")
            return None

        if not hasattr(prefs.filepaths, "asset_libraries"):
            debug_print("No asset_libraries in filepaths")
            return None

        # Try to get the params from space_data first
        params = None
        if hasattr(context.space_data, "params"):
            params = context.space_data.params
        elif hasattr(context.area.spaces, "active"):
            params = context.area.spaces.active.params

        if not params:
            debug_print("Could not get params")
            return None

        # Try different attribute names for the library reference
        asset_lib_ref = None
        if hasattr(params, "asset_library_reference"):
            asset_lib_ref = params.asset_library_reference
            debug_print(f"Found asset_library_reference: {asset_lib_ref}")
        elif hasattr(params, "asset_library_ref"):
            asset_lib_ref = params.asset_library_ref
            debug_print(f"Found asset_library_ref: {asset_lib_ref}")

        if not asset_lib_ref:
            debug_print("No asset library reference found")
            return None

        # Find the matching library
        for lib in prefs.filepaths.asset_libraries:
            if hasattr(lib, "name") and lib.name == asset_lib_ref:
                debug_print(f"Found library: {lib.name} at {lib.path}")
                return lib

        debug_print(f"No matching library found for: {asset_lib_ref}")
        return None

    def _validate_asset_file(self, asset_path):
        """
        Validate that an asset file is suitable for import.
        
        Checks file existence, type, and size to ensure it's a valid .blend file.
        
        Args:
            asset_path (Path): Path to the asset file to validate
        
        Returns:
            tuple: (is_valid: bool, error_message: str or None)
        """
        if not asset_path.exists():
            return False, f"File does not exist: {asset_path}"
        
        if not asset_path.is_file():
            return False, f"Not a file: {asset_path}"
        
        if asset_path.suffix.lower() != ".blend":
            return False, f"Not a .blend file: {asset_path}"
        
        try:
            file_size = asset_path.stat().st_size
            if file_size < MIN_BLEND_FILE_SIZE:
                return False, f"File too small ({file_size} bytes), possibly corrupted (minimum {MIN_BLEND_FILE_SIZE} bytes)"
        except OSError as e:
            return False, f"Cannot access file: {e}"
        
        return True, None

    def _import_asset_file(self, asset_path, duplicate_mode):
        """
        Import datablocks from a .blend file, preserving asset status.

        Loads all datablocks except system collections (workspaces, scenes, etc).
        Handles name conflicts based on duplicate_mode setting.

        Args:
            asset_path (Path): Path object for the source .blend file
            duplicate_mode (str): 'INCREMENT' or 'OVERWRITE' - controls name conflict resolution
            
        Returns:
            bool: True if successfully imported, False if skipped, None for errors
        """
        print(f"  Importing: {asset_path.name}")
        
        # Validate the file before attempting to load
        is_valid, error_msg = self._validate_asset_file(asset_path)
        if not is_valid:
            print(f"  ✗ Skipping: {error_msg}")
            return False

        skip_collections = {
            "workspaces",
            "screens",
            "window_managers",
            "scenes",
            "version",
            "filepath",
            "is_dirty",
            "is_saved",
            "use_autopack",
        }

        try:
            with bpy.data.libraries.load(str(asset_path), link=False) as (
                data_from,
                data_to,
            ):
                for attr in dir(data_from):
                    if attr.startswith("_") or attr in skip_collections:
                        continue

                    try:
                        source_collection = getattr(data_from, attr, None)
                        if source_collection and len(source_collection) > 0:
                            items_to_import = []

                            for item_name in source_collection:
                                if duplicate_mode == "OVERWRITE":
                                    self._remove_existing_datablock(attr, item_name)

                                items_to_import.append(item_name)

                            if items_to_import:
                                setattr(data_to, attr, items_to_import)
                    except (AttributeError, TypeError, KeyError, RuntimeError) as e:
                        # Silently skip collections that can't be processed
                        debug_print(f"Skipping collection '{attr}': {e}")
                    except (ValueError, MemoryError) as e:
                        # Log unexpected errors but continue processing
                        print(f"Unexpected error processing collection '{attr}': {e}")
        except (OSError, IOError, RuntimeError) as e:
            error_msg = str(e)
            if "not a blend file" in error_msg.lower() or "failed to read blend file" in error_msg.lower():
                print(f"  ⚠ Skipping '{asset_path.name}': Incompatible blend file version")
                print("     (This file may have been created in a newer version of Blender)")
                # Don't raise - continue with remaining files
                return False
            else:
                # For other errors, re-raise to stop the bundling
                print(f"  ✗ Error loading blend file '{asset_path.name}': {e}")
                print(f"     Full path: {asset_path}")
                raise
        
        # If we get here, import was successful
        return True

    def _remove_existing_datablock(self, collection_name, item_name):
        """
        Remove an existing datablock if OVERWRITE mode is active.

        Used during asset bundling to replace duplicate datablocks with
        newer versions from the imported assets.

        Args:
            collection_name (str): Name of the bpy.data collection (e.g., 'objects', 'materials')
            item_name (str): Name of the item to remove
        """
        try:
            collection = getattr(bpy.data, collection_name, None)
            if collection and item_name in collection:
                datablock = collection[item_name]
                collection.remove(datablock)
        except (RuntimeError, ReferenceError, KeyError) as e:
            debug_print(f"Could not remove existing datablock {item_name}: {e}")

    def _copy_catalog_file(self, library_path, target_path, output_name):
        """
        Copy the catalog definition file next to the bundle.

        Args:
            library_path: Path to the source asset library
            target_path: Path to the bundle .blend file
            output_name: Base name for the catalog backup file
        """
        catalog_source = library_path / "blender_assets.cats.txt"

        if not catalog_source.exists():
            print(f"No catalog file found at {catalog_source}")
            return

        catalog_dest = increment_filename(
            target_path.parent, f"{output_name}.blender_assets.cats", ".txt"
        )

        try:
            shutil.copy(catalog_source, catalog_dest)
            print(f"Catalog file copied to {catalog_dest}")
        except (OSError, IOError, shutil.Error) as e:
            print(f"Warning: Could not copy catalog file: {e}")


class QAS_OT_open_bundle_folder(Operator):
    """Open the folder where bundles are saved."""

    bl_idname = "qas.open_bundle_folder"
    bl_label = "Open Bundle Folder"
    bl_description = "Open the folder where asset bundles are saved"

    def execute(self, context):
        """
        Open the bundle save folder in the system file browser.

        Returns:
            set: {'FINISHED'} if successful, {'CANCELLED'} if folder doesn't exist
        """
        wm = context.window_manager
        props = wm.qas_bundler_props

        folder_path = props.save_path if props.save_path else str(Path.home())

        if not Path(folder_path).exists():
            self.report({"WARNING"}, "Folder does not exist yet")
            return {"CANCELLED"}

        bpy.ops.wm.path_open(filepath=folder_path)
        return {"FINISHED"}


classes = (
    QAS_OT_save_asset_to_library_direct,
    QAS_OT_open_library_folder,
    QAS_OT_move_selected_to_library,
    QAS_OT_delete_selected_assets,
    QAS_OT_bundle_assets,
    QAS_OT_open_bundle_folder,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
