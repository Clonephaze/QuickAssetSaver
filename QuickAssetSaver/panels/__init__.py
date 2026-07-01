"""
Panels package for Quick Asset Manager.

Manages the draw override for metadata edit mode. The native
ASSETBROWSER_PT_metadata and ASSETBROWSER_PT_metadata_tags panels
are temporarily replaced with editable versions when edit mode is active.

NOTE: Any other addon that has appended to ASSETBROWSER_PT_metadata will
have its appended content hidden during edit mode. This is a known,
accepted tradeoff. The native panels are always fully restored on exit.
"""

import bpy

from . import bulk_panel, context_menu, manage_panel, save_panel

# ============================================================================
# MODULE-LEVEL STATE
# Module-level storage for draw refs and edit mode flags.
# These hold function objects and primitive values — module-level is correct.
# ============================================================================

_original_metadata_draw = None
_original_tags_draw = None
_edit_mode_active = False
_edit_mode_asset_key = ""


# ============================================================================
# HELPERS
# ============================================================================

def _get_asset_source_path(context):
    """Get the source .blend file path for the active asset."""
    from pathlib import Path

    asset = getattr(context, "asset", None)
    if not asset:
        return None

    def _extract(full_path_str):
        if not full_path_str:
            return None
        idx = full_path_str.lower().find('.blend')
        if idx != -1:
            return Path(full_path_str[:idx + 6])
        return None

    if hasattr(asset, "full_path") and asset.full_path:
        p = _extract(asset.full_path)
        if p:
            return p

    if hasattr(asset, "full_library_path") and asset.full_library_path:
        p = _extract(asset.full_library_path)
        if p:
            return p

    return None


def _check_and_exit_edit_mode(context) -> bool:
    """Check if the selected asset changed; exit edit mode if so.
    Called from manage_panel.draw() on every redraw."""
    global _edit_mode_asset_key

    if not _edit_mode_active:
        return False

    asset = getattr(context, "asset", None)
    if not asset:
        _exit_edit_mode()
        return True

    source_path = _get_asset_source_path(context)
    current_key = f"{source_path}:{asset.name}" if source_path else asset.name

    if current_key != _edit_mode_asset_key:
        _exit_edit_mode()
        return True

    return False


# ============================================================================
# DRAW OVERRIDE FUNCTIONS
# Defined here so both enter_edit_mode and _enter_edit_mode can reference them.
# ============================================================================

def _draw_metadata_override(self, context):
    """Override for ASSETBROWSER_PT_metadata.draw() during edit mode."""
    layout = self.layout

    asset = getattr(context, "asset", None)
    if not asset:
        layout.label(text="No asset selected")
        return

    wm = context.window_manager
    meta = getattr(wm, "qam_metadata_edit", None)

    if not meta:
        layout.label(text="Metadata editing unavailable")
        return

    source_path = _get_asset_source_path(context)
    current_key = f"{source_path}:{asset.name}" if source_path else asset.name
    stored_key = f"{meta.source_file}:{meta.asset_name}"

    if current_key != stored_key:
        meta.sync_from_asset(asset, source_path)

    layout.separator(factor=0.5)
    layout.prop(meta, "edit_name", text="Name")

    col = layout.column(align=True)
    col.enabled = False
    col.label(text="Source")
    if source_path:
        path_str = str(source_path)
        if len(path_str) > 40:
            path_str = "..." + path_str[-37:]
        col.label(text=path_str, icon='NONE')
    else:
        col.label(text="Unknown", icon='NONE')

    layout.prop(meta, "edit_description", text="Description")
    layout.prop(meta, "edit_license", text="License")
    layout.prop(meta, "edit_copyright", text="Copyright")
    layout.prop(meta, "edit_author", text="Author")


def _draw_tags_override(self, context):
    """Override for ASSETBROWSER_PT_metadata_tags.draw() during edit mode."""
    layout = self.layout

    asset = getattr(context, "asset", None)
    if not asset:
        return

    wm = context.window_manager
    meta = getattr(wm, "qam_metadata_edit", None)

    if not meta:
        layout.label(text="Tags unavailable")
        return

    source_path = _get_asset_source_path(context)
    current_key = f"{source_path}:{asset.name}" if source_path else asset.name
    stored_key = f"{meta.source_file}:{meta.asset_name}"

    if current_key != stored_key:
        meta.sync_from_asset(asset, source_path)

    row = layout.row()
    row.template_list(
        "QAM_UL_metadata_tags", "",
        meta, "edit_tags",
        meta, "active_tag_index",
        rows=3,
    )
    col = row.column(align=True)
    col.operator("qam.tag_add", icon='ADD', text="")
    col.operator("qam.tag_remove", icon='REMOVE', text="")

    layout.separator(factor=0.3)


# ============================================================================
# EDIT MODE — CLEAN PUBLIC API
# ============================================================================

def enter_edit_mode(metadata_draw_fn, tags_draw_fn) -> bool:
    """
    Override Blender's native asset metadata panel draws with editable versions.
    Called only by QAM_OT_toggle_edit_mode when toggling edit mode on.

    Args:
        metadata_draw_fn: Replacement draw function for ASSETBROWSER_PT_metadata
        tags_draw_fn:     Replacement draw function for ASSETBROWSER_PT_metadata_tags

    Returns:
        True if override was applied successfully, False otherwise.

    Sensitive to: ASSETBROWSER_PT_metadata and ASSETBROWSER_PT_metadata_tags
    class names. If these change in a future Blender version this will fail
    gracefully — native panels are left unaffected.
    Check: bl_ui/space_filebrowser.py in the Blender source.
    """
    global _original_metadata_draw, _original_tags_draw
    try:
        from bl_ui.space_filebrowser import (
            ASSETBROWSER_PT_metadata,
            ASSETBROWSER_PT_metadata_tags,
        )
        _original_metadata_draw = ASSETBROWSER_PT_metadata.draw
        _original_tags_draw = ASSETBROWSER_PT_metadata_tags.draw
        ASSETBROWSER_PT_metadata.draw = metadata_draw_fn
        ASSETBROWSER_PT_metadata_tags.draw = tags_draw_fn
        if bpy.app.debug:
            print("[QAM] Entered metadata edit mode — native panels overridden")
        return True
    except Exception as e:
        if bpy.app.debug:
            print(f"[QAM] Could not enter edit mode: {e}")
        _original_metadata_draw = None
        _original_tags_draw = None
        return False


def exit_edit_mode() -> None:
    """
    Restore Blender's native panel draws. Safe to call when not in edit mode.
    Always called on unregister to ensure panels are never left overridden.
    """
    global _original_metadata_draw, _original_tags_draw
    try:
        from bl_ui.space_filebrowser import (
            ASSETBROWSER_PT_metadata,
            ASSETBROWSER_PT_metadata_tags,
        )
        if _original_metadata_draw is not None:
            ASSETBROWSER_PT_metadata.draw = _original_metadata_draw
        if _original_tags_draw is not None:
            ASSETBROWSER_PT_metadata_tags.draw = _original_tags_draw
        if bpy.app.debug:
            print("[QAM] Exited metadata edit mode — native panels restored")
    except Exception as e:
        if bpy.app.debug:
            print(f"[QAM] Error restoring native panels: {e}")
    finally:
        _original_metadata_draw = None
        _original_tags_draw = None


# ============================================================================
# EDIT MODE — LEGACY WRAPPERS
# Called by QAM_OT_toggle_edit_mode and QAM_OT_apply_metadata_changes in
# operators/metadata.py. These wrap the clean API with state tracking.
# ============================================================================

def _enter_edit_mode(context) -> None:
    """Enter edit mode using the embedded draw overrides. Used by toggle operator."""
    global _edit_mode_active, _edit_mode_asset_key

    if _edit_mode_active:
        return

    asset = getattr(context, "asset", None)
    if asset:
        source_path = _get_asset_source_path(context)
        _edit_mode_asset_key = f"{source_path}:{asset.name}" if source_path else asset.name

    success = enter_edit_mode(_draw_metadata_override, _draw_tags_override)
    if success:
        _edit_mode_active = True
        try:
            for area in context.screen.areas:
                if area.type == 'FILE_BROWSER':
                    area.tag_redraw()
        except Exception:
            pass


def _exit_edit_mode() -> None:
    """Exit edit mode and restore native panels. Used by toggle/apply/cancel."""
    global _edit_mode_active, _edit_mode_asset_key

    if not _edit_mode_active and _original_metadata_draw is None:
        return

    exit_edit_mode()
    _edit_mode_active = False
    _edit_mode_asset_key = ""

    try:
        for window in bpy.context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'FILE_BROWSER':
                    area.tag_redraw()
    except Exception:
        pass


def register():
    bulk_panel.register()
    context_menu.register()
    manage_panel.register()
    save_panel.register()


def unregister():
    # Always exit edit mode on unregister — crash recovery and clean reload
    exit_edit_mode()
    save_panel.unregister()
    manage_panel.unregister()
    context_menu.unregister()
    bulk_panel.unregister()