import time
import bpy

from ..compatibility import is_asset_browser_active
from ..properties import get_library_by_identifier


def _count_selected_assets(context):
    if hasattr(context, "selected_asset_files") and context.selected_asset_files is not None:
        return len(context.selected_asset_files)
    elif hasattr(context, "selected_assets") and context.selected_assets is not None:
        return len(context.selected_assets)
    elif hasattr(context.space_data, "files"):
        try:
            return len([f for f in context.space_data.files if getattr(f, "select", False)])
        except (AttributeError, TypeError):
            pass
    return 0


class QAM_PT_save_to_library(bpy.types.Panel):
    bl_idname = "QAM_PT_save_to_library"
    bl_label = "Save to Library"
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOL_PROPS"
    bl_order = 100

    @classmethod
    def poll(cls, context):
        if not is_asset_browser_active(context):
            return False
        asset = getattr(context, "asset", None)
        if asset is None:
            return False
        if getattr(asset, "local_id", None) is None:
            return False
        if _count_selected_assets(context) >= 2:
            return False
        return True

    def draw(self, context):
        layout = self.layout
        props = context.window_manager.qam_save_props
        asset = context.asset

        # Library dropdown
        layout.prop(props, "selected_library", text="Library")

        # Catalog dropdown row with refresh button
        # Disabled when "Copy Catalog from Current File" is on
        catalog_row = layout.row(align=True)
        catalog_row.enabled = not props.auto_create_catalog
        catalog_row.prop(props, "catalog", text="Catalog")
        catalog_row.operator("qam.refresh_catalog_list", icon="FILE_REFRESH", text="")
        row = layout.row()
        row.scale_y = 0.85
        row.prop(props, "auto_create_catalog")

        # Path preview
        if props.selected_library and props.selected_library != "NONE":
            lib = get_library_by_identifier(props.selected_library)
            if lib is not None:
                path = lib.path if hasattr(lib, "path") else str(lib)
                if len(path) > 35:
                    path_display = path[:12] + "..." + path[-20:]
                else:
                    path_display = path
                layout.label(text=path_display, icon="FILE_FOLDER")

        # Collection warning
        if asset.local_id is not None and isinstance(asset.local_id, bpy.types.Collection):
            box = layout.box()
            box.label(text="Collection previews may need", icon="INFO")
            box.label(text="regeneration after saving.")

        # Success message
        if props.show_success_message:
            if time.time() - props.success_message_time < 4.0:
                box = layout.box()
                col = box.column()
                col.alert = True
                col.label(text="Saved!", icon="CHECKMARK")
            else:
                props.show_success_message = False

        layout.separator()

        # Save button
        row = layout.row()
        row.scale_y = 1.3
        row.operator("qam.save_asset_to_library_direct", text="Copy to Asset Library", icon="EXPORT")

        # Open folder button
        row = layout.row()
        row.operator("qam.open_library_folder")


classes = (QAM_PT_save_to_library,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
