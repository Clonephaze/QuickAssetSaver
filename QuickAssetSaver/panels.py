
import bpy

from .properties import DEBUG_MODE

MAX_PATH_DISPLAY_LENGTH = 40
LARGE_SELECTION_THRESHOLD = 10
EXCLUDED_LIBRARY_REFS = ["LOCAL", "CURRENT", "ALL", "ESSENTIALS"]

_original_preview_panel_poll = None

def debug_print(*args, **kwargs):
    if DEBUG_MODE:
        print(*args, **kwargs)

def is_user_library(context, asset_lib_ref):
    """
    Check if the given library reference is a user-configured library.

    Args:
        context: Blender context
        asset_lib_ref: Library reference string to check

    Returns:
        bool: True if this is a user-configured library
    """
    if not asset_lib_ref or asset_lib_ref in EXCLUDED_LIBRARY_REFS:
        return False

    prefs = context.preferences
    if hasattr(prefs, "filepaths") and hasattr(prefs.filepaths, "asset_libraries"):
        for lib in prefs.filepaths.asset_libraries:
            if hasattr(lib, "name") and lib.name == asset_lib_ref:
                return True

    return False


def _count_selected_assets(context):
    """Count the number of selected assets in the Asset Browser.
    
    Returns:
        int: Number of selected assets, or 0 if none or unavailable.
    """
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

def _format_keymap_item(kmi):
    """Return a human-readable accelerator string for a keymap item."""
    parts = []
    if getattr(kmi, "ctrl", False):
        parts.append("Ctrl")
    if getattr(kmi, "alt", False):
        parts.append("Alt")
    if getattr(kmi, "shift", False):
        parts.append("Shift")
    key = getattr(kmi, "type", "")
    if key:
        parts.append(key.title())
    return "+".join(parts) if parts else "N"

def _find_tool_props_keybinding():
    """Find the active keybinding for toggling TOOL_PROPS in Asset Browser.

    Searches keymaps for wm.context_toggle with data_path 'space_data.show_region_tool_props'.
    Returns a string like 'N' or 'Ctrl+N'. Falls back to 'N' if not found.
    """
    try:
        wm = bpy.context.window_manager
        kc = getattr(wm, "keyconfigs", None)
        if not kc:
            return "N"
        active = getattr(kc, "active", None) or getattr(kc, "user", None) or getattr(kc, "default", None)
        if not active:
            return "N"

        candidate_maps = [
            active.keymaps.get("File Browser"),
            active.keymaps.get("Asset Browser"),
            active.keymaps.get("Window"),
            active.keymaps.get("Screen"),
        ]
        for km in candidate_maps:
            if not km:
                continue
            for kmi in km.keymap_items:
                if kmi.idname == "wm.context_toggle" and getattr(kmi.properties, "data_path", "") == "space_data.show_region_tool_props":
                    return _format_keymap_item(kmi) or "N"
    except Exception:
        pass
    return "N"


class QAS_PT_save_hint(bpy.types.Panel):
    """Hint panel shown in Current File to direct users to the right-side Save panel."""
    bl_label = "Quick Asset Saver"
    bl_idname = "QAS_PT_save_hint"
    bl_space_type = "FILE_BROWSER"
    bl_region_type = "TOOLS"
    bl_category = "Assets"
    bl_order = 10

    @classmethod
    def poll(cls, context):
        # Only show in Asset Browser when viewing Current File assets
        space = context.space_data
        if not space or space.type != "FILE_BROWSER":
            return False
        if not hasattr(space, "browse_mode") or space.browse_mode != "ASSETS":
            return False
        params = getattr(space, "params", None)
        if not params:
            return False
        asset_lib_ref = getattr(params, "asset_library_reference", None)
        is_current_file = asset_lib_ref in ["LOCAL", "CURRENT"] or getattr(params, "asset_library_ref", None) == "LOCAL"
        return bool(is_current_file)

    def draw(self, context):
        layout = self.layout

        # Message
        box = layout.box()
        box.label(text="The save panel has moved to", icon="INFO")
        box.label(text="Blender's tool panel to the right.", icon="BLANK1")
        key_str = _find_tool_props_keybinding()
        box.label(text=f"Open it with your ( {key_str} ) key.", icon="BLANK1")

class QAS_UL_metadata_tags(bpy.types.UIList):
    """UIList for displaying and editing asset tags."""
    bl_idname = "QAS_UL_metadata_tags"
    
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if self.layout_type in {'DEFAULT', 'COMPACT'}:
            layout.prop(item, "name", text="", emboss=False, icon='NONE')
        elif self.layout_type == 'GRID':
            layout.alignment = 'CENTER'
            layout.label(text=item.name, icon='NONE')


class QAS_OT_tag_add(bpy.types.Operator):
    """Add a new tag to the asset"""
    bl_idname = "qas.tag_add"
    bl_label = "Add Tag"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        return hasattr(wm, "qas_metadata_edit")
    
    def execute(self, context):
        wm = context.window_manager
        meta = wm.qas_metadata_edit
        
        tag = meta.edit_tags.add()
        tag.name = "Tag"
        meta.active_tag_index = len(meta.edit_tags) - 1
        
        return {'FINISHED'}


class QAS_OT_tag_remove(bpy.types.Operator):
    """Remove the selected tag"""
    bl_idname = "qas.tag_remove"
    bl_label = "Remove Tag"
    bl_options = {'REGISTER', 'UNDO'}
    
    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        if not hasattr(wm, "qas_metadata_edit"):
            return False
        meta = wm.qas_metadata_edit
        return len(meta.edit_tags) > 0 and meta.active_tag_index >= 0
    
    def execute(self, context):
        wm = context.window_manager
        meta = wm.qas_metadata_edit
        
        if meta.active_tag_index < len(meta.edit_tags):
            meta.edit_tags.remove(meta.active_tag_index)
            # Adjust active index if needed
            if meta.active_tag_index >= len(meta.edit_tags) and meta.active_tag_index > 0:
                meta.active_tag_index -= 1
        
        return {'FINISHED'}


class QAS_MT_asset_context_menu(bpy.types.Menu):
    """Quick Asset Saver context menu items for the Asset Browser."""
    bl_idname = "QAS_MT_asset_context_menu"
    bl_label = "Quick Asset Saver"

    def draw(self, context):
        layout = self.layout
        layout.operator("qas.delete_selected_assets", text="Remove Asset from Library", icon="TRASH")


def draw_asset_context_menu(self, context):
    """Append Quick Asset Saver options to the Asset Browser context menu."""
    # Only show in Asset Browser
    if not hasattr(context, "space_data") or context.space_data.type != "FILE_BROWSER":
        return
    if getattr(context.space_data, "browse_mode", None) != "ASSETS":
        return
    
    # Check if we're viewing local assets (Current File) or external library
    params = context.space_data.params
    asset_lib_ref = getattr(params, "asset_library_reference", None)
    is_current_file = asset_lib_ref in ["LOCAL", "CURRENT"] or getattr(params, "asset_library_ref", None) == "LOCAL"
    
    # Only show context menu items for external library assets
    if not is_current_file:
        layout = self.layout
        layout.separator()
        layout.operator("qas.swap_selected_with_asset", text="Replace Selected Objects", icon="FILE_REFRESH")
        layout.operator("qas.delete_selected_assets", text="Remove Asset from Library", icon="TRASH")


# ============================================================================
# BULK OPERATIONS PANEL (RIGHT SIDE - for 2+ assets)
# ============================================================================

class QAS_PT_bulk_operations(bpy.types.Panel):
    """Panel for bulk operations when 2+ assets are selected."""
    
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Bulk Operations"
    bl_order = 1  # Show first
    
    @classmethod
    def poll(cls, context):
        # Only show in Asset Browser
        space = context.space_data
        if not space or space.type != "FILE_BROWSER":
            return False
        if not hasattr(space, "browse_mode") or space.browse_mode != "ASSETS":
            return False
        
        # Only show when 2+ assets selected
        selected_count = _count_selected_assets(context)
        if selected_count < 2:
            return False
        
        # Only show in user libraries (not Current File)
        params = space.params
        if not hasattr(params, "asset_library_reference"):
            return False
        asset_lib_ref = params.asset_library_reference
        return is_user_library(context, asset_lib_ref)
    
    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        bundler_props = wm.qas_bundler_props
        manage_props = getattr(wm, "qas_manage_props", None)
        
        selected_count = _count_selected_assets(context)
        
        # Move section
        layout.label(text=f"{selected_count} Assets Selected", icon="ASSET_MANAGER")
        layout.separator()
        
        box = layout.box()
        box.label(text="Move Assets", icon="EXPORT")
        if manage_props:
            box.prop(manage_props, "move_target_library", text="Library")
            box.prop(manage_props, "move_target_catalog", text="Catalog")
        
        row = box.row()
        row.scale_y = 1.2
        row.operator("qas.move_selected_to_library", text=f"Move {selected_count} Assets", icon="EXPORT")
        
        layout.separator()
        
        # Bundle section
        box = layout.box()
        box.label(text="Bundle Assets", icon="PACKAGE")
        box.prop(bundler_props, "output_name", text="Name")
        box.prop(bundler_props, "save_path", text="Path")
        box.prop(bundler_props, "duplicate_mode", text="Overwrite")
        box.prop(bundler_props, "copy_catalog")
        
        row = box.row()
        row.scale_y = 1.2
        row.operator("qas.bundle_assets", text=f"Bundle {selected_count} Assets", icon="PACKAGE")


def _get_asset_source_path(context):
    """Get the source .blend file path for the active asset.
    
    Returns:
        Path or None: Path to the source .blend file, or None if unavailable
    """
    from pathlib import Path
    
    asset = getattr(context, "asset", None)
    if not asset:
        return None
    
    def extract_blend_path(full_path_str):
        """Extract just the .blend file path from a full asset path.
        
        Blender's full_path includes the internal datablock path, e.g.:
        C:\\path\\to\\file.blend\\Material\\Asset Name
        We need to extract just: C:\\path\\to\\file.blend
        """
        if not full_path_str:
            return None
        # Find .blend in the path and cut off everything after it
        lower_path = full_path_str.lower()
        blend_idx = lower_path.find('.blend')
        if blend_idx != -1:
            return Path(full_path_str[:blend_idx + 6])  # +6 for '.blend'
        return None
    
    # Try full_path first (newer API)
    if hasattr(asset, "full_path") and asset.full_path:
        blend_path = extract_blend_path(asset.full_path)
        if blend_path:
            return blend_path
    
    # Try full_library_path
    if hasattr(asset, "full_library_path") and asset.full_library_path:
        blend_path = extract_blend_path(asset.full_library_path)
        if blend_path:
            return blend_path
    
    # Fallback: construct from library path + relative path
    space = context.space_data
    if space and hasattr(space, "params"):
        params = space.params
        lib_ref = getattr(params, "asset_library_reference", None)
        if lib_ref and lib_ref not in EXCLUDED_LIBRARY_REFS:
            # Get library path
            for lib in context.preferences.filepaths.asset_libraries:
                if lib.name == lib_ref:
                    lib_path = Path(lib.path)
                    # Get relative path from active file
                    active_file = getattr(context, "active_file", None)
                    if active_file and hasattr(active_file, "relative_path"):
                        return lib_path / active_file.relative_path
    
    return None


class QAS_PT_asset_metadata(bpy.types.Panel):
    """Replacement for Blender's asset metadata panel with editable fields."""
    
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Asset Metadata"
    bl_options = {'HIDE_HEADER'}
    
    @classmethod
    def poll(cls, context):
        # Same poll as original - needs to be in asset browser
        space = context.space_data
        if not space or space.type != "FILE_BROWSER":
            return False
        if not hasattr(space, "browse_mode") or space.browse_mode != "ASSETS":
            return False
        
        # Hide when 2+ assets selected (bulk ops panel takes over)
        selected_count = _count_selected_assets(context)
        if selected_count >= 2:
            return False
        
        return True
    
    def draw(self, context):
        layout = self.layout
        
        asset = getattr(context, "asset", None)
        if not asset:
            layout.label(text="No asset selected")
            return
        
        # Check if this is a local asset (editable natively by Blender)
        is_local = bool(asset.local_id)
        
        if is_local:
            # For local assets, draw native fields like Blender does
            self._draw_local_asset(layout, context, asset)
        else:
            # For external assets, draw our editable fields
            self._draw_external_asset(layout, context, asset)
    
    def _draw_local_asset(self, layout, context, asset):
        """Draw editable fields for local assets (Current File) using our own properties."""
        wm = context.window_manager
        props = getattr(wm, "qas_save_props", None)
        
        if not props:
            layout.label(text="Properties unavailable")
            return
        
        # Sync props with current asset when asset changes
        asset_name = asset.name
        if props.last_asset_name != asset_name:
            # New asset selected - initialize props from preferences
            props.last_asset_name = asset_name
            props.asset_display_name = asset_name
            # Manually populate asset_file_name since update callback doesn't fire on direct assignment
            from .operators import sanitize_name
            props.asset_file_name = sanitize_name(asset_name)
            
            from .properties import get_addon_preferences
            prefs = get_addon_preferences(context)
            if prefs:
                props.asset_author = prefs.default_author
                props.asset_description = prefs.default_description
                props.asset_license = prefs.default_license
                props.asset_copyright = prefs.default_copyright
        
        # Add top padding
        layout.separator(factor=0.5)
        
        # Name (editable)
        layout.prop(props, "asset_display_name", text="Name")
        
        # Source path (greyed out, non-editable)
        col = layout.column(align=True)
        col.enabled = False
        col.label(text="Source")
        col.label(text="Current File", icon='NONE')
        
        # Metadata fields (using our properties)
        layout.prop(props, "asset_description", text="Description")
        layout.prop(props, "asset_license", text="License")
        layout.prop(props, "asset_copyright", text="Copyright")
        layout.prop(props, "asset_author", text="Author")
    
    def _draw_external_asset(self, layout, context, asset):
        """Draw editable fields for external assets (user libraries)."""
        wm = context.window_manager
        meta = getattr(wm, "qas_metadata_edit", None)
        
        if not meta:
            layout.label(text="Metadata editing unavailable")
            return
        
        source_path = _get_asset_source_path(context)
        
        # Check if we need to sync (different asset selected)
        current_key = f"{source_path}:{asset.name}" if source_path else asset.name
        stored_key = f"{meta.source_file}:{meta.asset_name}"
        
        if current_key != stored_key:
            # New asset selected, sync the fields
            meta.sync_from_asset(asset, source_path)
        
        # Add top padding
        layout.separator(factor=0.5)
        
        # Editable name field
        layout.prop(meta, "edit_name", text="Name")
        
        # Source path (greyed out, read-only display)
        col = layout.column(align=True)
        col.enabled = False
        col.label(text="Source")
        if source_path:
            # Show truncated path
            path_str = str(source_path)
            if len(path_str) > 40:
                path_str = "..." + path_str[-37:]
            col.label(text=path_str, icon='NONE')
        else:
            col.label(text="Unknown", icon='NONE')
        
        # Editable metadata fields
        layout.prop(meta, "edit_description", text="Description")
        layout.prop(meta, "edit_license", text="License")
        layout.prop(meta, "edit_copyright", text="Copyright")
        layout.prop(meta, "edit_author", text="Author")


# Store reference to original panels for restoration
_original_metadata_panel = None
_original_tags_panel = None


class QAS_PT_asset_tags(bpy.types.Panel):
    """Custom tags panel that replaces Blender's ASSETBROWSER_PT_metadata_tags."""
    
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Tags"
    bl_order = 50  # After Preview (which is around 40)
    
    @classmethod
    def poll(cls, context):
        # Only show in Asset Browser with an active asset
        space = context.space_data
        if not space or space.type != "FILE_BROWSER":
            return False
        if not hasattr(space, "browse_mode") or space.browse_mode != "ASSETS":
            return False
        
        # Hide when 2+ assets selected (bulk ops panel takes over)
        selected_count = _count_selected_assets(context)
        if selected_count >= 2:
            return False
        
        asset = getattr(context, "asset", None)
        return asset is not None
    
    def draw(self, context):
        layout = self.layout
        asset = getattr(context, "asset", None)
        
        if not asset:
            return
        
        is_local = bool(asset.local_id)
        
        if is_local:
            # For local assets, show Blender's native tag editor
            metadata = asset.local_id.asset_data
            if metadata:
                row = layout.row()
                row.template_list(
                    "ASSETBROWSER_UL_metadata_tags", "asset_tags",
                    metadata, "tags",
                    metadata, "active_tag",
                    rows=3,
                )
                col = row.column(align=True)
                col.operator("asset.tag_add", icon='ADD', text="")
                col.operator("asset.tag_remove", icon='REMOVE', text="")
                
                layout.separator(factor=0.3)
        else:
            # For external assets, show our custom editable tag list
            wm = context.window_manager
            meta = getattr(wm, "qas_metadata_edit", None)
            
            if not meta:
                layout.label(text="Tags unavailable")
                return
            
            # Ensure we're synced with the current asset
            source_path = _get_asset_source_path(context)
            current_key = f"{source_path}:{asset.name}" if source_path else asset.name
            stored_key = f"{meta.source_file}:{meta.asset_name}"
            
            if current_key != stored_key:
                meta.sync_from_asset(asset, source_path)
            
            row = layout.row()
            row.template_list(
                "QAS_UL_metadata_tags", "",
                meta, "edit_tags",
                meta, "active_tag_index",
                rows=3,
            )
            col = row.column(align=True)
            col.operator("qas.tag_add", icon='ADD', text="")
            col.operator("qas.tag_remove", icon='REMOVE', text="")
            
            # Small gap before filtering options
            layout.separator(factor=0.3)


class QAS_PT_asset_actions(bpy.types.Panel):
    """Panel for asset actions - Apply Changes and Remove Asset for external assets."""
    
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Actions"
    bl_order = 60  # After Tags (50)
    
    @classmethod
    def poll(cls, context):
        # Only show for external assets (not from Current File)
        space = context.space_data
        if not space or space.type != "FILE_BROWSER":
            return False
        if not hasattr(space, "browse_mode") or space.browse_mode != "ASSETS":
            return False
        
        # Hide when 2+ assets selected (bulk ops panel takes over)
        selected_count = _count_selected_assets(context)
        if selected_count >= 2:
            return False
        
        # Check if there's an active asset
        asset = getattr(context, "asset", None)
        if not asset:
            return False
        
        # Check if this is a LOCAL asset (has local_id) - if so, don't show this panel
        # This works correctly even in "All Libraries" view
        is_local = bool(asset.local_id)
        return not is_local
    
    def draw(self, context):
        layout = self.layout
        
        wm = context.window_manager
        meta = getattr(wm, "qas_metadata_edit", None)
        manage = getattr(wm, "qas_manage_props", None)
        
        # Check if there are changes
        has_changes = meta.has_changes() if meta else False
        
        # Apply Changes button (greyed out if no changes)
        row = layout.row()
        row.scale_y = 1.2
        row.enabled = has_changes
        row.operator("qas.apply_metadata_changes", text="Apply Changes", icon="CHECKMARK")
        
        # Move section
        layout.separator()
        layout.label(text="Move", icon="ASSET_MANAGER")
        box = layout.box()
        if manage:
            box.prop(manage, "move_target_library", text="Library")
            box.prop(manage, "move_target_catalog", text="Catalog")
        
        move_row = box.row()
        move_row.scale_y = 1.2
        move_row.operator("qas.move_selected_to_library", text="Move", icon="EXPORT")
        
        # Remove Asset button
        layout.separator()
        row = layout.row()
        row.scale_y = 1.2
        row.operator("qas.delete_selected_assets", text="Remove Asset from Library", icon="TRASH")


class QAS_PT_save_to_library(bpy.types.Panel):
    """Panel for saving local assets to a library - appears after Tags."""
    
    bl_space_type = 'FILE_BROWSER'
    bl_region_type = 'TOOL_PROPS'
    bl_label = "Save to Library"
    bl_order = 100  # High number to appear after Tags
    
    @classmethod
    def poll(cls, context):
        # Only show for local assets (from Current File)
        space = context.space_data
        if not space or space.type != "FILE_BROWSER":
            return False
        if not hasattr(space, "browse_mode") or space.browse_mode != "ASSETS":
            return False
        
        # Hide when 2+ assets selected (not applicable to local assets bulk)
        selected_count = _count_selected_assets(context)
        if selected_count >= 2:
            return False
        
        # Check if there's an active asset that is LOCAL (has local_id)
        # This works correctly even in "All Libraries" view
        asset = getattr(context, "asset", None)
        if not asset:
            return False
        
        return bool(asset.local_id)
    
    def draw(self, context):
        layout = self.layout
        wm = context.window_manager
        props = getattr(wm, "qas_save_props", None)
        
        if not props:
            layout.label(text="Properties unavailable")
            return
        
        # Target library dropdown
        layout.prop(props, "selected_library", text="Library")
        
        # Catalog dropdown
        layout.prop(props, "catalog", text="Catalog")
        
        # Show target path preview
        from .properties import get_library_by_identifier
        if props.selected_library and props.selected_library != "NONE":
            lib_name, lib_path = get_library_by_identifier(props.selected_library)
            if lib_path:
                # Truncate long paths
                if len(lib_path) > 35:
                    lib_path = lib_path[:15] + "..." + lib_path[-17:]
                layout.label(text=lib_path, icon="FILE_FOLDER")
        
        # Warn about collection asset previews
        asset = getattr(context, "asset", None)
        if asset and asset.local_id and isinstance(asset.local_id, bpy.types.Collection):
            box = layout.box()
            col = box.column(align=True)
            col.label(text="Collection previews may need", icon="INFO")
            col.label(text="regeneration after saving.")
        
        # Copy to Asset Library button
        row = layout.row()
        row.scale_y = 1.2
        row.operator("qas.save_asset_to_library_direct", text="Copy to Asset Library", icon="EXPORT")


classes = (
    QAS_PT_save_hint,
    QAS_PT_bulk_operations,
    QAS_UL_metadata_tags,
    QAS_OT_tag_add,
    QAS_OT_tag_remove,
    QAS_MT_asset_context_menu,
    QAS_PT_asset_metadata,
    QAS_PT_asset_tags,
    QAS_PT_asset_actions,
    QAS_PT_save_to_library,
)


def register():
    global _original_metadata_panel, _original_tags_panel, _original_preview_panel_poll
    
    for cls in classes:
        bpy.utils.register_class(cls)
    
    bpy.types.ASSETBROWSER_MT_context_menu.append(draw_asset_context_menu)
    
    # Replace Blender's metadata panel with our custom one
    try:
        from bl_ui.space_filebrowser import ASSETBROWSER_PT_metadata
        _original_metadata_panel = ASSETBROWSER_PT_metadata
        bpy.utils.unregister_class(ASSETBROWSER_PT_metadata)
        debug_print("[QAS] Replaced ASSETBROWSER_PT_metadata with custom panel")
    except Exception as e:
        debug_print(f"[QAS] Could not replace metadata panel: {e}")
    
    # Replace Blender's tags panel with our custom one
    try:
        from bl_ui.space_filebrowser import ASSETBROWSER_PT_metadata_tags
        _original_tags_panel = ASSETBROWSER_PT_metadata_tags
        bpy.utils.unregister_class(ASSETBROWSER_PT_metadata_tags)
        debug_print("[QAS] Replaced ASSETBROWSER_PT_metadata_tags with custom panel")
    except Exception as e:
        debug_print(f"[QAS] Could not replace tags panel: {e}")
    
    # Override preview panel poll to hide when 2+ assets selected
    try:
        from bl_ui.space_filebrowser import ASSETBROWSER_PT_metadata_preview
        _original_preview_panel_poll = ASSETBROWSER_PT_metadata_preview.poll
        
        @classmethod
        def custom_preview_poll(cls, context):
            # Hide when 2+ assets selected (bulk ops mode)
            selected_count = _count_selected_assets(context)
            if selected_count >= 2:
                return False
            # Otherwise use original poll logic
            return _original_preview_panel_poll(context)
        
        ASSETBROWSER_PT_metadata_preview.poll = custom_preview_poll
        debug_print("[QAS] Overrode ASSETBROWSER_PT_metadata_preview poll method")
    except Exception as e:
        debug_print(f"[QAS] Could not override preview panel poll: {e}")


def unregister():
    global _original_metadata_panel, _original_tags_panel, _original_preview_panel_poll
    
    bpy.types.ASSETBROWSER_MT_context_menu.remove(draw_asset_context_menu)
    
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
    
    # Restore Blender's original metadata panel
    if _original_metadata_panel:
        try:
            bpy.utils.register_class(_original_metadata_panel)
            debug_print("[QAS] Restored original ASSETBROWSER_PT_metadata panel")
        except Exception as e:
            debug_print(f"[QAS] Could not restore metadata panel: {e}")
        _original_metadata_panel = None
    
    # Restore Blender's original tags panel
    if _original_tags_panel:
        try:
            bpy.utils.register_class(_original_tags_panel)
            debug_print("[QAS] Restored original ASSETBROWSER_PT_metadata_tags panel")
        except Exception as e:
            debug_print(f"[QAS] Could not restore tags panel: {e}")
        _original_tags_panel = None
    
    # Restore preview panel poll method
    if _original_preview_panel_poll:
        try:
            from bl_ui.space_filebrowser import ASSETBROWSER_PT_metadata_preview
            ASSETBROWSER_PT_metadata_preview.poll = _original_preview_panel_poll
            debug_print("[QAS] Restored original ASSETBROWSER_PT_metadata_preview poll")
        except Exception as e:
            debug_print(f"[QAS] Could not restore preview panel poll: {e}")
        _original_preview_panel_poll = None
