"""
File I/O operations for Quick Asset Saver.
Handles reading/writing .blend files, dependency collection, and asset extraction.
"""

import shutil
from pathlib import Path

import bpy

from .utils import debug_print, MIN_BLEND_FILE_SIZE


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
            if hasattr(node, 'image') and node.image:
                dependencies['images'].add(node.image)
            if hasattr(node, 'clip') and node.clip:
                dependencies['movieclips'].add(node.clip)
            if node.type == 'TEX_IES' and hasattr(node, 'ies') and node.ies:
                pass
            if hasattr(node, 'node_tree') and node.node_tree:
                collect_from_node_tree(node.node_tree)

    def collect_from_material(material):
        """Collect dependencies from a material."""
        if not material:
            return
        if material.use_nodes and material.node_tree:
            collect_from_node_tree(material.node_tree)
        if hasattr(material, 'texture_slots'):
            for slot in material.texture_slots:
                if slot and slot.texture:
                    if hasattr(slot.texture, 'image') and slot.texture.image:
                        dependencies['images'].add(slot.texture.image)

    def collect_from_object(obj):
        """Collect dependencies from an object and its modifiers."""
        if not obj:
            return

        if obj.data:
            if hasattr(obj.data, 'materials'):
                for mat in obj.data.materials:
                    collect_from_material(mat)

            if obj.type == 'FONT' and hasattr(obj.data, 'font'):
                if obj.data.font:
                    dependencies['fonts'].add(obj.data.font)
                for font_attr in ['font_bold', 'font_italic', 'font_bold_italic']:
                    font = getattr(obj.data, font_attr, None)
                    if font:
                        dependencies['fonts'].add(font)

        if hasattr(obj, 'material_slots'):
            for slot in obj.material_slots:
                if slot.material:
                    collect_from_material(slot.material)

        if hasattr(obj, 'modifiers'):
            for mod in obj.modifiers:
                if hasattr(mod, 'texture') and mod.texture:
                    if hasattr(mod.texture, 'image') and mod.texture.image:
                        dependencies['images'].add(mod.texture.image)
                
                if mod.type == 'OCEAN' and hasattr(mod, 'filepath') and mod.filepath:
                    pass

        if hasattr(obj, 'modifiers'):
            for mod in obj.modifiers:
                if mod.type == 'NODES' and hasattr(mod, 'node_group') and mod.node_group:
                    collect_from_node_tree(mod.node_group)

    if isinstance(datablock, bpy.types.Material):
        collect_from_material(datablock)
    
    elif isinstance(datablock, bpy.types.NodeTree):
        collect_from_node_tree(datablock)
    
    elif isinstance(datablock, bpy.types.World):
        if datablock.use_nodes and datablock.node_tree:
            collect_from_node_tree(datablock.node_tree)
    
    elif isinstance(datablock, bpy.types.Light):
        if datablock.use_nodes and hasattr(datablock, 'node_tree') and datablock.node_tree:
            collect_from_node_tree(datablock.node_tree)
    
    elif isinstance(datablock, bpy.types.Scene):
        if datablock.world:
            if datablock.world.use_nodes and datablock.world.node_tree:
                collect_from_node_tree(datablock.world.node_tree)
        if hasattr(datablock, 'sequence_editor') and datablock.sequence_editor:
            for seq in datablock.sequence_editor.sequences_all:
                if hasattr(seq, 'sound') and seq.sound:
                    dependencies['sounds'].add(seq.sound)
                if hasattr(seq, 'clip') and seq.clip:
                    dependencies['movieclips'].add(seq.clip)
    
    elif isinstance(datablock, bpy.types.Object):
        collect_from_object(datablock)
        if datablock.data and hasattr(datablock.data, 'materials'):
            for mat in datablock.data.materials:
                if mat:
                    collect_from_material(mat)
    
    elif hasattr(datablock, 'materials'):
        for mat in datablock.materials:
            if mat:
                collect_from_material(mat)
    
    if hasattr(datablock, 'material_slots'):
        for slot in datablock.material_slots:
            if slot.material:
                collect_from_material(slot.material)
    
    if isinstance(datablock, bpy.types.Speaker):
        if datablock.sound:
            dependencies['sounds'].add(datablock.sound)
    
    if hasattr(bpy.types, 'Volume') and isinstance(datablock, bpy.types.Volume):
        dependencies['volumes'].add(datablock)

    return dependencies


def collect_selected_assets_with_names(context):
    """
    Collect selected assets with their file paths AND datablock names.

    Returns a tuple (assets, active_library) where:
    - assets is a list of dicts: {'path': Path, 'name': str, 'id_type': str}
    - active_library is the Blender preferences library object (or None)
    
    This is essential for asset-level operations in multi-asset .blend files.
    """  
    assets = []
    
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
        asset_name = None
        id_type = None
        
        if hasattr(asset_file, "name"):
            asset_name = asset_file.name
        
        if hasattr(asset_file, "id_type"):
            id_type = asset_file.id_type
        elif hasattr(asset_file, "asset_data") and hasattr(asset_file.asset_data, "id_type"):
            id_type = asset_file.asset_data.id_type
        
        if hasattr(asset_file, "full_library_path") and asset_file.full_library_path:
            asset_path = Path(asset_file.full_library_path)
        elif hasattr(asset_file, "full_path") and asset_file.full_path:
            asset_path = Path(asset_file.full_path)
        elif hasattr(asset_file, "relative_path") and library_path:
            asset_path = library_path / asset_file.relative_path
        elif asset_name and library_path:
            potential_path = library_path / (asset_name if asset_name.endswith(".blend") else f"{asset_name}.blend")
            if potential_path.exists():
                asset_path = potential_path

        if asset_path and asset_path.exists() and asset_path.is_file() and asset_path.suffix.lower() == ".blend":
            try:
                if asset_path.stat().st_size > MIN_BLEND_FILE_SIZE:
                    assets.append({
                        'path': asset_path,
                        'name': asset_name,
                        'id_type': id_type
                    })
            except Exception:
                pass

    return assets, active_library


def count_assets_in_blend(blend_path):
    """
    Count how many assets exist in a .blend file.
    
    Returns a dict with asset count and list of asset info:
    {'count': int, 'assets': [{'name': str, 'type': str}, ...]}
    """
    datablock_collections = [
        'objects', 'materials', 'node_groups', 'worlds', 'collections',
        'meshes', 'curves', 'armatures', 'actions', 'brushes',
    ]
    
    result = {'count': 0, 'assets': []}
    
    try:
        with bpy.data.libraries.load(str(blend_path), link=False, assets_only=True) as (data_from, data_to):
            for collection_name in datablock_collections:
                if hasattr(data_from, collection_name):
                    source = getattr(data_from, collection_name)
                    if source:
                        for name in source:
                            result['assets'].append({
                                'name': name,
                                'type': collection_name
                            })
                            result['count'] += 1
    except Exception as e:
        debug_print(f"Error counting assets in {blend_path}: {e}")
    
    return result


def collect_selected_asset_files(context):
    """
    Collect absolute Paths to selected asset .blend files in the active Asset Browser.

    Returns a tuple (asset_paths, active_library) where active_library is the
    Blender preferences library object for the current Asset Browser context (or None).
    
    Note: For asset-level operations, use collect_selected_assets_with_names() instead.
    """
    asset_paths = []
    asset_blend_files = set()

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
            try:
                if asset_path.stat().st_size > MIN_BLEND_FILE_SIZE:
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

        for image in all_dependencies['images']:
            if image and image.source == 'FILE' and not image.packed_file:
                try:
                    packed_items['images'].append(image)
                    image.pack()
                    debug_print(f"Packed image: {image.name}")
                except Exception as e:
                    print(f"Warning: Could not pack image '{image.name}': {e}")

        for font in all_dependencies['fonts']:
            if font and not font.packed_file:
                if font.filepath and font.filepath != '<builtin>':
                    try:
                        packed_items['fonts'].append(font)
                        font.pack()
                        debug_print(f"Packed font: {font.name}")
                    except Exception as e:
                        print(f"Warning: Could not pack font '{font.name}': {e}")

        for sound in all_dependencies['sounds']:
            if sound and not sound.packed_file:
                try:
                    packed_items['sounds'].append(sound)
                    sound.pack()
                    debug_print(f"Packed sound: {sound.name}")
                except Exception as e:
                    print(f"Warning: Could not pack sound '{sound.name}': {e}")

        for clip in all_dependencies['movieclips']:
            if clip and hasattr(clip, 'packed_file') and not clip.packed_file:
                try:
                    packed_items['movieclips'].append(clip)
                    clip.pack()
                    debug_print(f"Packed movie clip: {clip.name}")
                except Exception as e:
                    print(f"Warning: Could not pack movie clip '{clip.name}': {e}")

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


def get_addon_preferences():
    """Get the addon preferences object."""
    return bpy.context.preferences.addons.get(__package__.rsplit('.', 1)[0], None)
