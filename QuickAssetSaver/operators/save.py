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


def get_addon_preferences():
    """Get the addon preferences object."""
    addon = bpy.context.preferences.addons.get(__package__.rsplit('.', 1)[0], None)
    if addon:
        return addon.preferences
    return None


class QAS_OT_save_asset_to_library_direct(Operator):
    """Save selected asset directly from panel without popup"""

    bl_idname = "qas.save_asset_to_library_direct"
    bl_label = "Copy to Asset Library"
    bl_description = "Save this asset as a standalone .blend file in your asset library"
    bl_options = {"REGISTER", "UNDO"}
    
    conflict_action: bpy.props.EnumProperty(
        name="File Exists",
        description="A file with this name already exists. What would you like to do?",
        items=[
            ("INCREMENT", "Save with New Name", "Save as Name_001.blend, etc."),
            ("OVERWRITE", "Overwrite", "Replace the existing file"),
            ("CANCEL", "Cancel", "Don't save"),
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
        props = wm.qas_save_props
        
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
        props = wm.qas_save_props

        if not props.selected_library or props.selected_library == "NONE":
            self.report({"ERROR"}, "No asset library selected")
            return {"CANCELLED"}

        library_name, library_path_str = get_library_by_identifier(props.selected_library)
        
        debug_print(f"[QAS Debug] Selected library identifier: {props.selected_library}")
        debug_print(f"[QAS Debug] Resolved library name: {library_name}")
        debug_print(f"[QAS Debug] Resolved library path: {library_path_str}")
        
        if not library_path_str:
            self.report({"ERROR"}, f"Could not find library for: {props.selected_library}. Please re-select the library.")
            return {"CANCELLED"}

        library_path = Path(library_path_str)
        if not library_path.exists():
            self.report({"ERROR"}, f"Library path does not exist: {library_path}")
            return {"CANCELLED"}

        target_dir = library_path

        if (
            prefs.use_catalog_subfolders
            and props.catalog
            and props.catalog != "UNASSIGNED"
        ):
            catalog_path = get_catalog_path_from_uuid(
                library_path_str, props.catalog
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

        if asset_id.asset_data:
            asset_id.name = props.asset_display_name

            asset_id.asset_data.author = props.asset_author
            asset_id.asset_data.description = props.asset_description
            asset_id.asset_data.license = props.asset_license
            asset_id.asset_data.copyright = props.asset_copyright

            if props.catalog and props.catalog != "UNASSIGNED":
                asset_id.asset_data.catalog_id = props.catalog

        datablocks = {asset_id}

        success = write_blend_file(output_path, datablocks)

        if not success:
            self.report({"ERROR"}, f"Failed to write {output_path.name}")
            return {"CANCELLED"}

        self.report({"INFO"}, f"Saved asset to {output_path.name}")
        
        props.show_success_message = True
        props.success_message_time = time.time()

        if prefs.auto_refresh:
            refresh_asset_browser(context)

        return {"FINISHED"}


class QAS_OT_open_library_folder(Operator):
    """Open the asset library folder in the system file browser"""

    bl_idname = "qas.open_library_folder"
    bl_label = "Open Library Folder"
    bl_description = "Open the configured asset library folder in your file browser"
    bl_options = {"REGISTER"}

    def execute(self, context):
        """Execute the operator to open the library folder."""
        from ..properties import get_library_by_identifier

        wm = context.window_manager
        props = wm.qas_save_props

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
    QAS_OT_save_asset_to_library_direct,
    QAS_OT_open_library_folder,
)
