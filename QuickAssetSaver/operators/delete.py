"""
Delete operator for Quick Asset Saver.
Handles deleting assets from the Asset Browser.
"""

import shutil

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
    refresh_asset_browser,
    ALL_DATABLOCK_COLLECTIONS,
)
from .file_io import (
    collect_selected_assets_with_names,
    count_assets_in_blend,
)


# Common asset companion folder groups (case variations)
COMPANION_FOLDER_GROUPS = [
    ['textures', 'Textures', 'TEXTURES'],
    ['maps', 'Maps', 'MAPS'],
    ['materials', 'Materials', 'MATERIALS'],
    ['shaders', 'Shaders', 'SHADERS'],
    ['images', 'Images', 'IMAGES'],
    ['hdri', 'HDRI', 'hdris', 'HDRIs'],
    ['references', 'References', 'ref', 'Ref'],
    ['documentation', 'Documentation', 'docs', 'Docs'],
    ['resources', 'Resources', 'RESOURCES'],
]

# Flat list of all companion folder names for quick checking
COMPANION_FOLDER_NAMES = [name for group in COMPANION_FOLDER_GROUPS for name in group]

# Thumbnail file extensions
THUMBNAIL_EXTENSIONS = ['.png', '.webp', '.jpg', '.jpeg']

# Metadata file extensions
METADATA_EXTENSIONS = ['.json', '.txt', '.md', '.xml']


def _should_cleanup_empty_folder(folder_path):
    """Check if a folder is empty or only contains hidden/system files.
    
    Returns True if the folder should be sent to recycle bin.
    
    CRITICAL: NEVER returns True for folders containing blender_assets.cats.txt
    or any library root folder. This protects catalog definitions.
    """
    from pathlib import Path
    folder_path = Path(folder_path)
    
    if not folder_path.exists() or not folder_path.is_dir():
        return False
    
    try:
        # NEVER cleanup folders containing catalog files - these are library roots!
        catalog_file = folder_path / "blender_assets.cats.txt"
        if catalog_file.exists():
            debug_print(f"PROTECTED: {folder_path} contains catalog file, will not cleanup")
            return False
        
        # Get all contents
        contents = list(folder_path.iterdir())
        
        # Empty folder - should be cleaned up
        if not contents:
            return True
        
        # Check if only contains hidden/system files
        for item in contents:
            name = item.name
            # Skip hidden files and common system files
            if name.startswith('.') or name.startswith('~') or name in ['desktop.ini', 'Thumbs.db', '.DS_Store']:
                continue
            # Found a real file/folder - don't cleanup
            return False
        
        # Only hidden/system files found - cleanup
        return True
        
    except Exception:
        return False


def _trash_companions_for_file(blend_path):
    """Send companion files for a .blend file to recycle bin.
    
    Trashes:
    - Thumbnails: {stem}.png, thumbnail.webp, etc.
    - Common asset folders: textures/, maps/, materials/, etc.
    - Asset-named subfolders: {stem}/
    - Metadata files: *.json, *.txt, *.md, *.xml
    
    Returns:
        int: Number of companion items trashed
    """
    from pathlib import Path
    blend_path = Path(blend_path)
    items_to_trash = []
    
    stem = blend_path.stem
    parent = blend_path.parent
    
    # Collect thumbnails - both stem-named and generic "thumbnail" named
    for ext in THUMBNAIL_EXTENSIONS:
        thumbnail_path = parent / f"{stem}{ext}"
        if thumbnail_path.exists():
            items_to_trash.append(thumbnail_path)
        thumbnail_path = parent / f"thumbnail{ext}"
        if thumbnail_path.exists():
            items_to_trash.append(thumbnail_path)
    
    # Collect common asset companion folders
    for folder_group in COMPANION_FOLDER_GROUPS:
        for folder_name in folder_group:
            folder_path = parent / folder_name
            if folder_path.exists() and folder_path.is_dir():
                items_to_trash.append(folder_path)
                break  # Only trash one folder per group
    
    # Collect asset-named subfolder
    asset_folder = parent / stem
    if asset_folder.exists() and asset_folder.is_dir():
        items_to_trash.append(asset_folder)
    
    # Collect metadata files - but NEVER touch catalog files!
    protected_files = {'blender_assets.cats.txt'}
    for ext in METADATA_EXTENSIONS:
        for f in parent.glob(f"*{ext}"):
            if f.is_file() and f not in items_to_trash and f.name not in protected_files:
                items_to_trash.append(f)
    
    trashed_count = 0
    for item in items_to_trash:
        try:
            send2trash(str(item))
            debug_print(f"Sent companion to recycle bin: {item}")
            trashed_count += 1
        except Exception as e:
            debug_print(f"Warning: Could not trash {item}: {e}")
            try:
                if item.is_dir():
                    shutil.rmtree(str(item))
                else:
                    item.unlink()
                trashed_count += 1
            except Exception:
                pass
    
    return trashed_count


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
        folders_cleaned = 0
        companions_trashed = 0
        
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
                    parent_folder = path.parent
                    
                    # Trash companion files first
                    companions_count = _trash_companions_for_file(path)
                    companions_trashed += companions_count
                    
                    # Then trash the .blend file itself
                    send2trash(str(path))
                    deleted_files += 1
                    
                    # Check if parent folder is now empty and clean it up
                    if _should_cleanup_empty_folder(parent_folder):
                        try:
                            send2trash(str(parent_folder))
                            folders_cleaned += 1
                            debug_print(f"Cleaned up empty folder: {parent_folder}")
                        except Exception as e:
                            debug_print(f"Could not cleanup empty folder {parent_folder}: {e}")
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
        if companions_trashed:
            messages.append(f"{companions_trashed} companion file(s) removed")
        if folders_cleaned:
            messages.append(f"{folders_cleaned} empty folder(s) cleaned up")
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
        """Remove asset status from specific datablocks in a multi-asset .blend file.
        
        Preserves ALL data in the .blend file by importing all datablock types,
        not just asset-related ones. This ensures non-asset data, custom structures,
        backup objects, etc. are maintained.
        """
        try:
            renamed_existing = []
            
            # Use ALL datablock collections to preserve complete file contents
            names_to_import = {}
            with bpy.data.libraries.load(str(blend_path), link=False, assets_only=False) as (data_from, data_to):
                for collection_name in ALL_DATABLOCK_COLLECTIONS:
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
                for collection_name in ALL_DATABLOCK_COLLECTIONS:
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
                            
                            # Only clear asset status on specified datablocks
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
    
    def _remove_datablock(self, datablock):
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
    QAS_OT_delete_selected_assets,
)
