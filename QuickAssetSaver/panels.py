"""
Panels Module - Quick Asset Saver
==================================
UI integration for context menus and panels in the Asset Browser.
Adds "Save to Library" option to asset context menus when viewing Current File.
"""

import bpy
from bpy.types import Menu


def asset_browser_context_menu_draw(self, context):
    """
    Add 'Save to Library' option to the Asset Browser context menu.
    Only appears when viewing Current File assets.
    """
    layout = self.layout
    
    # Check if we're in the Asset Browser viewing Current File
    space = context.space_data
    if not space or space.type != 'FILE_BROWSER':
        return
    
    # Check if this is the asset browser and viewing "Current File"
    if not hasattr(space, 'browse_mode') or space.browse_mode != 'ASSETS':
        return
    
    # Check if we're viewing Current File (LOCAL library)
    params = space.params
    if not hasattr(params, 'asset_library_reference'):
        return
    
    asset_lib_ref = params.asset_library_reference
    
    # In Blender 5.0+, LOCAL or 'Current File' indicates current blend file
    is_current_file = (asset_lib_ref == 'LOCAL' or 
                       asset_lib_ref == 'CURRENT' or
                       getattr(params, 'asset_library_ref', None) == 'LOCAL')
    
    if not is_current_file:
        return
    
    # Check if an asset is selected
    if not context.asset:
        return
    
    # Add separator and our operator
    layout.separator()
    layout.operator("qas.save_asset_to_library", icon='EXPORT')


def asset_browser_header_draw(self, context):
    """
    Optional: Add a button to the Asset Browser header.
    Only visible when viewing Current File.
    """
    layout = self.layout
    space = context.space_data
    
    if not space or space.type != 'FILE_BROWSER':
        return
    
    if not hasattr(space, 'browse_mode') or space.browse_mode != 'ASSETS':
        return
    
    params = space.params
    if not hasattr(params, 'asset_library_reference'):
        return
    
    asset_lib_ref = params.asset_library_reference
    is_current_file = (asset_lib_ref == 'LOCAL' or 
                       asset_lib_ref == 'CURRENT' or
                       getattr(params, 'asset_library_ref', None) == 'LOCAL')
    
    if is_current_file and context.asset:
        layout.separator()
        layout.operator("qas.save_asset_to_library", text="", icon='EXPORT')


class QAS_PT_asset_tools_panel(bpy.types.Panel):
    """
    Optional side panel in Asset Browser for Quick Asset Saver tools.
    Provides additional UI for managing asset saving workflow.
    """
    bl_label = "Quick Asset Saver"
    bl_idname = "QAS_PT_asset_tools"
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOLS'
    bl_category = "Assets"
    
    @classmethod
    def poll(cls, context):
        """Only show in Asset Browser when viewing Current File."""
        space = context.space_data
        if not space or space.type != 'FILE_BROWSER':
            return False
        
        if not hasattr(space, 'browse_mode') or space.browse_mode != 'ASSETS':
            return False
        
        params = space.params
        if not hasattr(params, 'asset_library_reference'):
            return False
        
        asset_lib_ref = params.asset_library_reference
        is_current_file = (asset_lib_ref == 'LOCAL' or 
                           asset_lib_ref == 'CURRENT' or
                           getattr(params, 'asset_library_ref', None) == 'LOCAL')
        
        return is_current_file
    
    def draw(self, context):
        """Draw the panel UI."""
        layout = self.layout
        
        from . import properties
        prefs = properties.get_addon_preferences(context)
        
        # Library path info
        box = layout.box()
        box.label(text="Target Library:", icon='ASSET_MANAGER')
        
        if prefs.asset_library_path:
            # Show path (truncated if too long)
            path_str = str(prefs.asset_library_path)
            if len(path_str) > 30:
                path_str = "..." + path_str[-27:]
            box.label(text=path_str, icon='FILE_FOLDER')
        else:
            box.label(text="Not set", icon='ERROR')
        
        box.operator("qas.open_library_folder", icon='FILEBROWSER')
        
        layout.separator()
        
        # Main action
        if context.asset:
            layout.label(text="Selected Asset:", icon='ASSET_MANAGER')
            asset_name = getattr(context.asset, 'name', 'Unknown')
            layout.label(text=f"  {asset_name}")
            layout.separator()
            layout.operator("qas.save_asset_to_library", icon='EXPORT')
        else:
            box = layout.box()
            box.label(text="No asset selected", icon='INFO')
            box.label(text="Right-click an asset")
            box.label(text="to save it to your library")


# Registration
classes = (
    QAS_PT_asset_tools_panel,
)


def register():
    """Register UI elements and menu items."""
    for cls in classes:
        bpy.utils.register_class(cls)
    
    # Add to Asset Browser context menu
    # The context menu for assets is ASSETBROWSER_MT_context_menu in Blender 5.0+
    # We'll try multiple possible menu names for compatibility
    menus_to_try = [
        'ASSETBROWSER_MT_context_menu',
        'FILEBROWSER_MT_context_menu',
        'ASSETBROWSER_MT_asset',
    ]
    
    for menu_name in menus_to_try:
        if hasattr(bpy.types, menu_name):
            menu_class = getattr(bpy.types, menu_name)
            menu_class.append(asset_browser_context_menu_draw)
            print(f"Quick Asset Saver: Added to {menu_name}")
            break
    
    # Optional: Add to header
    # bpy.types.FILEBROWSER_HT_header.append(asset_browser_header_draw)


def unregister():
    """Unregister UI elements and menu items."""
    # Remove from context menu
    menus_to_try = [
        'ASSETBROWSER_MT_context_menu',
        'FILEBROWSER_MT_context_menu',
        'ASSETBROWSER_MT_asset',
    ]
    
    for menu_name in menus_to_try:
        if hasattr(bpy.types, menu_name):
            menu_class = getattr(bpy.types, menu_name)
            try:
                menu_class.remove(asset_browser_context_menu_draw)
            except:
                pass
    
    # Remove from header if added
    # try:
    #     bpy.types.FILEBROWSER_HT_header.remove(asset_browser_header_draw)
    # except:
    #     pass
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
