"""
Metadata editing operator for Quick Asset Saver.
"""

import shutil
from pathlib import Path

import bpy
from bpy.types import Operator

from .utils import debug_print, refresh_asset_browser, ALL_DATABLOCK_COLLECTIONS


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
                if blend_path.exists():
                    blend_path.unlink()
                shutil.move(str(temp_path), str(blend_path))
                
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
    QAS_OT_apply_metadata_changes,
)
