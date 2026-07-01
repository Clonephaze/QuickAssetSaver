import time

import bpy

from ..compatibility import is_asset_browser_active
from ..constants import LARGE_SELECTION_WARNING_THRESHOLD


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


class QAM_PT_bulk_operations(bpy.types.Panel):
    bl_idname = "QAM_PT_bulk_operations"
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Bulk Operations"
    bl_order = 1

    @classmethod
    def poll(cls, context):
        if not is_asset_browser_active(context):
            return False
        return _count_selected_assets(context) >= 2

    def draw(self, context):
        layout = self.layout
        wm = context.window_manager

        selected_count = _count_selected_assets(context)

        # Header
        layout.label(text=f"{selected_count} Assets Selected", icon="ASSET_MANAGER")

        # Large selection warning
        if selected_count >= LARGE_SELECTION_WARNING_THRESHOLD:
            box = layout.box()
            box.label(text=f"Large selection ({selected_count} assets)", icon="ERROR")
            box.label(text="This may take a while.")

        layout.separator()

        # Move box
        move_box = layout.box()
        move_box.label(text="Move Assets", icon="EXPORT")

        manage_props = getattr(wm, "qam_manage_props", None)
        if manage_props is not None:
            move_box.prop(manage_props, "move_target_library", text="Library")
            move_box.prop(manage_props, "move_target_catalog", text="Catalog")

        move_row = move_box.row()
        move_row.scale_y = 1.2
        move_row.operator(
            "qam.move_selected_to_library",
            text=f"Move {selected_count} Assets",
            icon="EXPORT",
        )

        layout.separator()

        # Bundle box
        bundle_box = layout.box()
        bundle_box.label(text="Bundle Assets", icon="PACKAGE")

        bundler_props = getattr(wm, "qam_bundler_props", None)
        if bundler_props is not None:
            bundle_box.prop(bundler_props, "output_name", text="Name")
            bundle_box.prop(bundler_props, "save_path", text="Path")
            # Blender deselects assets when the file picker opens — warn the user
            hint = bundle_box.row()
            hint.scale_y = 0.75
            hint.label(text="Tip: selecting a path deselects assets", icon="INFO")
            bundle_box.prop(bundler_props, "duplicate_mode", text="Duplicates")
            bundle_box.prop(bundler_props, "copy_catalog")

            if bundler_props.show_success_message:
                if time.time() - bundler_props.success_message_time < 4.0:
                    success_box = bundle_box.box()
                    success_box.label(text="Bundle saved!", icon="CHECKMARK")
                else:
                    bundler_props.show_success_message = False

        bundle_row = bundle_box.row()
        bundle_row.scale_y = 1.2
        bundle_row.operator(
            "qam.bundle_assets",
            text=f"Bundle {selected_count} Assets",
            icon="PACKAGE",
        )


classes = (QAM_PT_bulk_operations,)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
