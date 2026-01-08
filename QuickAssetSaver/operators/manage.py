"""
Asset management operators for Quick Asset Saver.
Move and delete operations.
"""

import shutil
from pathlib import Path

import bpy
from bpy.types import Operator

try:
    from send2trash import send2trash
except ImportError:
    def send2trash(path):
        import os
        os.remove(path)

from .utils import (
    debug_print,
    sanitize_name,
    increment_filename,
    refresh_asset_browser,
)
from .catalog import get_catalog_path_from_uuid
from .file_io import (
    collect_selected_assets_with_names,
    count_assets_in_blend,
    write_blend_file,
)


def get_addon_preferences():
    """Get the addon preferences object."""
    addon = bpy.context.preferences.addons.get(__package__.rsplit('.', 1)[0], None)
    if addon:
        return addon.preferences
    return None


class QAS_OT_move_selected_to_library(Operator):
    """Move selected assets to another library - handles multi-asset files correctly."""

    bl_idname = "qas.move_selected_to_library"
    bl_label = "Move Assets"
    bl_description = "Move selected assets to the target library (extracts from multi-asset files)"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return (
            hasattr(context, "space_data")
            and context.space_data.type == "FILE_BROWSER"
            and getattr(context.space_data, "browse_mode", None) == "ASSETS"
        )

    def execute(self, context):
        from ..properties import get_library_by_identifier

        prefs = get_addon_preferences()
        wm = context.window_manager
        manage = getattr(wm, "qas_manage_props", None)
        if not manage:
            self.report({"ERROR"}, "Internal properties missing")
            return {"CANCELLED"}

        selected_assets, active_library = collect_selected_assets_with_names(context)
        if not selected_assets:
            self.report({"WARNING"}, "No assets selected")
            return {"CANCELLED"}

        if not manage.move_target_library or manage.move_target_library == "NONE":
            self.report({"ERROR"}, "Please choose a target library")
            return {"CANCELLED"}

        target_name, target_path_str = get_library_by_identifier(manage.move_target_library)
        if not target_path_str:
            self.report({"ERROR"}, "Target library path not found")
            return {"CANCELLED"}

        target_root = Path(target_path_str)
        if not target_root.exists():
            try:
                target_root.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                self.report({"ERROR"}, f"Cannot access target library: {e}")
                return {"CANCELLED"}

        target_catalog_uuid = manage.move_target_catalog if manage.move_target_catalog else "UNASSIGNED"
        
        debug_print(f"[Move Debug] Target catalog UUID: {target_catalog_uuid}")
        
        dest_base = target_root
        if prefs and prefs.use_catalog_subfolders and target_catalog_uuid != "UNASSIGNED":
            catalog_path = get_catalog_path_from_uuid(str(target_root), target_catalog_uuid)
            if catalog_path:
                for part in [p for p in catalog_path.split("/") if p]:
                    dest_base = dest_base / sanitize_name(part, max_length=64)

        try:
            dest_base.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.report({"ERROR"}, f"Could not create destination folders: {e}")
            return {"CANCELLED"}

        moved = 0
        extracted = 0
        skipped = 0
        
        files_to_process = {}
        for asset in selected_assets:
            path = asset['path']
            if path not in files_to_process:
                files_to_process[path] = {
                    'asset_info': count_assets_in_blend(path),
                    'selected_assets': []
                }
            files_to_process[path]['selected_assets'].append(asset['name'])
        
        catalog_to_set = "" if target_catalog_uuid == "UNASSIGNED" else target_catalog_uuid
        
        debug_print(f"[Move Debug] catalog_to_set: '{catalog_to_set}'")
        
        for src_path, info in files_to_process.items():
            total_assets = info['asset_info']['count']
            selected_names = info['selected_assets']
            
            debug_print(f"[Move Debug] Processing {src_path.name}: {total_assets} total, {len(selected_names)} selected")
            
            try:
                if total_assets <= 1 or len(selected_names) >= total_assets:
                    dest = dest_base / src_path.name
                    
                    same_location = False
                    try:
                        same_location = src_path.resolve() == dest.resolve()
                    except Exception:
                        pass
                    
                    debug_print(f"[Move Debug] Same location check: {same_location}, catalog_to_set: {catalog_to_set}")
                    
                    if same_location:
                        debug_print(f"[Move Debug] Updating catalog in place for {src_path.name} to '{catalog_to_set}'")
                        success = self._update_catalog_in_blend(
                            src_path, catalog_to_set, selected_names
                        )
                        if success:
                            moved += 1
                            debug_print(f"[Move Debug] Successfully updated catalog")
                        else:
                            skipped += 1
                            debug_print(f"[Move Debug] Failed to update catalog")
                        continue
                    
                    if dest.exists():
                        dest = increment_filename(dest.parent, dest.stem, dest.suffix)
                    
                    success = self._move_file_with_packing(
                        src_path, dest, selected_names, catalog_to_set
                    )
                    
                    if success:
                        moved += 1
                    else:
                        skipped += 1
                else:
                    for asset_name in selected_names:
                        try:
                            dest_filename = f"{sanitize_name(asset_name)}.blend"
                            dest = dest_base / dest_filename
                            
                            if dest.exists():
                                dest = increment_filename(dest.parent, sanitize_name(asset_name), ".blend")
                            
                            success = self._extract_asset_to_file(
                                src_path, asset_name, dest, catalog_to_set
                            )
                            
                            if success:
                                self._remove_asset_from_source(src_path, asset_name)
                                extracted += 1
                            else:
                                skipped += 1
                        except Exception as e:
                            print(f"Failed to extract {asset_name}: {e}")
                            skipped += 1
                            
            except Exception as e:
                print(f"Failed to process {src_path.name}: {e}")
                skipped += len(selected_names)

        refresh_asset_browser(context)

        msg_parts = []
        if moved:
            msg_parts.append(f"moved {moved} file(s)")
        if extracted:
            msg_parts.append(f"extracted {extracted} asset(s)")
        if skipped:
            msg_parts.append(f"skipped {skipped}")
        
        self.report({"INFO"}, ", ".join(msg_parts) if msg_parts else "No changes made")
        return {"FINISHED"}

    def _move_file_with_packing(self, src_path, dest_path, asset_names, catalog_uuid):
        """Move asset file by re-saving with all external resources packed."""
        datablock_collections = [
            'objects', 'materials', 'node_groups', 'worlds', 'collections',
            'meshes', 'curves', 'armatures', 'actions', 'brushes', 'scenes',
        ]
        
        imported_datablocks = []
        renamed_existing = []
        
        try:
            targets_to_import = {}
            with bpy.data.libraries.load(str(src_path), link=False, assets_only=True) as (data_from, data_to):
                for asset_name in asset_names:
                    for collection_name in datablock_collections:
                        if hasattr(data_from, collection_name):
                            source = getattr(data_from, collection_name)
                            if source and asset_name in source:
                                if collection_name not in targets_to_import:
                                    targets_to_import[collection_name] = []
                                targets_to_import[collection_name].append(asset_name)
                                break
            
            if not targets_to_import:
                print(f"No assets found in {src_path.name}")
                return False
            
            for collection_name, names in targets_to_import.items():
                if hasattr(bpy.data, collection_name):
                    collection = getattr(bpy.data, collection_name)
                    for name in names:
                        name_str = str(name)
                        if name_str in collection:
                            existing_db = collection[name_str]
                            temp_name = f"__QAS_MOVE_TEMP_{name_str}_{id(existing_db)}"
                            original_name = existing_db.name
                            existing_db.name = temp_name
                            renamed_existing.append((existing_db, original_name))
            
            with bpy.data.libraries.load(str(src_path), link=False, assets_only=False) as (data_from, data_to):
                for collection_name, names in targets_to_import.items():
                    setattr(data_to, collection_name, [str(n) for n in names])
            
            for collection_name, names in targets_to_import.items():
                if hasattr(bpy.data, collection_name):
                    collection = getattr(bpy.data, collection_name)
                    for name in names:
                        name_str = str(name)
                        if name_str in collection:
                            db = collection[name_str]
                            if db.asset_data:
                                imported_datablocks.append(db)
                                if catalog_uuid:
                                    db.asset_data.catalog_id = catalog_uuid
            
            if not imported_datablocks:
                print(f"Failed to import any assets from {src_path.name}")
                for existing_db, original_name in renamed_existing:
                    try:
                        existing_db.name = original_name
                    except Exception:
                        pass
                return False
            
            success = write_blend_file(str(dest_path), set(imported_datablocks))
            
            if success and dest_path.exists():
                self._trash_source_with_companions(src_path)
            
            for db in imported_datablocks:
                self._remove_datablock(db)
            
            for existing_db, original_name in renamed_existing:
                try:
                    existing_db.name = original_name
                except Exception:
                    pass
            
            return success and dest_path.exists()
            
        except Exception as e:
            print(f"Error moving file with packing: {e}")
            import traceback
            traceback.print_exc()
            
            for db in imported_datablocks:
                try:
                    self._remove_datablock(db)
                except Exception:
                    pass
            for existing_db, original_name in renamed_existing:
                try:
                    existing_db.name = original_name
                except Exception:
                    pass
            return False
    
    def _trash_source_with_companions(self, src_path):
        """Send source file and companion resources to recycle bin."""
        items_to_trash = [src_path]
        
        stem = src_path.stem
        parent = src_path.parent
        
        thumbnail_extensions = ['.png', '.webp', '.jpg', '.jpeg']
        for ext in thumbnail_extensions:
            thumbnail_path = parent / f"{stem}{ext}"
            if thumbnail_path.exists():
                items_to_trash.append(thumbnail_path)
            thumbnail_path = parent / f"thumbnail{ext}"
            if thumbnail_path.exists():
                items_to_trash.append(thumbnail_path)
        
        textures_folder = parent / "textures"
        if textures_folder.exists() and textures_folder.is_dir():
            items_to_trash.append(textures_folder)
        
        asset_folder = parent / stem
        if asset_folder.exists() and asset_folder.is_dir():
            items_to_trash.append(asset_folder)
        
        for item in items_to_trash:
            try:
                send2trash(str(item))
                debug_print(f"Sent to recycle bin: {item}")
            except Exception as e:
                print(f"Warning: Could not trash {item}: {e}")
                try:
                    if item.is_dir():
                        shutil.rmtree(str(item))
                    else:
                        item.unlink()
                except Exception:
                    pass

    def _extract_asset_to_file(self, src_path, asset_name, dest_path, catalog_uuid):
        """Extract a single asset from a multi-asset file into a new file."""
        datablock_collections = [
            'objects', 'materials', 'node_groups', 'worlds', 'collections',
            'meshes', 'curves', 'armatures', 'actions', 'brushes', 'scenes', 'scenes',
        ]
        
        try:
            target_collection = None
            with bpy.data.libraries.load(str(src_path), link=False, assets_only=True) as (data_from, data_to):
                for collection_name in datablock_collections:
                    if hasattr(data_from, collection_name):
                        source = getattr(data_from, collection_name)
                        if source and asset_name in source:
                            target_collection = collection_name
                            break
            
            if not target_collection:
                print(f"Asset '{asset_name}' not found in {src_path.name}")
                return False
            
            renamed_existing = []
            if hasattr(bpy.data, target_collection):
                collection = getattr(bpy.data, target_collection)
                if asset_name in collection:
                    existing_db = collection[asset_name]
                    temp_name = f"__QAS_EXTRACT_TEMP_{asset_name}_{id(existing_db)}"
                    original_name = existing_db.name
                    existing_db.name = temp_name
                    renamed_existing.append((existing_db, original_name))
            
            with bpy.data.libraries.load(str(src_path), link=False, assets_only=False) as (data_from, data_to):
                setattr(data_to, target_collection, [asset_name])
            
            target_db = None
            if hasattr(bpy.data, target_collection):
                collection = getattr(bpy.data, target_collection)
                if asset_name in collection:
                    target_db = collection[asset_name]
            
            if not target_db or not target_db.asset_data:
                if target_db:
                    self._remove_datablock(target_db)
                for existing_db, original_name in renamed_existing:
                    try:
                        existing_db.name = original_name
                    except Exception:
                        pass
                return False
            
            if catalog_uuid:
                target_db.asset_data.catalog_id = catalog_uuid
            
            success = write_blend_file(str(dest_path), {target_db})
            
            self._remove_datablock(target_db)
            for existing_db, original_name in renamed_existing:
                try:
                    existing_db.name = original_name
                except Exception:
                    pass
            
            return success and dest_path.exists()
            
        except Exception as e:
            print(f"Error extracting asset: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _remove_asset_from_source(self, src_path, asset_name):
        """Remove an asset from the source file after extraction."""
        datablock_collections = [
            'objects', 'materials', 'node_groups', 'worlds', 'collections',
            'meshes', 'curves', 'armatures', 'actions', 'brushes', 'scenes',
        ]
        
        try:
            names_to_import = {}
            with bpy.data.libraries.load(str(src_path), link=False, assets_only=False) as (data_from, data_to):
                for collection_name in datablock_collections:
                    if hasattr(data_from, collection_name):
                        source = getattr(data_from, collection_name)
                        if source:
                            names_to_import[collection_name] = list(source)
            
            renamed_existing = []
            for collection_name, names in names_to_import.items():
                if hasattr(bpy.data, collection_name):
                    collection = getattr(bpy.data, collection_name)
                    for name in names:
                        if name in collection:
                            existing_db = collection[name]
                            temp_name = f"__QAS_MOVE_TEMP_{name}_{id(existing_db)}"
                            original_name = existing_db.name
                            existing_db.name = temp_name
                            renamed_existing.append((existing_db, original_name))
            
            with bpy.data.libraries.load(str(src_path), link=False, assets_only=False) as (data_from, data_to):
                for collection_name in datablock_collections:
                    if hasattr(data_from, collection_name):
                        source = getattr(data_from, collection_name)
                        if source:
                            setattr(data_to, collection_name, list(source))
            
            imported_datablocks = set()
            for collection_name in names_to_import.keys():
                if hasattr(bpy.data, collection_name):
                    collection = getattr(bpy.data, collection_name)
                    for name in names_to_import[collection_name]:
                        if name in collection:
                            db = collection[name]
                            imported_datablocks.add(db)
                            
                            if name == asset_name and hasattr(db, 'asset_clear'):
                                db.asset_clear()
            
            temp_path = src_path.parent / f".tmp_{src_path.name}"
            bpy.data.libraries.write(
                str(temp_path),
                imported_datablocks,
                path_remap="RELATIVE_ALL",
                fake_user=True,
                compress=True,
            )
            
            for db in list(imported_datablocks):
                self._remove_datablock(db)
            for existing_db, original_name in renamed_existing:
                try:
                    existing_db.name = original_name
                except Exception:
                    pass
            
            if temp_path.exists():
                if src_path.exists():
                    src_path.unlink()
                shutil.move(str(temp_path), str(src_path))
                
        except Exception as e:
            print(f"Error removing asset from source: {e}")

    def _update_catalog_in_blend(self, blend_path, catalog_uuid, target_names=None):
        """Update catalog on specific assets (or all if target_names is None).
        
        Args:
            blend_path: Path to the .blend file
            catalog_uuid: UUID string for the target catalog
            target_names: List of asset names to update, or None for all
            
        Returns:
            bool: True if successful
        """
        try:
            datablock_collections = [
                'objects', 'materials', 'node_groups', 'worlds', 'collections',
                'meshes', 'curves', 'armatures', 'actions', 'brushes', 'scenes',
            ]
            
            names_to_import = {}
            with bpy.data.libraries.load(str(blend_path), link=False, assets_only=False) as (data_from, data_to):
                for collection_name in datablock_collections:
                    if hasattr(data_from, collection_name):
                        source = getattr(data_from, collection_name)
                        if source:
                            names_to_import[collection_name] = list(source)
            
            renamed_existing = []
            for collection_name, names in names_to_import.items():
                if hasattr(bpy.data, collection_name):
                    collection = getattr(bpy.data, collection_name)
                    for name in names:
                        if name in collection:
                            existing_db = collection[name]
                            temp_name = f"__QAS_CAT_TEMP_{name}_{id(existing_db)}"
                            original_name = existing_db.name
                            existing_db.name = temp_name
                            renamed_existing.append((existing_db, original_name))
            
            with bpy.data.libraries.load(str(blend_path), link=False, assets_only=False) as (data_from, data_to):
                for collection_name in datablock_collections:
                    if hasattr(data_from, collection_name):
                        source = getattr(data_from, collection_name)
                        if source:
                            setattr(data_to, collection_name, list(source))
            
            imported_datablocks = set()
            for collection_name in names_to_import.keys():
                if hasattr(bpy.data, collection_name):
                    collection = getattr(bpy.data, collection_name)
                    for name in names_to_import[collection_name]:
                        if name in collection:
                            db = collection[name]
                            imported_datablocks.add(db)
                            
                            if hasattr(db, 'asset_data') and db.asset_data:
                                if target_names is None or name in target_names:
                                    db.asset_data.catalog_id = catalog_uuid
            
            if not imported_datablocks:
                for existing_db, original_name in renamed_existing:
                    try:
                        existing_db.name = original_name
                    except Exception:
                        pass
                return False
            
            temp_path = blend_path.parent / f".tmp_{blend_path.name}"
            bpy.data.libraries.write(
                str(temp_path),
                imported_datablocks,
                path_remap="RELATIVE_ALL",
                fake_user=True,
                compress=True,
            )
            
            for db in list(imported_datablocks):
                self._remove_datablock(db)
            for existing_db, original_name in renamed_existing:
                try:
                    existing_db.name = original_name
                except Exception:
                    pass
            
            if temp_path.exists():
                if blend_path.exists():
                    blend_path.unlink()
                shutil.move(str(temp_path), str(blend_path))
                return True
                
        except (RuntimeError, IOError, OSError) as e:
            print(f"Failed to update catalog in {blend_path.name}: {e}")
            try:
                temp_path = blend_path.parent / f".tmp_{blend_path.name}"
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
        
        return False

    def _remove_datablock(self, datablock):
        """Remove a datablock from the current session."""
        try:
            if isinstance(datablock, bpy.types.Object):
                bpy.data.objects.remove(datablock)
            elif isinstance(datablock, bpy.types.Material):
                bpy.data.materials.remove(datablock)
            elif isinstance(datablock, bpy.types.NodeTree):
                bpy.data.node_groups.remove(datablock)
            elif isinstance(datablock, bpy.types.World):
                bpy.data.worlds.remove(datablock)
            elif isinstance(datablock, bpy.types.Collection):
                bpy.data.collections.remove(datablock)
            elif isinstance(datablock, bpy.types.Mesh):
                bpy.data.meshes.remove(datablock)
            elif isinstance(datablock, bpy.types.Curve):
                bpy.data.curves.remove(datablock)
            elif isinstance(datablock, bpy.types.Armature):
                bpy.data.armatures.remove(datablock)
            elif isinstance(datablock, bpy.types.Action):
                bpy.data.actions.remove(datablock)
            elif isinstance(datablock, bpy.types.Brush):
                bpy.data.brushes.remove(datablock)
        except (RuntimeError, ReferenceError):
            pass


class QAS_OT_delete_selected_assets(Operator):
    """Delete selected assets - handles both single and multi-asset files safely"""

    bl_idname = "qas.delete_selected_assets"
    bl_label = "Delete Selected Assets"
    bl_description = "Delete selected assets (removes from multi-asset files or sends single-asset files to trash)"
    bl_options = {"REGISTER"}
    
    _single_asset_files: list = []
    _multi_asset_entries: list = []

    def invoke(self, context, event):
        self._single_asset_files = []
        self._multi_asset_entries = []
        
        selected_assets, _ = collect_selected_assets_with_names(context)
        if not selected_assets:
            self.report({"WARNING"}, "No assets selected")
            return {"CANCELLED"}
        
        files_analyzed = {}
        for asset in selected_assets:
            path = asset['path']
            if path not in files_analyzed:
                files_analyzed[path] = count_assets_in_blend(path)
            
            asset_count = files_analyzed[path]['count']
            if asset_count <= 1:
                self._single_asset_files.append(path)
            else:
                self._multi_asset_entries.append((path, asset['name'], asset_count))
        
        return context.window_manager.invoke_props_dialog(self, width=480)

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column(align=True)
        
        if self._single_asset_files and not self._multi_asset_entries:
            col.label(text="Move selected files to the trash or recycle bin", icon="TRASH")
            col.label(text=f"Files to delete: {len(self._single_asset_files)}")
        elif self._multi_asset_entries and not self._single_asset_files:
            col.label(text="Remove asset status from selected assets", icon="ASSET_MANAGER")
            col.separator()
            col.label(text="The following assets will be unmarked (file preserved):")
            for path, name, count in self._multi_asset_entries[:5]:
                col.label(text=f"  • {name} (in {path.name}, {count} assets)", icon="DOT")
            if len(self._multi_asset_entries) > 5:
                col.label(text=f"  ... and {len(self._multi_asset_entries) - 5} more")
        else:
            col.label(text="Delete/Remove Selected Assets", icon="TRASH")
            col.separator()
            if self._single_asset_files:
                col.label(text=f"Files to trash: {len(self._single_asset_files)}")
            if self._multi_asset_entries:
                col.label(text=f"Assets to unmark: {len(self._multi_asset_entries)}")
                col.label(text="(Files with multiple assets are preserved)", icon="INFO")

    @classmethod
    def poll(cls, context):
        return (
            hasattr(context, "space_data")
            and context.space_data.type == "FILE_BROWSER"
            and getattr(context.space_data, "browse_mode", None) == "ASSETS"
        )

    def execute(self, context):
        selected_assets, _ = collect_selected_assets_with_names(context)
        if not selected_assets:
            self.report({"WARNING"}, "No assets selected")
            return {"CANCELLED"}

        deleted_files = 0
        unmarked_assets = 0
        failed = 0
        
        files_to_process = {}
        for asset in selected_assets:
            path = asset['path']
            if path not in files_to_process:
                files_to_process[path] = {
                    'asset_info': count_assets_in_blend(path),
                    'selected_assets': []
                }
            files_to_process[path]['selected_assets'].append(asset['name'])
        
        for path, info in files_to_process.items():
            total_assets = info['asset_info']['count']
            selected_names = info['selected_assets']
            
            if total_assets <= 1:
                try:
                    send2trash(str(path))
                    deleted_files += 1
                except Exception as e:
                    print(f"Failed to send {path.name} to trash: {e}")
                    failed += 1
            else:
                try:
                    success = self._remove_assets_from_blend(path, selected_names)
                    if success:
                        unmarked_assets += len(selected_names)
                    else:
                        failed += len(selected_names)
                except Exception as e:
                    print(f"Failed to modify {path.name}: {e}")
                    failed += len(selected_names)

        refresh_asset_browser(context)

        messages = []
        if deleted_files:
            messages.append(f"{deleted_files} file(s) sent to trash")
        if unmarked_assets:
            messages.append(f"{unmarked_assets} asset(s) removed")
        if failed:
            messages.append(f"{failed} failed")
        
        if failed:
            self.report({"WARNING"}, ", ".join(messages))
        else:
            self.report({"INFO"}, ", ".join(messages))
        return {"FINISHED"}
    
    def _remove_assets_from_blend(self, blend_path, asset_names_to_remove):
        """Remove asset status from specific datablocks in a multi-asset .blend file."""
        datablock_collections = [
            'objects', 'materials', 'node_groups', 'worlds', 'collections',
            'meshes', 'curves', 'armatures', 'actions', 'brushes', 'scenes',
        ]
        
        try:
            renamed_existing = []
            
            names_to_import = {}
            with bpy.data.libraries.load(str(blend_path), link=False, assets_only=False) as (data_from, data_to):
                for collection_name in datablock_collections:
                    if hasattr(data_from, collection_name):
                        source = getattr(data_from, collection_name)
                        if source:
                            names_to_import[collection_name] = list(source)
            
            for collection_name, names in names_to_import.items():
                if hasattr(bpy.data, collection_name):
                    collection = getattr(bpy.data, collection_name)
                    for name in names:
                        if name in collection:
                            existing_db = collection[name]
                            temp_name = f"__QAS_DEL_TEMP_{name}_{id(existing_db)}"
                            original_name = existing_db.name
                            existing_db.name = temp_name
                            renamed_existing.append((existing_db, original_name))
            
            with bpy.data.libraries.load(str(blend_path), link=False, assets_only=False) as (data_from, data_to):
                for collection_name in datablock_collections:
                    if hasattr(data_from, collection_name):
                        source = getattr(data_from, collection_name)
                        if source:
                            setattr(data_to, collection_name, list(source))
            
            imported_datablocks = set()
            for collection_name in names_to_import.keys():
                if hasattr(bpy.data, collection_name):
                    collection = getattr(bpy.data, collection_name)
                    for name in names_to_import[collection_name]:
                        if name in collection:
                            db = collection[name]
                            imported_datablocks.add(db)
                            
                            if name in asset_names_to_remove:
                                if hasattr(db, 'asset_clear'):
                                    db.asset_clear()
                                    debug_print(f"Cleared asset status from: {name}")
            
            temp_path = blend_path.parent / f".tmp_{blend_path.name}"
            bpy.data.libraries.write(
                str(temp_path),
                imported_datablocks,
                path_remap="RELATIVE_ALL",
                fake_user=True,
                compress=True,
            )
            
            for db in list(imported_datablocks):
                self._remove_datablock_safe(db)
            
            for existing_db, original_name in renamed_existing:
                try:
                    existing_db.name = original_name
                except Exception:
                    pass
            
            if temp_path.exists():
                if blend_path.exists():
                    blend_path.unlink()
                shutil.move(str(temp_path), str(blend_path))
                return True
                
        except Exception as e:
            print(f"Error removing assets from {blend_path.name}: {e}")
            import traceback
            traceback.print_exc()
            
            try:
                temp_path = blend_path.parent / f".tmp_{blend_path.name}"
                if temp_path.exists():
                    temp_path.unlink()
            except OSError:
                pass
        
        return False
    
    def _remove_datablock_safe(self, datablock):
        """Safely remove a datablock from the current session."""
        try:
            if isinstance(datablock, bpy.types.Object):
                bpy.data.objects.remove(datablock)
            elif isinstance(datablock, bpy.types.Material):
                bpy.data.materials.remove(datablock)
            elif isinstance(datablock, bpy.types.NodeTree):
                bpy.data.node_groups.remove(datablock)
            elif isinstance(datablock, bpy.types.World):
                bpy.data.worlds.remove(datablock)
            elif isinstance(datablock, bpy.types.Collection):
                bpy.data.collections.remove(datablock)
            elif isinstance(datablock, bpy.types.Mesh):
                bpy.data.meshes.remove(datablock)
            elif isinstance(datablock, bpy.types.Curve):
                bpy.data.curves.remove(datablock)
            elif isinstance(datablock, bpy.types.Armature):
                bpy.data.armatures.remove(datablock)
            elif isinstance(datablock, bpy.types.Action):
                bpy.data.actions.remove(datablock)
            elif isinstance(datablock, bpy.types.Brush):
                bpy.data.brushes.remove(datablock)
        except (RuntimeError, ReferenceError):
            pass


classes = (
    QAS_OT_move_selected_to_library,
    QAS_OT_delete_selected_assets,
)
