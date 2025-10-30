"""
Panels Module - Quick Asset Saver
==================================
UI integration for panels in the Asset Browser.
Provides a side panel for saving assets to libraries.
"""

import bpy


class QAS_PT_asset_tools_panel(bpy.types.Panel):
    """
    Optional side panel in Asset Browser for Quick Asset Saver tools.
    Provides additional UI for managing asset saving workflow.
    """

    bl_label = "Quick Asset Saver"
    bl_idname = "QAS_PT_asset_tools"
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOLS"
    bl_category = "Assets"

    @classmethod
    def poll(cls, context):
        """Only show in Asset Browser when viewing Current File."""
        space = context.space_data
        if not space or space.type != "FILE_BROWSER":
            return False

        if not hasattr(space, "browse_mode") or space.browse_mode != "ASSETS":
            return False

        params = space.params
        if not hasattr(params, "asset_library_reference"):
            return False

        asset_lib_ref = params.asset_library_reference
        is_current_file = (
            asset_lib_ref == "LOCAL"
            or asset_lib_ref == "CURRENT"
            or getattr(params, "asset_library_ref", None) == "LOCAL"
        )

        return is_current_file

    def draw(self, context):
        """Draw the panel UI."""
        layout = self.layout

        from . import properties
        from .operators import sanitize_name

        prefs = properties.get_addon_preferences(context)
        wm = context.window_manager
        props = wm.qas_save_props

        # Library selection dropdown
        box = layout.box()
        box.label(text="Target Library:", icon="ASSET_MANAGER")
        box.prop(props, "selected_library", text="")
        box.label(
            text="Add other libraries in the File Paths tab in Blender Preferences."
        )
        
        # Show path of selected library as helper text
        if props.selected_library and props.selected_library != 'NONE':
            row = box.row()
            row.label(text=f"Path: {props.selected_library}", icon="FILE_FOLDER")
            row.operator("qas.open_library_folder", text="", icon="FILEBROWSER")

        layout.separator()

        # Main action - show options if asset is selected
        if context.asset:
            # Auto-populate properties only when asset selection changes
            asset_name = getattr(context.asset, "name", "Unknown")
            
            # Only update if this is a different asset than before
            if props.last_asset_name != asset_name:
                props.last_asset_name = asset_name
                props.asset_display_name = asset_name
                props.asset_author = prefs.default_author
                props.asset_description = prefs.default_description
                props.asset_license = prefs.default_license
                props.asset_copyright = prefs.default_copyright
                
            # Always update file name based on display name
            if props.asset_display_name:
                props.asset_file_name = sanitize_name(props.asset_display_name)
            
            # Asset save options
            outer_box = layout.box()
            outer_box.label(text="Selected Asset:", icon="ASSET_MANAGER")
            outer_box.label(text=f"  {asset_name}")
            
            inner_box = outer_box.box()
            inner_box.label(text="Save Options:", icon="SETTINGS")
            
            inner_box.prop(props, "asset_display_name")
            inner_box.prop(props, "catalog")
            inner_box.prop(props, "asset_author")
            inner_box.prop(props, "asset_description")
            inner_box.prop(props, "asset_license")
            inner_box.prop(props, "asset_copyright")
            inner_box.prop(props, "asset_tags")
            inner_box.prop(props, "conflict_resolution")
            
            layout.separator()
            layout.operator("qas.save_asset_to_library_direct", text="Save to Asset Library", icon="EXPORT")
        else:
            box = layout.box()
            box.label(text="No asset selected", icon="INFO")
            box.label(text="Select an asset")
            box.label(text="to save it to your library")


# Registration
classes = (QAS_PT_asset_tools_panel,)


def register():
    """Register UI elements."""
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    """Unregister UI elements."""
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
