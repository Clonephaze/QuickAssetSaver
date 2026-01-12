"""
Move operator for Quick Asset Saver.
Handles moving assets between libraries with full companion file support.
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
    ALL_DATABLOCK_COLLECTIONS,
    ASSET_DATABLOCK_COLLECTIONS,
)
from .catalog import get_catalog_path_from_uuid
from .file_io import (
    collect_selected_assets_with_names,
    count_assets_in_blend,
    write_blend_file,
)


def _should_cleanup_empty_folder(folder_path):
    """Check if a folder is empty or only contains hidden/system files.
    
    Returns True if the folder should be sent to recycle bin.
    
    CRITICAL: NEVER returns True for folders containing blender_assets.cats.txt
    or any library root folder. This protects catalog definitions.
    """
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


def get_addon_preferences():
    """Get the addon preferences object."""
    addon = bpy.context.preferences.addons.get(__package__.rsplit('.', 1)[0], None)
    if addon:
        return addon.preferences
    return None


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
                            debug_print("[Move Debug] Successfully updated catalog")
                        else:
                            skipped += 1
                            debug_print("[Move Debug] Failed to update catalog")
                        continue
                    
                    if dest.exists():
                        dest = increment_filename(dest.parent, dest.stem, dest.suffix)
                    
                    success = self._move_file_with_companions(
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

    # -------------------------------------------------------------------------
    # Companion File Detection
    # -------------------------------------------------------------------------

    def _has_companion_files(self, src_path):
        """Check if the source .blend file has any companion files or folders.
        
        Returns True if there are textures, thumbnails, metadata files, etc.
        that should be moved along with the .blend file.
        
        Only detects files/folders that are SPECIFIC to this asset, not general
        library files like blender_assets.cats.txt.
        """
        stem = src_path.stem
        parent = src_path.parent
        
        # Files that are NEVER companions - they belong to the library
        protected_files = {'blender_assets.cats.txt'}
        
        # Check for thumbnails
        for ext in THUMBNAIL_EXTENSIONS:
            if (parent / f"{stem}{ext}").exists():
                return True
            if (parent / f"thumbnail{ext}").exists():
                return True
        
        # Check for asset-named subfolder (e.g., asset_name/ folder for an asset_name.blend)
        if (parent / stem).is_dir():
            return True
        
        # Check for asset-specific metadata files (must contain asset name)
        for ext in METADATA_EXTENSIONS:
            # Check for exact stem match (e.g., asset_name.json)
            if (parent / f"{stem}{ext}").exists():
                return True
            # Check for stem-prefixed files (e.g., asset_name_info.json)
            for f in parent.glob(f"{stem}*{ext}"):
                if f.is_file() and f.name not in protected_files:
                    return True
        
        # NOTE: We intentionally do NOT check for generic companion folders like
        # textures/, materials/, etc. at the parent level because those could be
        # catalog folders, not asset companions. Only asset-named subfolders count.
        
        return False

    # -------------------------------------------------------------------------
    # File Moving
    # -------------------------------------------------------------------------

    def _move_file_with_companions(self, src_path, dest_path, asset_names, catalog_uuid):
        """Move asset file by copying the entire .blend file to preserve all data.
        
        This preserves the complete .blend file structure including:
        - Non-asset datablocks (backup data, reference objects, etc.)
        - Custom scene structures and hierarchies  
        - File-level settings and metadata
        - Packed textures and external dependencies
        - Any other data the user has stored in the file
        
        If the asset has companion files (textures, thumbnails, metadata), 
        everything is placed in a subfolder named after the .blend file to
        keep assets organized and avoid folder name conflicts.
        
        Note: Catalog assignment is NOT updated during move to preserve file integrity.
        """
        has_companions = False
        try:
            has_companions = self._has_companion_files(src_path)
            
            if has_companions:
                # Create a subfolder for this asset to keep everything organized
                asset_folder = dest_path.parent / dest_path.stem
                asset_folder.mkdir(parents=True, exist_ok=True)
                actual_dest = asset_folder / dest_path.name
                debug_print(f"Asset has companions, creating folder: {asset_folder.name}/")
            else:
                actual_dest = dest_path
                dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy the entire .blend file to preserve all data
            shutil.copy2(str(src_path), str(actual_dest))
            debug_print(f"Copied {src_path.name} to {actual_dest}")
            
            # Copy ALL companion files and folders
            if has_companions:
                self._copy_companion_files(src_path, actual_dest)
            
            # Update catalog - this rewrites the file but preserves all datablocks
            # catalog_uuid can be empty string for "Unassigned"
            if catalog_uuid is not None:
                try:
                    success = self._update_catalog_in_blend(
                        actual_dest, 
                        catalog_uuid, 
                        target_names=asset_names
                    )
                    if success:
                        debug_print(f"Updated catalog for {len(asset_names)} asset(s) in {actual_dest.name}")
                    else:
                        debug_print(f"Warning: Could not update catalog in {actual_dest.name}")
                except Exception as e:
                    debug_print(f"Warning: Catalog update failed: {e}")
            
            # Only trash source after successful copy
            if actual_dest.exists():
                source_parent = src_path.parent
                self._trash_source_with_companions(src_path)
                
                # Check if source folder is now empty and clean it up
                if _should_cleanup_empty_folder(source_parent):
                    try:
                        send2trash(str(source_parent))
                        debug_print(f"Cleaned up empty source folder: {source_parent}")
                    except Exception as e:
                        debug_print(f"Could not cleanup empty folder {source_parent}: {e}")
                
                return True
            
            return False
            
        except Exception as e:
            print(f"Error moving file: {e}")
            import traceback
            traceback.print_exc()
            
            # Clean up partial copy on failure
            if has_companions:
                asset_folder = dest_path.parent / dest_path.stem
                if asset_folder.exists():
                    try:
                        shutil.rmtree(str(asset_folder))
                    except OSError:
                        pass
            elif dest_path.exists():
                try:
                    dest_path.unlink()
                except OSError:
                    pass
            return False

    # -------------------------------------------------------------------------
    # Companion File Copying
    # -------------------------------------------------------------------------
    
    def _copy_companion_files(self, src_path, dest_path):
        """Copy companion files and folders alongside the blend file.
        
        Only copies files that are SPECIFIC to this asset:
        - Thumbnails: {stem}.png, thumbnail.webp, etc.
        - Asset-named subfolders: {stem}/
        - Asset-specific metadata: {stem}.json, {stem}_info.txt, etc.
        
        Does NOT copy:
        - Library files (blender_assets.cats.txt)
        - Generic folders that might be catalog paths (textures/, materials/, etc.)
        """
        src_stem = src_path.stem
        dest_stem = dest_path.stem
        src_parent = src_path.parent
        dest_parent = dest_path.parent
        
        # Files that should NEVER be copied
        protected_files = {'blender_assets.cats.txt'}
        
        # Copy thumbnails - both stem-named and generic "thumbnail" named
        for ext in THUMBNAIL_EXTENSIONS:
            # Check for stem-named thumbnails (e.g., brick_floor_003.png)
            src_thumbnail = src_parent / f"{src_stem}{ext}"
            if src_thumbnail.exists():
                dest_thumbnail = dest_parent / f"{dest_stem}{ext}"
                try:
                    shutil.copy2(str(src_thumbnail), str(dest_thumbnail))
                    debug_print(f"Copied thumbnail: {src_thumbnail.name} -> {dest_thumbnail.name}")
                except Exception as e:
                    debug_print(f"Warning: Could not copy thumbnail {src_thumbnail.name}: {e}")
            
            # Check for generic "thumbnail" named files (e.g., thumbnail.webp)
            src_thumbnail = src_parent / f"thumbnail{ext}"
            if src_thumbnail.exists():
                dest_thumbnail = dest_parent / f"thumbnail{ext}"
                try:
                    shutil.copy2(str(src_thumbnail), str(dest_thumbnail))
                    debug_print(f"Copied thumbnail: {src_thumbnail.name}")
                except Exception as e:
                    debug_print(f"Warning: Could not copy thumbnail {src_thumbnail.name}: {e}")
        
        # Copy asset-named subfolder if it exists (e.g., brick_floor_003/)
        src_asset_folder = src_parent / src_stem
        if src_asset_folder.exists() and src_asset_folder.is_dir():
            dest_asset_folder = dest_parent / dest_stem
            try:
                shutil.copytree(str(src_asset_folder), str(dest_asset_folder))
                debug_print(f"Copied asset folder: {src_stem}/")
            except Exception as e:
                debug_print(f"Warning: Could not copy asset folder {src_stem}/: {e}")
        
        # Copy asset-specific metadata files (must match asset name)
        for ext in METADATA_EXTENSIONS:
            # Exact match (e.g., asset_name.json)
            src_file = src_parent / f"{src_stem}{ext}"
            if src_file.exists() and src_file.is_file():
                dest_file = dest_parent / f"{dest_stem}{ext}"
                try:
                    shutil.copy2(str(src_file), str(dest_file))
                    debug_print(f"Copied metadata: {src_file.name}")
                except Exception as e:
                    debug_print(f"Warning: Could not copy {src_file.name}: {e}")
            
            # Prefixed files (e.g., asset_name_info.json) - but not catalog files
            for src_file in src_parent.glob(f"{src_stem}_*{ext}"):
                if src_file.is_file() and src_file.name not in protected_files:
                    # Preserve the suffix part of the filename
                    suffix = src_file.name[len(src_stem):]
                    dest_file = dest_parent / f"{dest_stem}{suffix}"
                    try:
                        shutil.copy2(str(src_file), str(dest_file))
                        debug_print(f"Copied metadata: {src_file.name}")
                    except Exception as e:
                        debug_print(f"Warning: Could not copy {src_file.name}: {e}")

    # -------------------------------------------------------------------------
    # Source Cleanup (Trash)
    # -------------------------------------------------------------------------
    
    def _trash_source_with_companions(self, src_path):
        """Send source file and companion resources to recycle bin.
        
        Trashes:
        - The .blend file itself
        - Thumbnails: {stem}.png, thumbnail.webp, etc.
        - Common asset folders: textures/, maps/, materials/, shaders/, images/,
          hdri/, references/, documentation/, resources/
        - Asset-named subfolders: {stem}/
        - Metadata files: *.json, *.txt, *.md, *.xml
        """
        items_to_trash = [src_path]
        
        stem = src_path.stem
        parent = src_path.parent
        
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

    # -------------------------------------------------------------------------
    # Asset Extraction (from multi-asset files)
    # -------------------------------------------------------------------------

    def _extract_asset_to_file(self, src_path, asset_name, dest_path, catalog_uuid):
        """Extract a single asset from a multi-asset file into a new file.
        
        Note: This creates a NEW file containing only the extracted asset.
        The extracted file will NOT contain any non-asset data from the source.
        The source file is preserved with all its original data intact.
        """
        try:
            target_collection = None
            with bpy.data.libraries.load(str(src_path), link=False, assets_only=True) as (data_from, data_to):
                for collection_name in ASSET_DATABLOCK_COLLECTIONS:
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
            
            # Set catalog - use null UUID for Unassigned
            if catalog_uuid == "" or catalog_uuid is None:
                target_db.asset_data.catalog_id = "00000000-0000-0000-0000-000000000000"
            elif catalog_uuid:
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
        """Remove an asset marking from the source file after extraction.
        
        Preserves ALL data in the source .blend file by importing all datablock
        types, then just clearing the asset status on the specified datablock.
        """
        try:
            # Use ALL datablock collections to preserve complete file contents
            names_to_import = {}
            with bpy.data.libraries.load(str(src_path), link=False, assets_only=False) as (data_from, data_to):
                for collection_name in ALL_DATABLOCK_COLLECTIONS:
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
                            
                            # Only clear asset status on the extracted asset
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

    # -------------------------------------------------------------------------
    # Catalog Update (for same-location moves)
    # -------------------------------------------------------------------------

    def _update_catalog_in_blend(self, blend_path, catalog_uuid, target_names=None):
        """Update catalog on specific assets (or all if target_names is None).
        
        Preserves ALL data in the .blend file by importing all datablock types,
        not just asset-related ones. This ensures non-asset data, custom structures,
        backup objects, etc. are maintained.
        
        Args:
            blend_path: Path to the .blend file
            catalog_uuid: UUID string for the target catalog
            target_names: List of asset names to update, or None for all
            
        Returns:
            bool: True if successful
        """
        try:
            # Use ALL datablock collections to preserve complete file contents
            names_to_import = {}
            with bpy.data.libraries.load(str(blend_path), link=False, assets_only=False) as (data_from, data_to):
                for collection_name in ALL_DATABLOCK_COLLECTIONS:
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
                            
                            # Only update catalog on asset datablocks
                            if hasattr(db, 'asset_data') and db.asset_data:
                                if target_names is None or name in target_names:
                                    # Use null UUID for Unassigned, otherwise use the provided UUID
                                    # Blender uses "00000000-0000-0000-0000-000000000000" for unassigned
                                    if catalog_uuid == "" or catalog_uuid is None:
                                        db.asset_data.catalog_id = "00000000-0000-0000-0000-000000000000"
                                    else:
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

    # -------------------------------------------------------------------------
    # Datablock Cleanup
    # -------------------------------------------------------------------------

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


classes = (
    QAS_OT_move_selected_to_library,
)
