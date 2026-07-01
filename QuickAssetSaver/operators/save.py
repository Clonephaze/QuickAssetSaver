"""
Save asset operator for Quick Asset Saver.
"""

import time
from pathlib import Path

import bpy
from bpy.types import Operator

from .utils import (
    debug_print,
    sanitize_name,
    build_asset_filename,
    increment_filename,
    refresh_asset_browser,
)
from .catalog import get_catalog_path_from_uuid
from .file_io import write_blend_file


def _auto_create_catalog_if_needed(library_path_str: str, source_catalog_uuid: str):
    """
    Resolve source_catalog_uuid (the asset's existing catalog from the Current File)
    to a catalog path string, then ensure that path exists in the target library —
    creating it if not. Returns the UUID to use when saving to the target library,
    or None if the path could not be resolved.

    Resolution order for the path:
    1. Current file's sibling blender_assets.cats.txt (if file is saved)
    2. The target library's own CDF (already migrated in a prior save)

    Never raises — failures must not block the save.
    """
    from .catalog import get_catalog_path_from_uuid, create_catalog_entry

    catalog_path = None

    # Try to resolve from the current file's CDF first
    if bpy.data.filepath:
        current_dir = str(Path(bpy.data.filepath).parent)
        catalog_path = get_catalog_path_from_uuid(current_dir, source_catalog_uuid)

    # Fallback: UUID already exists in target library from a prior save
    if not catalog_path:
        catalog_path = get_catalog_path_from_uuid(library_path_str, source_catalog_uuid)

    if not catalog_path:
        if bpy.app.debug:
            print(f"[QAM] auto_create_catalog: could not resolve UUID {source_catalog_uuid} to a path — skipping")
        return None

    try:
        return create_catalog_entry(library_path_str, catalog_path)
    except Exception as e:
        if bpy.app.debug:
            print(f"[QAM] auto_create_catalog: failed to create entry: {e}")
        return None


class QAM_OT_save_asset_to_library_direct(Operator):
    """Save selected asset directly from panel without popup"""

    bl_idname = "qam.save_asset_to_library_direct"
    bl_label = "Copy to Asset Library"
    bl_description = "Save this asset as a standalone .blend file in your asset library"
    bl_options = {"REGISTER", "UNDO"}
    
    conflict_action: bpy.props.EnumProperty(
        name="File Exists",
        description="A file with this name already exists. What would you like to do?",
        items=[
            ("INCREMENT", "Save with New Name", "Save as Name_001.blend, etc."),
            ("OVERWRITE", "Overwrite", "Replace the existing file"),
        ],
        default="INCREMENT",
    )
    
    _conflict_path: str = ""
    
    def invoke(self, context, event):
        """Check for conflicts before executing."""
        from .. import properties
        from ..properties import get_library_by_identifier
        
        prefs = properties.get_addon_preferences(context)
        wm = context.window_manager
        props = wm.qam_save_props
        
        # Ensure asset name is synced to our properties
        asset = getattr(context, "asset", None)
        if asset and asset.local_id:
            # Use asset name if our properties are empty or stale
            if not props.asset_file_name or props.last_asset_name != asset.name:
                props.last_asset_name = asset.name
                props.asset_display_name = asset.name
                props.asset_file_name = sanitize_name(asset.name)
                
                # Also sync metadata from asset_data if available
                if asset.local_id.asset_data:
                    asset_data = asset.local_id.asset_data
                    props.asset_description = asset_data.description or ""
                    props.asset_author = asset_data.author or ""
                    props.asset_license = asset_data.license or ""
                    props.asset_copyright = asset_data.copyright or ""
                else:
                    # Use preference defaults if no asset_data yet
                    if prefs:
                        props.asset_author = prefs.default_author
                        props.asset_description = prefs.default_description
                        props.asset_license = prefs.default_license
                        props.asset_copyright = prefs.default_copyright
        
        if not props.selected_library or props.selected_library == "NONE":
            self.report({"ERROR"}, "No asset library selected")
            return {"CANCELLED"}
        
        library_name, library_path_str = get_library_by_identifier(props.selected_library)
        if not library_path_str:
            self.report({"ERROR"}, "Could not find library path")
            return {"CANCELLED"}
        
        library_path = Path(library_path_str)
        target_dir = library_path
        
        if prefs.use_catalog_subfolders and props.catalog and props.catalog != "UNASSIGNED":
            catalog_path = get_catalog_path_from_uuid(library_path_str, props.catalog)
            if catalog_path:
                path_parts = catalog_path.split("/")
                sanitized_parts = [sanitize_name(part, max_length=64) for part in path_parts if part]
                for part in sanitized_parts:
                    target_dir = target_dir / part
        
        base_name = props.asset_file_name
        if not base_name:
            debug_print(f"[QAM Debug] asset_display_name: '{props.asset_display_name}'")
            debug_print(f"[QAM Debug] asset_file_name: '{props.asset_file_name}'")
            self.report({"ERROR"}, "Invalid file name")
            return {"CANCELLED"}
        
        final_filename = build_asset_filename(base_name, prefs)
        check_path = target_dir / f"{final_filename}.blend"
        
        if check_path.exists():
            self._conflict_path = str(check_path)
            return context.window_manager.invoke_props_dialog(self, width=350)
        
        return self.execute(context)
    
    def draw(self, context):
        """Draw the conflict resolution dialog."""
        layout = self.layout
        layout.label(text="A file with this name already exists:", icon="ERROR")
        
        path = self._conflict_path
        if len(path) > 50:
            path = "..." + path[-47:]
        layout.label(text=path)
        
        layout.separator()
        layout.prop(self, "conflict_action", text="")

    def execute(self, context):
        """Execute the save operation directly using panel properties."""
        from .. import properties
        from ..properties import get_library_by_identifier

        prefs = properties.get_addon_preferences(context)
        wm = context.window_manager
        props = wm.qam_save_props

        if not props.selected_library or props.selected_library == "NONE":
            self.report({"ERROR"}, "No asset library selected")
            return {"CANCELLED"}

        library_name, library_path_str = get_library_by_identifier(props.selected_library)
        
        debug_print(f"[QAM Debug] Selected library identifier: {props.selected_library}")
        debug_print(f"[QAM Debug] Resolved library name: {library_name}")
        debug_print(f"[QAM Debug] Resolved library path: {library_path_str}")
        
        if not library_path_str:
            self.report({"ERROR"}, f"Could not find library for: {props.selected_library}. Please re-select the library.")
            return {"CANCELLED"}

        library_path = Path(library_path_str)
        if not library_path.exists():
            self.report({"ERROR"}, f"Library path does not exist: {library_path}")
            return {"CANCELLED"}

        target_dir = library_path

        # Determine the catalog UUID to assign to the saved asset.
        # When auto-create is on: read the asset's existing catalog from the Current File
        # and ensure it exists in the target library, creating it if needed.
        # This lets the asset land in the right catalog even if the target library
        # doesn't have that catalog yet — bypassing the dropdown entirely.
        effective_catalog_uuid = props.catalog if props.catalog != "UNASSIGNED" else None

        if props.auto_create_catalog:
            asset_local = getattr(getattr(context, "asset", None), "local_id", None)
            if asset_local and asset_local.asset_data:
                source_catalog_id = asset_local.asset_data.catalog_id
                if source_catalog_id:
                    created_uuid = _auto_create_catalog_if_needed(library_path_str, source_catalog_id)
                    if created_uuid:
                        effective_catalog_uuid = created_uuid

        if (
            prefs.use_catalog_subfolders
            and effective_catalog_uuid
        ):
            catalog_path = get_catalog_path_from_uuid(
                library_path_str, effective_catalog_uuid
            )

            if catalog_path:
                path_parts = catalog_path.split("/")
                sanitized_parts = [
                    sanitize_name(part, max_length=64) for part in path_parts if part
                ]

                target_dir = library_path
                for part in sanitized_parts:
                    target_dir = target_dir / part

                try:
                    target_dir.mkdir(parents=True, exist_ok=True)
                except OSError as e:
                    self.report({"ERROR"}, f"Could not create catalog subfolder: {e}")
                    return {"CANCELLED"}

        try:
            test_file = target_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
        except (OSError, PermissionError):
            self.report({"ERROR"}, f"Target path is not writable: {target_dir}")
            return {"CANCELLED"}

        base_sanitized_name = props.asset_file_name
        if not base_sanitized_name:
            self.report({"ERROR"}, "Invalid file name")
            return {"CANCELLED"}

        final_filename = build_asset_filename(base_sanitized_name, prefs)

        check_path = target_dir / f"{final_filename}.blend"
        
        if check_path.exists():
            if self.conflict_action == "INCREMENT":
                output_path = increment_filename(target_dir, final_filename)
            elif self.conflict_action == "OVERWRITE":
                output_path = check_path
            else:
                self.report({"INFO"}, "Save cancelled")
                return {"CANCELLED"}
        else:
            output_path = check_path

        asset_id = None
        if hasattr(context, "asset") and hasattr(context.asset, "local_id"):
            asset_id = context.asset.local_id
        elif hasattr(context, "id"):
            asset_id = context.id

        if not asset_id:
            self.report({"ERROR"}, "Could not identify asset to save")
            return {"CANCELLED"}

        if not asset_id.asset_data:
            asset_id.asset_mark()

        # Capture originals before modifying in-memory — must restore after write
        # so the source asset in the current file is not permanently affected.
        _original_name = asset_id.name if asset_id else None
        _original_catalog_id = asset_id.asset_data.catalog_id if asset_id and asset_id.asset_data else None

        if asset_id.asset_data:
            asset_id.name = props.asset_display_name

            asset_id.asset_data.author = props.asset_author
            asset_id.asset_data.description = props.asset_description
            asset_id.asset_data.license = props.asset_license
            asset_id.asset_data.copyright = props.asset_copyright

            if effective_catalog_uuid:
                asset_id.asset_data.catalog_id = effective_catalog_uuid

        datablocks = {asset_id}

        success = write_blend_file(output_path, datablocks)

        # Restore in-memory state so the source asset is unchanged in the current file
        if _original_name is not None and asset_id:
            asset_id.name = _original_name
        if _original_catalog_id is not None and asset_id and asset_id.asset_data:
            asset_id.asset_data.catalog_id = _original_catalog_id

        if not success:
            self.report({"ERROR"}, f"Failed to write {output_path.name}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Saved asset to {output_path.name}")
        
        props.show_success_message = True
        props.success_message_time = time.time()

        if prefs.auto_refresh:
            refresh_asset_browser(context)

        return {"FINISHED"}


class QAM_OT_open_library_folder(Operator):
    """Open the asset library folder in the system file browser"""

    bl_idname = "qam.open_library_folder"
    bl_label = "Open Library Folder"
    bl_description = "Open the configured asset library folder in your file browser"
    bl_options = {"REGISTER"}

    def execute(self, context):
        """Execute the operator to open the library folder."""
        from ..properties import get_library_by_identifier

        wm = context.window_manager
        props = wm.qam_save_props

        if not props.selected_library or props.selected_library == "NONE":
            self.report({"ERROR"}, "No asset library selected")
            return {"CANCELLED"}

        library_name, library_path_str = get_library_by_identifier(props.selected_library)
        if not library_path_str:
            self.report({"ERROR"}, f"Could not find library: {props.selected_library}")
            return {"CANCELLED"}

        library_path = Path(library_path_str)
        if not library_path.exists():
            self.report({"ERROR"}, "Library path does not exist")
            return {"CANCELLED"}

        bpy.ops.wm.path_open(filepath=str(library_path))
        return {"FINISHED"}


classes = (
    QAM_OT_save_asset_to_library_direct,
    QAM_OT_open_library_folder,
)
