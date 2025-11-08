"""
Panels Module - Quick Asset Saver
==================================
UI integration for panels in the Asset Browser.
Provides a side panel for saving assets to libraries.
"""

import bpy


class QAS_PT_asset_tools_panel(bpy.types.Panel):
    """Side panel in Asset Browser for Quick Asset Saver."""

    bl_label = "Quick Asset Saver"
    bl_idname = "QAS_PT_asset_tools"
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOLS"
    bl_category = "Assets"

    @classmethod
    def poll(cls, context):
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
        layout = self.layout

        from . import properties
        from .operators import sanitize_name

        prefs = properties.get_addon_preferences(context)
        wm = context.window_manager
        props = wm.qas_save_props

        box = layout.box()
        box.label(text="Target Library:", icon="ASSET_MANAGER")
        box.prop(props, "selected_library", text="")
        box.label(text="Add other libraries in the File Paths tab in Blender Preferences.")
        
        if props.selected_library and props.selected_library != 'NONE':
            row = box.row()
            row.label(text=f"Path: {props.selected_library}", icon="FILE_FOLDER")
            row.operator("qas.open_library_folder", text="", icon="FILEBROWSER")

        layout.separator()

        if context.asset:
            asset_name = getattr(context.asset, "name", "Unknown")
            
            if props.last_asset_name != asset_name:
                props.last_asset_name = asset_name
                props.asset_display_name = asset_name
                props.asset_author = prefs.default_author
                props.asset_description = prefs.default_description
                props.asset_license = prefs.default_license
                props.asset_copyright = prefs.default_copyright
                
            if props.asset_display_name:
                props.asset_file_name = sanitize_name(props.asset_display_name)
            
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
            
            # Show target path preview
            if props.selected_library and props.selected_library != 'NONE' and props.asset_file_name:
                from pathlib import Path
                from .operators import get_catalog_path_from_uuid, build_asset_filename
                
                preview_box = layout.box()
                preview_box.label(text="Target Path:", icon="FILE_FOLDER")
                
                # Build the preview path
                library_path = Path(props.selected_library)
                target_path = library_path
                
                # Add catalog subfolder if enabled
                if prefs.use_catalog_subfolders and props.catalog and props.catalog != "UNASSIGNED":
                    catalog_path = get_catalog_path_from_uuid(props.selected_library, props.catalog)
                    if catalog_path:
                        path_parts = catalog_path.split("/")
                        sanitized_parts = [sanitize_name(part, max_length=64) for part in path_parts if part]
                        for part in sanitized_parts:
                            target_path = target_path / part
                
                # Build the final filename with naming conventions
                final_filename = build_asset_filename(props.asset_file_name, prefs)
                full_path = target_path / f"{final_filename}.blend"
                
                # Display relative path if it fits, otherwise show just the filename with ellipsis
                try:
                    relative_path = full_path.relative_to(library_path)
                    path_str = str(relative_path)
                except ValueError:
                    path_str = full_path.name
                
                # Split long paths across multiple lines
                if len(path_str) > 40:
                    col = preview_box.column(align=True)
                    col.scale_y = 0.8
                    # Show library name
                    col.label(text=f"  {library_path.name}/", icon="BLANK1")
                    # Show subdirectories
                    if target_path != library_path:
                        try:
                            subpath = target_path.relative_to(library_path)
                            col.label(text=f"    {subpath}/", icon="BLANK1")
                        except ValueError:
                            pass
                    # Show filename
                    col.label(text=f"    {final_filename}.blend", icon="BLANK1")
                else:
                    preview_box.label(text=f"  {path_str}", icon="BLANK1")
            
            layout.separator()
            layout.operator("qas.save_asset_to_library_direct", text="Save to Asset Library", icon="EXPORT")
        else:
            box = layout.box()
            box.label(text="No asset selected", icon="INFO")
            box.label(text="Select an asset")
            box.label(text="to save it to your library")


classes = (QAS_PT_asset_tools_panel,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
