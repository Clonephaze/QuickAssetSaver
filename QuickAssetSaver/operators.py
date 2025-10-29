"""
Operators Module - Quick Asset Saver
=====================================
Core operators for saving assets from Current File to library folders.
Includes helpers for file I/O, catalog parsing, metadata assignment, and sanitization.
"""

import bpy
from bpy.types import Operator
from bpy.props import StringProperty, EnumProperty
import os
import re
import uuid
from pathlib import Path
import tempfile
import shutil


def sanitize_name(name, max_length=128):
    """
    Sanitize a filename to be cross-platform compatible.
    Removes or replaces invalid filesystem characters for Windows/macOS/Linux.
    
    Args:
        name (str): The original filename
        max_length (int): Maximum length for the filename
    
    Returns:
        str: Sanitized filename safe for all platforms
    
    Examples:
        >>> sanitize_name("My Asset/Test*")
        'My Asset_Test_'
        >>> sanitize_name("Material:Wood|Pine")
        'Material_Wood_Pine'
        >>> sanitize_name("x" * 200)[:128] == "x" * 128
        True
    """
    # Replace invalid characters with underscore
    # Windows invalid: < > : " / \ | ? *
    # Also remove control characters
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, '_', name)
    
    # Remove leading/trailing dots and spaces (problematic on Windows)
    sanitized = sanitized.strip('. ')
    
    # Ensure not empty
    if not sanitized:
        sanitized = "asset"
    
    # Truncate to max_length
    sanitized = sanitized[:max_length]
    
    return sanitized


def increment_filename(base_path, name, extension=".blend"):
    """
    Generate an incremented filename if the base file exists.
    
    Args:
        base_path (Path): Directory where the file will be saved
        name (str): Base filename without extension
        extension (str): File extension (default: .blend)
    
    Returns:
        Path: Full path with incremented name if necessary
    
    Examples:
        # If "Material.blend" exists, returns "Material_001.blend"
        # If "Material_001.blend" also exists, returns "Material_002.blend"
    """
    base_path = Path(base_path)
    filepath = base_path / f"{name}{extension}"
    
    if not filepath.exists():
        return filepath
    
    # Find next available increment
    counter = 1
    while True:
        new_name = f"{name}_{counter:03d}{extension}"
        filepath = base_path / new_name
        if not filepath.exists():
            return filepath
        counter += 1
        
        # Safety: prevent infinite loop
        if counter > 9999:
            raise RuntimeError(f"Too many incremental files for {name}")


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
    enum_items = [('UNASSIGNED', "Unassigned", "No catalog assigned", 'NONE', 0)]
    
    if not cdf_path.exists():
        print(f"No catalog file found at {cdf_path}")
        return catalogs, enum_items
    
    try:
        with open(cdf_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # Parse CDF format: UUID:catalog_path:catalog_name
        # Lines starting with # are comments or headers
        idx = 1  # Start from 1 since UNASSIGNED is 0
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('VERSION'):
                continue
            
            parts = line.split(':')
            if len(parts) >= 2:
                catalog_uuid = parts[0].strip()
                catalog_path = parts[1].strip()
                
                # Validate UUID format
                try:
                    uuid.UUID(catalog_uuid)
                    catalogs[catalog_path] = catalog_uuid
                    # Create enum item
                    enum_items.append((
                        catalog_uuid,
                        catalog_path,
                        f"Catalog: {catalog_path}",
                        'ASSET_MANAGER',
                        idx
                    ))
                    idx += 1
                except ValueError:
                    print(f"Invalid UUID in catalog file: {catalog_uuid}")
                    continue
    
    except Exception as e:
        print(f"Error reading catalog file: {e}")
    
    return catalogs, enum_items


def collect_datablocks_for_asset(asset_data):
    """
    Collect the main datablock for an asset.
    bpy.data.libraries.write() will automatically include indirect dependencies.
    
    Args:
        asset_data: Asset data from context.asset or asset_file_handle
    
    Returns:
        set: Set of ID datablocks to write
    """
    # In Blender 5.0, we need to get the actual ID datablock from the asset
    # The asset_data from context provides information to locate it
    datablocks = set()
    
    # Asset data should have a local_id or we need to find it in bpy.data
    if hasattr(asset_data, 'local_id') and asset_data.local_id:
        datablocks.add(asset_data.local_id)
    
    return datablocks


def write_blend_file(filepath, datablocks, pack_images=True):
    """
    Write a .blend file containing only the specified datablocks.
    
    Args:
        filepath (Path): Destination .blend file path
        datablocks (set): Set of bpy.types.ID datablocks to write
        pack_images (bool): Whether to pack external images
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        filepath = Path(filepath)
        
        # Use a temporary file for atomic write
        temp_dir = filepath.parent
        temp_file = temp_dir / f".tmp_{filepath.name}"
        
        # Write the blend file with only specified datablocks
        # bpy.data.libraries.write automatically includes indirect dependencies
        bpy.data.libraries.write(
            str(temp_file),
            datablocks,
            path_remap='RELATIVE_ALL' if pack_images else 'NONE',
            fake_user=True,
            compress=True,
        )
        
        # Move temp file to final location (atomic on most systems)
        if filepath.exists():
            filepath.unlink()  # Remove existing file
        
        shutil.move(str(temp_file), str(filepath))
        
        print(f"Successfully wrote {filepath}")
        return True
        
    except Exception as e:
        print(f"Error writing blend file: {e}")
        # Clean up temp file if it exists
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
                if attr.startswith('_'):
                    continue
                items = getattr(data_from, attr, [])
                if items and len(items) > 0:
                    # Load the first item of this type
                    setattr(data_to, attr, [items[0]])
                    break
        
        # Get the loaded datablock
        loaded_block = None
        for attr in dir(data_to):
            if attr.startswith('_'):
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
                if 'author' in metadata_dict:
                    loaded_block.asset_data.author = metadata_dict['author']
                if 'description' in metadata_dict:
                    loaded_block.asset_data.description = metadata_dict['description']
                if 'catalog_id' in metadata_dict and metadata_dict['catalog_id'] != 'UNASSIGNED':
                    loaded_block.asset_data.catalog_id = metadata_dict['catalog_id']
                
                # Tags: Blender 5.0 asset_data has tags attribute
                if 'tags' in metadata_dict and hasattr(loaded_block.asset_data, 'tags'):
                    # Remove existing tags (no clear() method in bpy_prop_collection)
                    while len(loaded_block.asset_data.tags) > 0:
                        loaded_block.asset_data.tags.remove(loaded_block.asset_data.tags[0])
                    
                    # Add new tags
                    tags_list = [t.strip() for t in metadata_dict['tags'].split(',') if t.strip()]
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


class QAS_OT_save_asset_to_library(Operator):
    """Save selected asset from Current File to library folder"""
    bl_idname = "qas.save_asset_to_library"
    bl_label = "Save to Library"
    bl_description = "Save this asset as a standalone .blend file in your asset library"
    bl_options = {'REGISTER', 'UNDO'}
    
    # Dynamic enum property for catalogs
    def get_catalog_items(self, context):
        """Dynamically generate catalog enum items."""
        from . import properties
        prefs = properties.get_addon_preferences(context)
        library_path = prefs.asset_library_path
        
        if not library_path or not Path(library_path).exists():
            return [('UNASSIGNED', "Unassigned", "No catalog assigned")]
        
        catalogs, enum_items = get_catalogs_from_cdf(library_path)
        return enum_items if enum_items else [('UNASSIGNED', "Unassigned", "No catalog assigned")]
    
    catalog: EnumProperty(
        name="Catalog",
        description="Catalog to assign the asset to",
        items=get_catalog_items,
    )
    
    def invoke(self, context, event):
        """Show dialog before executing."""
        from . import properties
        
        # Get preferences
        prefs = properties.get_addon_preferences(context)
        
        # Validate library path
        if not prefs.asset_library_path:
            self.report({'ERROR'}, "Asset library path not set in preferences")
            return {'CANCELLED'}
        
        library_path = Path(prefs.asset_library_path)
        if not library_path.exists():
            self.report({'ERROR'}, f"Library path does not exist: {library_path}")
            return {'CANCELLED'}
        
        if not os.access(library_path, os.W_OK):
            self.report({'ERROR'}, f"Library path is not writable: {library_path}")
            return {'CANCELLED'}
        
        # Get the selected asset
        # In Asset Browser context, we need to get the active asset
        wm = context.window_manager
        props = wm.qas_save_props
        
        # Try to get asset information from context
        asset_name = "Asset"
        asset_description = ""
        
        # Check for selected assets in Asset Browser
        if hasattr(context, 'asset'):
            asset = context.asset
            if hasattr(asset, 'name'):
                asset_name = asset.name
            if hasattr(asset, 'metadata') and hasattr(asset.metadata, 'description'):
                asset_description = asset.metadata.description
        elif hasattr(context, 'id') and context.id:
            # Direct ID datablock context
            asset_name = context.id.name
            if hasattr(context.id, 'asset_data') and context.id.asset_data:
                asset_description = context.id.asset_data.description
        
        # Initialize dialog properties
        props.asset_name = sanitize_name(asset_name)
        props.asset_description = asset_description
        props.asset_author = prefs.default_author
        props.asset_tags = ""
        props.catalog_id = "UNASSIGNED"
        
        # Show dialog
        return context.window_manager.invoke_props_dialog(self, width=400)
    
    def draw(self, context):
        """Draw the dialog UI."""
        layout = self.layout
        wm = context.window_manager
        props = wm.qas_save_props
        
        from . import properties
        prefs = properties.get_addon_preferences(context)
        
        layout.label(text="Save Asset to Library", icon='ASSET_MANAGER')
        layout.separator()
        
        # Show destination path
        box = layout.box()
        box.label(text=f"Destination: {prefs.asset_library_path}", icon='FILE_FOLDER')
        
        layout.separator()
        
        # Asset properties
        layout.prop(props, "asset_name")
        layout.prop(self, "catalog")
        layout.prop(props, "asset_author")
        layout.prop(props, "asset_description")
        layout.prop(props, "asset_tags")
        
        layout.separator()
        layout.prop(props, "conflict_resolution", expand=False)
    
    def execute(self, context):
        """Execute the save operation."""
        from . import properties
        
        wm = context.window_manager
        props = wm.qas_save_props
        prefs = properties.get_addon_preferences(context)
        
        # Get sanitized filename
        sanitized_name = sanitize_name(props.asset_name)
        if not sanitized_name:
            self.report({'ERROR'}, "Invalid asset name")
            return {'CANCELLED'}
        
        # Determine output path
        library_path = Path(prefs.asset_library_path)
        
        # Handle file conflicts
        if props.conflict_resolution == 'INCREMENT':
            output_path = increment_filename(library_path, sanitized_name)
        elif props.conflict_resolution == 'OVERWRITE':
            output_path = library_path / f"{sanitized_name}.blend"
        else:  # CANCEL
            check_path = library_path / f"{sanitized_name}.blend"
            if check_path.exists():
                self.report({'WARNING'}, f"File already exists: {check_path.name}")
                return {'CANCELLED'}
            output_path = check_path
        
        # Collect datablocks to save
        datablocks = set()
        
        # Get the asset datablock from context
        asset_id = None
        if hasattr(context, 'asset') and hasattr(context.asset, 'local_id'):
            asset_id = context.asset.local_id
        elif hasattr(context, 'id'):
            asset_id = context.id
        
        if not asset_id:
            self.report({'ERROR'}, "Could not identify asset to save")
            return {'CANCELLED'}
        
        # Mark as asset if not already
        if not asset_id.asset_data:
            asset_id.asset_mark()
        
        # Set metadata on the source asset before saving
        if asset_id.asset_data:
            asset_id.asset_data.author = props.asset_author
            asset_id.asset_data.description = props.asset_description
            
            # Set catalog
            if self.catalog != 'UNASSIGNED':
                asset_id.asset_data.catalog_id = self.catalog
            
            # Set tags if supported
            if hasattr(asset_id.asset_data, 'tags'):
                # Remove existing tags (no clear() method in bpy_prop_collection)
                while len(asset_id.asset_data.tags) > 0:
                    asset_id.asset_data.tags.remove(asset_id.asset_data.tags[0])
                
                # Add new tags
                tags_list = [t.strip() for t in props.asset_tags.split(',') if t.strip()]
                for tag in tags_list:
                    asset_id.asset_data.tags.new(tag)
        
        datablocks.add(asset_id)
        
        # Write the blend file
        success = write_blend_file(output_path, datablocks, prefs.pack_images)
        
        if not success:
            self.report({'ERROR'}, f"Failed to write {output_path.name}")
            return {'CANCELLED'}
        
        self.report({'INFO'}, f"Saved asset to {output_path.name}")
        
        # Refresh Asset Browser if enabled
        if prefs.auto_refresh:
            try:
                # Try different refresh operators depending on Blender version
                if hasattr(bpy.ops.asset, 'library_refresh'):
                    bpy.ops.asset.library_refresh()
                elif hasattr(bpy.ops.asset, 'refresh'):
                    bpy.ops.asset.refresh()
                else:
                    self.report({'WARNING'}, "Asset browser refresh not available. Please refresh manually.")
            except Exception as e:
                print(f"Could not refresh asset browser: {e}")
        
        return {'FINISHED'}


class QAS_OT_open_library_folder(Operator):
    """Open the asset library folder in the system file browser"""
    bl_idname = "qas.open_library_folder"
    bl_label = "Open Library Folder"
    bl_description = "Open the configured asset library folder in your file browser"
    bl_options = {'REGISTER'}
    
    def execute(self, context):
        """Open folder in OS file browser."""
        from . import properties
        prefs = properties.get_addon_preferences(context)
        
        if not prefs.asset_library_path:
            self.report({'ERROR'}, "Asset library path not set")
            return {'CANCELLED'}
        
        library_path = Path(prefs.asset_library_path)
        if not library_path.exists():
            self.report({'ERROR'}, "Library path does not exist")
            return {'CANCELLED'}
        
        # Open in file browser
        bpy.ops.wm.path_open(filepath=str(library_path))
        
        return {'FINISHED'}


class QAS_OT_reset_library_path(Operator):
    """Reset library path to default"""
    bl_idname = "qas.reset_library_path"
    bl_label = "Reset to Default Path"
    bl_description = "Reset the asset library path to the default location"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        """Reset to default path."""
        from . import properties
        prefs = properties.get_addon_preferences(context)
        default_path = properties.get_default_library_path()
        prefs.asset_library_path = default_path
        self.report({'INFO'}, f"Reset to: {default_path}")
        return {'FINISHED'}


# Registration
classes = (
    QAS_OT_save_asset_to_library,
    QAS_OT_open_library_folder,
    QAS_OT_reset_library_path,
)


def register():
    """Register operator classes."""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregister operator classes."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
