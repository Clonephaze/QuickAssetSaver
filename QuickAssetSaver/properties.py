"""
Properties Module - Quick Asset Saver
======================================
Defines addon preferences, property groups, and configuration management.
Handles user settings like library path, default author, and options.
"""

import bpy
from bpy.types import AddonPreferences, PropertyGroup
from bpy.props import StringProperty, BoolProperty, EnumProperty
from pathlib import Path


def get_default_library_path():
    """
    Auto-detect or create a default asset library path using Blender's API.
    Cross-platform compatible using bpy.utils.user_resource().
    
    Returns:
        str: Path to the default library folder
    """
    # Try to detect existing Blender user library
    prefs = bpy.context.preferences
    if hasattr(prefs, 'filepaths') and hasattr(prefs.filepaths, 'asset_libraries'):
        # Check if any user libraries are defined
        asset_libs = prefs.filepaths.asset_libraries
        if asset_libs and len(asset_libs) > 0:
            first_lib = asset_libs[0]
            if hasattr(first_lib, 'path') and first_lib.path:
                return first_lib.path
    
    # Fallback: Use Blender's user resource directory (cross-platform)
    # This respects Blender's configured user paths and works on all OS
    default_path = bpy.utils.user_resource('DATAFILES', path='assets', create=True)
    
    if default_path:
        print(f"Using Blender user resource path for assets: {default_path}")
        return default_path
    
    # Last resort fallback (should rarely happen)
    return str(Path.home() / "BlenderAssets")


class QuickAssetSaverPreferences(AddonPreferences):
    """
    Addon preferences for Quick Asset Saver.
    Accessible via Edit > Preferences > Add-ons > Quick Asset Saver
    """
    bl_idname = __package__
    
    asset_library_path: StringProperty(
        name="Asset Library Path",
        description="Folder where saved assets will be stored as individual .blend files",
        subtype='DIR_PATH',
        default="",
    )
    
    default_author: StringProperty(
        name="Default Author",
        description="Default author name to embed in saved asset metadata",
        default="",
    )
    
    auto_refresh: BoolProperty(
        name="Auto-Refresh Asset Browser",
        description="Automatically refresh the Asset Browser after saving an asset",
        default=True,
    )
    
    pack_images: BoolProperty(
        name="Pack Images by Default",
        description="Pack external images into the .blend file when saving assets",
        default=True,
    )
    
    def draw(self, context):
        """Draw the preferences UI."""
        layout = self.layout
        
        # Display instructions if path is not set
        if not self.asset_library_path:
            box = layout.box()
            box.label(text="Welcome to Quick Asset Saver!", icon='INFO')
            box.label(text="Please set your Asset Library Path below.")
            box.label(text="If you don't have one, we'll create 'Easy Add Assets' in your home folder.")
        
        layout.prop(self, "asset_library_path")
        
        # Button to reset to default
        row = layout.row()
        row.operator("qas.reset_library_path", text="Reset to Default Path")
        
        layout.separator()
        layout.prop(self, "default_author")
        layout.prop(self, "auto_refresh")
        layout.prop(self, "pack_images")
        
        layout.separator()
        box = layout.box()
        box.label(text="Usage:", icon='QUESTION')
        box.label(text="1. In Asset Browser (Current File), right-click an asset")
        box.label(text="2. Select 'Save to Library'")
        box.label(text="3. Configure name, catalog, and metadata")
        box.label(text="4. Click OK to save as a standalone .blend file")


class QASSaveProperties(PropertyGroup):
    """
    Property group for the save dialog.
    Holds temporary data during the asset saving process.
    """
    asset_name: StringProperty(
        name="Asset Name",
        description="Name for the saved asset file (will be sanitized)",
        default="",
    )
    
    asset_description: StringProperty(
        name="Description",
        description="Optional description for the asset metadata",
        default="",
    )
    
    asset_tags: StringProperty(
        name="Tags",
        description="Comma-separated tags for the asset",
        default="",
    )
    
    asset_author: StringProperty(
        name="Author",
        description="Author name for this asset",
        default="",
    )
    
    catalog_id: StringProperty(
        name="Catalog ID",
        description="Internal UUID for the selected catalog",
        default="",
    )
    
    conflict_resolution: EnumProperty(
        name="If File Exists",
        description="What to do if a file with the same name already exists",
        items=[
            ('INCREMENT', "Increment", "Save as Name_001.blend, etc.", 'DUPLICATE', 0),
            ('OVERWRITE', "Overwrite", "Replace the existing file", 'FILE_REFRESH', 1),
            ('CANCEL', "Cancel", "Don't save if file exists", 'CANCEL', 2),
        ],
        default='INCREMENT',
    )


def get_addon_preferences(context=None):
    """
    Get the addon preferences.
    
    Args:
        context: Blender context (optional, uses bpy.context if None)
    
    Returns:
        QuickAssetSaverPreferences: The addon preferences
    """
    if context is None:
        context = bpy.context
    
    preferences = context.preferences
    addon_prefs = preferences.addons[__package__].preferences
    
    # Initialize library path if not set
    if not addon_prefs.asset_library_path:
        addon_prefs.asset_library_path = get_default_library_path()
    
    return addon_prefs


# Registration
classes = (
    QuickAssetSaverPreferences,
    QASSaveProperties,
)


def register():
    """Register properties classes."""
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Register property group on WindowManager for dialog data
    bpy.types.WindowManager.qas_save_props = bpy.props.PointerProperty(
        type=QASSaveProperties
    )


def unregister():
    """Unregister properties classes."""
    # Remove property group
    if hasattr(bpy.types.WindowManager, 'qas_save_props'):
        del bpy.types.WindowManager.qas_save_props
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
