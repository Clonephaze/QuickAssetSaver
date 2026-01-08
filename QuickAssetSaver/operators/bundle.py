"""
Asset bundle operator for Quick Asset Saver.
"""

import shutil
import time
from datetime import datetime
from pathlib import Path

import bpy
from bpy.types import Operator

from .utils import (
    debug_print,
    sanitize_name,
    increment_filename,
    MIN_BLEND_FILE_SIZE,
    LARGE_SELECTION_WARNING_THRESHOLD,
    VERY_LARGE_BUNDLE_WARNING_MB,
    DEFAULT_MAX_BUNDLE_SIZE_MB,
)


def get_addon_preferences():
    """Get the addon preferences object."""
    addon = bpy.context.preferences.addons.get(__package__.rsplit('.', 1)[0], None)
    if addon:
        return addon.preferences
    return None


class QAS_OT_bundle_assets(Operator):
    """Bundle selected assets from a user library into a single .blend file."""

    bl_idname = "qas.bundle_assets"
    bl_label = "Bundle Selected Assets"
    bl_description = "Combine selected assets into a single shareable .blend file"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        """Only enable when in Asset Browser with a user-configured library."""
        if not context.space_data or context.space_data.type != "FILE_BROWSER":
            return False

        if not hasattr(context.space_data, "browse_mode"):
            return False

        if context.space_data.browse_mode != "ASSETS":
            return False

        params = context.space_data.params
        if not hasattr(params, "asset_library_reference"):
            return False

        asset_lib_ref = params.asset_library_reference

        excluded_refs = ["LOCAL", "CURRENT", "ALL", "ESSENTIALS"]
        if asset_lib_ref in excluded_refs:
            return False

        if hasattr(params, "asset_library_ref"):
            newer_ref = params.asset_library_ref
            if newer_ref in excluded_refs:
                return False

        prefs = context.preferences
        if hasattr(prefs, "filepaths") and hasattr(prefs.filepaths, "asset_libraries"):
            for lib in prefs.filepaths.asset_libraries:
                if hasattr(lib, "name") and lib.name == asset_lib_ref:
                    return True

        return False

    def execute(self, context):
        """Execute the bundling operation."""
        wm = context.window_manager
        props = wm.qas_bundler_props

        selected_assets = self._collect_selected_assets(context)

        if not selected_assets:
            self.report({"WARNING"}, "No assets selected")
            return {"CANCELLED"}

        active_library = self._get_active_library(context)
        if not active_library:
            self.report({"ERROR"}, "Could not determine active asset library")
            return {"CANCELLED"}

        library_path = Path(active_library.path)
        save_path = Path(props.save_path) if props.save_path else Path.home()

        try:
            if save_path.resolve().is_relative_to(library_path.resolve()):
                self.report(
                    {"WARNING"},
                    "Saving bundle inside asset library directory - this may cause issues",
                )
        except (ValueError, OSError):
            pass

        if len(selected_assets) > LARGE_SELECTION_WARNING_THRESHOLD:
            self.report(
                {"INFO"},
                f"Bundling {len(selected_assets)} assets - this may take several minutes",
            )

        total_size_mb = self._calculate_total_size(selected_assets)
        preferences = get_addon_preferences()
        max_bundle_size_mb = preferences.max_bundle_size_mb if preferences else DEFAULT_MAX_BUNDLE_SIZE_MB

        print(f"Total asset size: {total_size_mb:.1f} MB")
        print(f"Max bundle size: {max_bundle_size_mb} MB")

        if total_size_mb > max_bundle_size_mb:
            self.report(
                {"ERROR"},
                f"Bundle too large: {total_size_mb:.0f}MB exceeds limit of {max_bundle_size_mb}MB. "
                f"Try selecting fewer assets or increase the limit in addon preferences.",
            )
            return {"CANCELLED"}

        if total_size_mb > VERY_LARGE_BUNDLE_WARNING_MB:
            self.report(
                {"WARNING"},
                f"Very large selection ({total_size_mb / 1024:.1f}GB). "
                "This may take a very long time and use significant RAM.",
            )

        output_name = props.output_name if props.output_name else "AssetBundle"
        output_name = sanitize_name(output_name)
        date_str = datetime.now().strftime("%Y-%m-%d")

        try:
            save_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.report({"ERROR"}, f"Could not create output directory: {e}")
            return {"CANCELLED"}

        target_path = increment_filename(
            save_path, f"{output_name}_{date_str}", ".blend"
        )

        duplicate_mode = props.duplicate_mode
        total_assets = len(selected_assets)

        print(f"Importing {total_assets} asset files...")

        wm.progress_begin(0, total_assets)
        
        imported_count = 0
        skipped_count = 0
        error_count = 0

        try:
            for i, asset_path in enumerate(selected_assets):
                wm.progress_update(i)
                try:
                    result = self._import_asset_file(asset_path, duplicate_mode)
                    if result is None or result is False:
                        skipped_count += 1
                    else:
                        imported_count += 1
                except (RuntimeError, OSError, IOError, MemoryError) as e:
                    error_count += 1
                    print(f"  ✗ Fatal error importing '{asset_path.name}': {e}")
                    continue
            
            print("\nImport Summary:")
            print(f"  Successfully imported: {imported_count} files")
            if skipped_count > 0:
                print(f"  Skipped (incompatible): {skipped_count} files")
            if error_count > 0:
                print(f"  Failed with errors: {error_count} files")
                
        except (RuntimeError, OSError, MemoryError) as e:
            wm.progress_end()
            self.report({"ERROR"}, f"Failed to import assets: {e}")
            import traceback
            traceback.print_exc()
            return {"CANCELLED"}
        finally:
            wm.progress_end()

        try:
            print(f"Saving bundle to: {target_path}")
            bpy.ops.wm.save_as_mainfile(filepath=str(target_path), copy=True)
            print("Bundle saved successfully")
        except (RuntimeError, OSError) as e:
            self.report({"ERROR"}, f"Failed to save bundle: {e}")
            return {"CANCELLED"}

        if props.copy_catalog:
            self._copy_catalog_file(library_path, target_path, output_name)

        if skipped_count > 0 and imported_count > 0:
            self.report(
                {"WARNING"}, 
                f"Bundle saved: {target_path.name} ({imported_count} imported, {skipped_count} skipped due to version incompatibility)"
            )
            props.show_success_message = True
            props.success_message_time = time.time()
        elif skipped_count > 0 and imported_count == 0:
            self.report(
                {"ERROR"},
                f"No assets could be imported - all {skipped_count} files are incompatible with this Blender version"
            )
            return {"CANCELLED"}
        else:
            self.report({"INFO"}, f"Bundle saved: {target_path.name} ({imported_count} assets)")
            props.show_success_message = True
            props.success_message_time = time.time()
        
        return {"FINISHED"}

    def _calculate_total_size(self, asset_paths):
        """Calculate the total size of all asset files in megabytes."""
        total_bytes = 0
        for asset_path in asset_paths:
            try:
                if asset_path.exists():
                    total_bytes += asset_path.stat().st_size
            except (OSError, PermissionError) as e:
                print(f"Could not get size of {asset_path.name}: {e}")
            except Exception as e:
                print(f"Unexpected error getting size of {asset_path.name}: {e}")

        return total_bytes / (1024 * 1024)

    def _collect_selected_assets(self, context):
        """Collect absolute paths of selected asset files."""
        selected_assets = []
        asset_blend_files = set()

        active_library = self._get_active_library(context)
        if not active_library:
            debug_print("Could not get active library")
            return selected_assets

        library_path = Path(active_library.path)
        debug_print(f"Library path: {library_path}")

        asset_files = None

        if hasattr(context, "selected_asset_files"):
            asset_files = context.selected_asset_files
            debug_print(f"Using selected_asset_files: {len(asset_files)} items")
        elif hasattr(context, "selected_assets"):
            asset_files = context.selected_assets
            debug_print(f"Using selected_assets: {len(asset_files)} items")
        elif hasattr(context.space_data, "files"):
            try:
                asset_files = [f for f in context.space_data.files if f.select]
                debug_print(f"Using space_data.files: {len(asset_files)} items")
            except (AttributeError, TypeError) as e:
                print(f"Error getting files: {e}")

        if not asset_files:
            debug_print("No asset files found")
            return selected_assets

        for asset_file in asset_files:
            asset_path = None

            if hasattr(asset_file, "full_library_path"):
                full_path = asset_file.full_library_path
                if full_path:
                    asset_path = Path(full_path)
                    debug_print(f"Using full_library_path: {asset_path}")

            if not asset_path and hasattr(asset_file, "full_path"):
                full_path = asset_file.full_path
                if full_path:
                    asset_path = Path(full_path)
                    debug_print(f"Using full_path: {asset_path}")

            if not asset_path and hasattr(asset_file, "relative_path"):
                asset_path = library_path / asset_file.relative_path
                debug_print(f"Using relative_path: {asset_file.relative_path}")

            if not asset_path and hasattr(asset_file, "name"):
                file_name = asset_file.name
                debug_print(f"Fallback: trying name-based path for: {file_name}")

                if not file_name.endswith(".blend"):
                    asset_path = library_path / f"{file_name}.blend"
                else:
                    asset_path = library_path / file_name

            if asset_path:
                debug_print(f"Checking path: {asset_path}")

                if asset_path.exists():
                    if asset_path.is_file() and asset_path.suffix.lower() == ".blend":
                        try:
                            file_size = asset_path.stat().st_size
                            if file_size > MIN_BLEND_FILE_SIZE:
                                asset_blend_files.add(asset_path)
                                debug_print(f"✓ Added asset: {asset_path.name} ({file_size} bytes)")
                            else:
                                print(f"⚠ Skipping {asset_path.name}: File too small ({file_size} bytes, minimum {MIN_BLEND_FILE_SIZE})")
                        except OSError as e:
                            print(f"⚠ Cannot access {asset_path.name}: {e}")
                    elif asset_path.is_dir():
                        debug_print(f"✗ Is a directory, not a file: {asset_path}")
                    else:
                        debug_print(f"✗ Not a .blend file: {asset_path.suffix}")
                else:
                    debug_print(f"✗ Path does not exist: {asset_path}")
                    if asset_path.parent.exists():
                        debug_print(f"   Parent directory exists: {asset_path.parent}")
                        try:
                            actual_files = list(asset_path.parent.glob("*.blend"))
                            if actual_files:
                                debug_print(f"   Found {len(actual_files)} .blend files in parent directory")
                        except OSError:
                            pass

        selected_assets = list(asset_blend_files)
        debug_print(f"Total unique .blend files found: {len(selected_assets)}")

        return selected_assets

    def _get_active_library(self, context):
        """Get the active asset library object."""
        prefs = context.preferences

        if not hasattr(prefs, "filepaths"):
            debug_print("No filepaths in preferences")
            return None

        if not hasattr(prefs.filepaths, "asset_libraries"):
            debug_print("No asset_libraries in filepaths")
            return None

        params = None
        if hasattr(context.space_data, "params"):
            params = context.space_data.params
        elif hasattr(context.area.spaces, "active"):
            params = context.area.spaces.active.params

        if not params:
            debug_print("Could not get params")
            return None

        asset_lib_ref = None
        if hasattr(params, "asset_library_reference"):
            asset_lib_ref = params.asset_library_reference
            debug_print(f"Found asset_library_reference: {asset_lib_ref}")
        elif hasattr(params, "asset_library_ref"):
            asset_lib_ref = params.asset_library_ref
            debug_print(f"Found asset_library_ref: {asset_lib_ref}")

        if not asset_lib_ref:
            debug_print("No asset library reference found")
            return None

        for lib in prefs.filepaths.asset_libraries:
            if hasattr(lib, "name") and lib.name == asset_lib_ref:
                debug_print(f"Found library: {lib.name} at {lib.path}")
                return lib

        debug_print(f"No matching library found for: {asset_lib_ref}")
        return None

    def _validate_asset_file(self, asset_path):
        """Validate that an asset file is suitable for import."""
        if not asset_path.exists():
            return False, f"File does not exist: {asset_path}"
        
        if not asset_path.is_file():
            return False, f"Not a file: {asset_path}"
        
        if asset_path.suffix.lower() != ".blend":
            return False, f"Not a .blend file: {asset_path}"
        
        try:
            file_size = asset_path.stat().st_size
            if file_size < MIN_BLEND_FILE_SIZE:
                return False, f"File too small ({file_size} bytes), possibly corrupted (minimum {MIN_BLEND_FILE_SIZE} bytes)"
        except OSError as e:
            return False, f"Cannot access file: {e}"
        
        return True, None

    def _import_asset_file(self, asset_path, duplicate_mode):
        """Import datablocks from a .blend file, preserving asset status."""
        print(f"  Importing: {asset_path.name}")
        
        is_valid, error_msg = self._validate_asset_file(asset_path)
        if not is_valid:
            print(f"  ✗ Skipping: {error_msg}")
            return False

        skip_collections = {
            "workspaces",
            "screens",
            "window_managers",
            "scenes",
            "version",
            "filepath",
            "is_dirty",
            "is_saved",
            "use_autopack",
        }

        try:
            with bpy.data.libraries.load(str(asset_path), link=False) as (
                data_from,
                data_to,
            ):
                for attr in dir(data_from):
                    if attr.startswith("_") or attr in skip_collections:
                        continue

                    try:
                        source_collection = getattr(data_from, attr, None)
                        if source_collection and len(source_collection) > 0:
                            items_to_import = []

                            for item_name in source_collection:
                                if duplicate_mode == "OVERWRITE":
                                    self._remove_existing_datablock(attr, item_name)

                                items_to_import.append(item_name)

                            if items_to_import:
                                setattr(data_to, attr, items_to_import)
                    except (AttributeError, TypeError, KeyError, RuntimeError) as e:
                        debug_print(f"Skipping collection '{attr}': {e}")
                    except (ValueError, MemoryError) as e:
                        print(f"Unexpected error processing collection '{attr}': {e}")
        except (OSError, IOError, RuntimeError) as e:
            error_msg = str(e)
            if "not a blend file" in error_msg.lower() or "failed to read blend file" in error_msg.lower():
                print(f"  ⚠ Skipping '{asset_path.name}': Incompatible blend file version")
                print("     (This file may have been created in a newer version of Blender)")
                return False
            else:
                print(f"  ✗ Error loading blend file '{asset_path.name}': {e}")
                print(f"     Full path: {asset_path}")
                raise
        
        return True

    def _remove_existing_datablock(self, collection_name, item_name):
        """Remove an existing datablock if OVERWRITE mode is active."""
        try:
            collection = getattr(bpy.data, collection_name, None)
            if collection and item_name in collection:
                datablock = collection[item_name]
                collection.remove(datablock)
        except (RuntimeError, ReferenceError, KeyError) as e:
            debug_print(f"Could not remove existing datablock {item_name}: {e}")

    def _copy_catalog_file(self, library_path, target_path, output_name):
        """Copy the catalog definition file next to the bundle."""
        catalog_source = library_path / "blender_assets.cats.txt"

        if not catalog_source.exists():
            print(f"No catalog file found at {catalog_source}")
            return

        catalog_dest = increment_filename(
            target_path.parent, f"{output_name}.blender_assets.cats", ".txt"
        )

        try:
            shutil.copy(catalog_source, catalog_dest)
            print(f"Catalog file copied to {catalog_dest}")
        except (OSError, IOError, shutil.Error) as e:
            print(f"Warning: Could not copy catalog file: {e}")


class QAS_OT_open_bundle_folder(Operator):
    """Open the folder where bundles are saved."""

    bl_idname = "qas.open_bundle_folder"
    bl_label = "Open Bundle Folder"
    bl_description = "Open the folder where asset bundles are saved"

    def execute(self, context):
        """Open the bundle save folder in the system file browser."""
        wm = context.window_manager
        props = wm.qas_bundler_props

        folder_path = props.save_path if props.save_path else str(Path.home())

        if not Path(folder_path).exists():
            self.report({"WARNING"}, "Folder does not exist yet")
            return {"CANCELLED"}

        bpy.ops.wm.path_open(filepath=folder_path)
        return {"FINISHED"}


classes = (
    QAS_OT_bundle_assets,
    QAS_OT_open_bundle_folder,
)
