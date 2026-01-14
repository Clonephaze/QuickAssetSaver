"""
Metadata editing operator for Quick Asset Saver.
"""

import shutil
from pathlib import Path

import bpy
from bpy.types import Operator

from .utils import debug_print, refresh_asset_browser, ALL_DATABLOCK_COLLECTIONS
from .move import THUMBNAIL_EXTENSIONS


class QAS_OT_apply_metadata_changes(Operator):
    """Apply metadata changes to the asset in its source .blend file."""

    bl_idname = "qas.apply_metadata_changes"
    bl_label = "Apply Changes"
    bl_description = "Save metadata changes back to the asset's source file"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        wm = context.window_manager
        meta = getattr(wm, "qas_metadata_edit", None)
        if not meta:
            return False
        return meta.has_changes() and meta.source_file

    def execute(self, context):
        wm = context.window_manager
        meta = wm.qas_metadata_edit
        
        source_path = Path(meta.source_file)
        if not source_path.exists():
            self.report({"ERROR"}, f"Source file not found: {source_path}")
            return {"CANCELLED"}
        
        target_asset_name = meta.asset_name
        new_name = meta.edit_name.strip() if meta.edit_name.strip() else None
        new_description = meta.edit_description
        new_license = meta.edit_license
        new_copyright = meta.edit_copyright
        new_author = meta.edit_author
        
        tag_list = [tag.name.strip() for tag in meta.edit_tags if tag.name.strip()]
        
        try:
            success = self._update_asset_metadata(
                source_path, 
                target_asset_name,
                new_name=new_name,
                new_description=new_description,
                new_license=new_license,
                new_copyright=new_copyright,
                new_author=new_author,
                new_tags=tag_list,
            )
            
            if success:
                meta.orig_name = meta.edit_name
                meta.orig_description = meta.edit_description
                meta.orig_license = meta.edit_license
                meta.orig_copyright = meta.edit_copyright
                meta.orig_author = meta.edit_author
                meta.orig_tags = meta.get_tags_string()
                
                if new_name and new_name != target_asset_name:
                    meta.asset_name = new_name
                
                refresh_asset_browser(context)
                
                self.report({"INFO"}, f"Updated metadata for '{meta.edit_name}'")
                return {"FINISHED"}
            else:
                self.report({"ERROR"}, "Failed to update asset metadata")
                return {"CANCELLED"}
                
        except Exception as e:
            self.report({"ERROR"}, f"Error updating metadata: {e}")
            return {"CANCELLED"}

    def _update_asset_metadata(self, blend_path, target_name, new_name=None, 
                                new_description=None, new_license=None,
                                new_copyright=None, new_author=None, new_tags=None):
        """Update metadata for a specific asset in a .blend file.
        
        Preserves ALL data in the .blend file by importing all datablock types,
        not just asset-related ones. This ensures non-asset data, custom structures,
        backup objects, etc. are maintained.
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
                            temp_name = f"__QAS_META_TEMP_{name}_{id(existing_db)}"
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
            target_found = False
            preview_data = None
            
            for collection_name in names_to_import.keys():
                if hasattr(bpy.data, collection_name):
                    collection = getattr(bpy.data, collection_name)
                    for name in names_to_import[collection_name]:
                        if name in collection:
                            db = collection[name]
                            imported_datablocks.add(db)
                            
                            if name == target_name and hasattr(db, 'asset_data') and db.asset_data:
                                target_found = True
                                
                                if hasattr(db, 'preview') and db.preview and db.preview.image_size[0] > 0:
                                    try:
                                        preview_data = {
                                            'size': tuple(db.preview.image_size),
                                            'pixels': list(db.preview.image_pixels_float)
                                        }
                                    except Exception as e:
                                        debug_print(f"Could not capture preview data: {e}")
                                        preview_data = None
                                
                                if new_description is not None:
                                    db.asset_data.description = new_description
                                if new_license is not None:
                                    db.asset_data.license = new_license
                                if new_copyright is not None:
                                    db.asset_data.copyright = new_copyright
                                if new_author is not None:
                                    db.asset_data.author = new_author
                                
                                if new_tags is not None:
                                    while len(db.asset_data.tags) > 0:
                                        db.asset_data.tags.remove(db.asset_data.tags[0])
                                    for tag in new_tags:
                                        db.asset_data.tags.new(tag)
                                
                                if new_name and new_name != target_name:
                                    db.name = new_name
            
            if not target_found:
                for db in list(imported_datablocks):
                    self._remove_datablock(db)
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
                # Handle file rename if asset name changed
                final_path = blend_path
                if new_name and new_name != target_name:
                    # Rename .blend file to match new asset name
                    new_blend_name = f"{new_name}.blend"
                    final_path = blend_path.parent / new_blend_name
                    
                    # If target already exists, add increment
                    if final_path.exists() and final_path != blend_path:
                        counter = 1
                        while final_path.exists():
                            new_blend_name = f"{new_name}.{counter:03d}.blend"
                            final_path = blend_path.parent / new_blend_name
                            counter += 1
                    
                    debug_print(f"Renaming file: {blend_path.name} -> {final_path.name}")
                
                # Remove old file and move temp to final location
                if blend_path.exists():
                    blend_path.unlink()
                shutil.move(str(temp_path), str(final_path))
                
                # Rename companion files if asset name changed
                if new_name and new_name != target_name and final_path != blend_path:
                    self._rename_companion_files(blend_path, target_name, new_name)
                
                # Update blend_path reference for preview restoration
                blend_path = final_path
                
                if preview_data:
                    try:
                        with bpy.data.libraries.load(str(blend_path)) as (data_from, data_to):
                            for collection_name in dir(data_from):
                                if not collection_name.startswith('_'):
                                    source = getattr(data_from, collection_name, None)
                                    if source and target_name in source:
                                        setattr(data_to, collection_name, [target_name])
                                        break
                        
                        for collection_name in dir(bpy.data):
                            if not collection_name.startswith('_'):
                                collection = getattr(bpy.data, collection_name, None)
                                if collection and hasattr(collection, '__iter__') and target_name in collection:
                                    db = collection[target_name]
                                    if hasattr(db, 'preview') and db.preview:
                                        db.preview.image_size = preview_data['size']
                                        db.preview.image_pixels_float = preview_data['pixels']
                                        debug_print(f"Restored preview for {target_name}")
                                    self._remove_datablock(db)
                                    break
                    except Exception as e:
                        debug_print(f"Could not restore preview: {e}")
                
                return True
                
        except Exception as e:
            print(f"Error updating metadata: {e}")
            import traceback
            traceback.print_exc()
            try:
                temp_path = blend_path.parent / f".tmp_{blend_path.name}"
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass
        
        return False
    
    def _rename_companion_files(self, old_blend_path, old_stem, new_stem):
        """Rename companion files when asset is renamed.
        
        Args:
            old_blend_path: Original .blend file path
            old_stem: Original asset name (file stem)
            new_stem: New asset name
        """
        parent = old_blend_path.parent
        
        # Rename asset-named thumbnails (old_stem.png -> new_stem.png)
        for ext in THUMBNAIL_EXTENSIONS:
            old_thumb = parent / f"{old_stem}{ext}"
            if old_thumb.exists():
                new_thumb = parent / f"{new_stem}{ext}"
                # Avoid collision - add .001 if target exists
                if new_thumb.exists():
                    counter = 1
                    while new_thumb.exists():
                        new_thumb = parent / f"{new_stem}.{counter:03d}{ext}"
                        counter += 1
                try:
                    old_thumb.rename(new_thumb)
                    debug_print(f"Renamed thumbnail: {old_thumb.name} -> {new_thumb.name}")
                except Exception as e:
                    debug_print(f"Could not rename thumbnail {old_thumb}: {e}")
        
        # Rename asset-named subfolder (old_stem/ -> new_stem/)
        old_folder = parent / old_stem
        if old_folder.exists() and old_folder.is_dir():
            new_folder = parent / new_stem
            # Avoid collision
            if new_folder.exists():
                counter = 1
                while new_folder.exists():
                    new_folder = parent / f"{new_stem}.{counter:03d}"
                    counter += 1
            try:
                old_folder.rename(new_folder)
                debug_print(f"Renamed asset folder: {old_folder.name} -> {new_folder.name}")
            except Exception as e:
                debug_print(f"Could not rename asset folder {old_folder}: {e}")
    
    def _remove_datablock(self, datablock):
        """Remove a datablock from the current session.
        
        Handles all common datablock types to prevent them from staying
        in the user's current file after metadata operations.
        """
        try:
            # Get the collection this datablock belongs to
            for collection_name in dir(bpy.data):
                if collection_name.startswith('_'):
                    continue
                collection = getattr(bpy.data, collection_name, None)
                if collection is None:
                    continue
                if not hasattr(collection, 'remove'):
                    continue
                
                # Check if this datablock is in this collection
                try:
                    if datablock in collection.values():
                        collection.remove(datablock)
                        return
                except (TypeError, AttributeError, RuntimeError):
                    # Some collections don't support 'in' or removal
                    continue
        except (RuntimeError, ReferenceError):
            # Datablock already removed or invalid
            pass


class QAS_OT_toggle_edit_mode(Operator):
    """Toggle edit mode for asset metadata and tags"""
    bl_idname = "qas.toggle_edit_mode"
    bl_label = "Edit Metadata/Tags"
    bl_description = "Enable editing of metadata and tags (temporarily overrides native panels)"
    
    @classmethod
    def poll(cls, context):
        # Only available for external assets
        asset = getattr(context, "asset", None)
        if not asset:
            return False
        return not bool(asset.local_id)
    
    def execute(self, context):
        # Import here to avoid circular dependency
        from .. import panels
        
        if panels._edit_mode_active:
            # Exit edit mode and apply changes
            wm = context.window_manager
            meta = getattr(wm, "qas_metadata_edit", None)
            
            if meta and meta.has_changes():
                # Apply changes
                bpy.ops.qas.apply_metadata_changes()
            
            panels._exit_edit_mode()
            self.report({'INFO'}, "Exited edit mode")
        else:
            # Enter edit mode
            panels._enter_edit_mode(context)
            self.report({'INFO'}, "Entered edit mode - native panels temporarily overridden")
        
        return {'FINISHED'}


classes = (
    QAS_OT_apply_metadata_changes,
    QAS_OT_toggle_edit_mode,
)
