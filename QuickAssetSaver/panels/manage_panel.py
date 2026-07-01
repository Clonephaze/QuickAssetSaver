import bpy
from ..compatibility import is_asset_browser_active, is_protected_library


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


class QAM_UL_metadata_tags(bpy.types.UIList):
    bl_idname = "QAM_UL_metadata_tags"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.prop(item, "name", text="", emboss=False, icon='NONE')


class QAM_OT_tag_add(bpy.types.Operator):
    bl_idname = "qam.tag_add"
    bl_label = "Add Tag"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hasattr(context.window_manager, "qam_metadata_edit")

    def execute(self, context):
        meta = context.window_manager.qam_metadata_edit
        tag = meta.edit_tags.add()
        tag.name = "Tag"
        meta.active_tag_index = len(meta.edit_tags) - 1
        return {'FINISHED'}


class QAM_OT_tag_remove(bpy.types.Operator):
    bl_idname = "qam.tag_remove"
    bl_label = "Remove Tag"
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        if not hasattr(wm, "qam_metadata_edit"):
            return False
        meta = wm.qam_metadata_edit
        return len(meta.edit_tags) > 0 and meta.active_tag_index >= 0

    def execute(self, context):
        meta = context.window_manager.qam_metadata_edit
        if meta.active_tag_index < len(meta.edit_tags):
            meta.edit_tags.remove(meta.active_tag_index)
            if meta.active_tag_index >= len(meta.edit_tags) and meta.active_tag_index > 0:
                meta.active_tag_index -= 1
        return {'FINISHED'}


class QAM_PT_asset_actions(bpy.types.Panel):
    bl_idname = "QAM_PT_asset_actions"
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Actions"
    bl_order = 60

    @classmethod
    def poll(cls, context):
        if not is_asset_browser_active(context):
            return False
        if not context.asset:
            return False
        if context.asset.local_id is not None:
            return False
        if _count_selected_assets(context) >= 2:
            return False
        return True

    def draw(self, context):
        from .. import panels as panels_pkg
        panels_pkg._check_and_exit_edit_mode(context)

        layout = self.layout
        layout.enabled = not is_protected_library(context)

        wm = context.window_manager
        manage = getattr(wm, "qam_manage_props", None)
        meta = getattr(wm, "qam_metadata_edit", None)

        # Edit mode toggle
        edit_row = layout.row()
        edit_row.scale_y = 1.3
        if panels_pkg._edit_mode_active:
            edit_row.operator(
                "qam.toggle_edit_mode",
                text="Cancel",
                icon="PANEL_CLOSE",
                depress=True,
            )
            apply_row = layout.row()
            apply_row.scale_y = 1.3
            apply_row.enabled = meta.has_changes() if meta else False
            apply_row.operator(
                "qam.apply_metadata_changes",
                text="Apply Changes",
                icon="CHECKMARK",
            )
        else:
            edit_row.operator(
                "qam.toggle_edit_mode",
                text="Edit Metadata/Tags",
                icon="GREASEPENCIL",
            )

        # Move section
        layout.separator()
        layout.label(text="Move", icon="ASSET_MANAGER")
        box = layout.box()
        if manage:
            box.prop(manage, "move_target_library", text="Library")
            box.prop(manage, "move_target_catalog", text="Catalog")
        move_row = box.row()
        move_row.scale_y = 1.2
        move_row.operator(
            "qam.move_selected_to_library",
            text="Move Asset",
            icon="EXPORT",
        )

        # Delete section
        layout.separator()
        delete_row = layout.row()
        delete_row.scale_y = 1.2
        delete_row.operator(
            "qam.delete_selected_assets",
            text="Remove Asset from Library",
            icon="TRASH",
        )


classes = (
    QAM_UL_metadata_tags,
    QAM_OT_tag_add,
    QAM_OT_tag_remove,
    QAM_PT_asset_actions,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
