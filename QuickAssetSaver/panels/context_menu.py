import bpy


def draw_asset_context_menu(self, context):
    if not hasattr(context, "space_data") or context.space_data.type != "FILE_BROWSER":
        return
    if getattr(context.space_data, "browse_mode", None) != "ASSETS":
        return

    params = getattr(context.space_data, "params", None)
    if not params:
        return

    asset_lib_ref = getattr(params, "asset_library_reference", None)
    if not asset_lib_ref:
        asset_lib_ref = getattr(params, "asset_library_ref", None)

    is_current_file = asset_lib_ref in ("LOCAL", "CURRENT") or asset_lib_ref is None

    if is_current_file:
        return

    layout = self.layout
    layout.separator()
    layout.operator("qam.swap_selected_with_asset", text="Replace Selected Objects", icon="FILE_REFRESH")
    layout.operator("qam.delete_selected_assets", text="Remove Asset from Library", icon="TRASH")


def register():
    bpy.types.ASSETBROWSER_MT_context_menu.append(draw_asset_context_menu)


def unregister():
    bpy.types.ASSETBROWSER_MT_context_menu.remove(draw_asset_context_menu)
