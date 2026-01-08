"""
Swap/replace operator for Quick Asset Saver.
"""

import bpy
import mathutils
from bpy.types import Operator

from .file_io import collect_selected_asset_files


class QAS_OT_swap_selected_with_asset(Operator):
    """Swap selected scene objects with the selected asset from the library."""

    bl_idname = "qas.swap_selected_with_asset"
    bl_label = "Replace with Asset"
    bl_description = "Replace selected objects in the scene with the selected asset (Only available for Object and Collection assets)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not (hasattr(context, "space_data")
            and context.space_data.type == "FILE_BROWSER"
            and getattr(context.space_data, "browse_mode", None) == "ASSETS"):
            return False
        
        has_selected = False
        for obj in bpy.data.objects:
            if obj.select_get():
                has_selected = True
                break
        
        if not has_selected:
            return False
        
        asset = getattr(context, "asset", None)
        if not asset:
            return False
        
        # Check asset ID type - works for both current file and library assets
        asset_id_type = getattr(asset, "id_type", None)
        if not asset_id_type:
            return False
        
        # Only enable for Object and Collection assets
        return asset_id_type in {'OBJECT', 'COLLECTION'}

    def _get_import_settings(self, context):
        """Get import settings from Blender's Asset Browser."""
        space = context.space_data
        use_link = False
        instance_collections = False
        
        import_method = getattr(space.params, 'import_method', 'FOLLOW_PREFS')
        
        if import_method == 'FOLLOW_PREFS':
            prefs = context.preferences.filepaths
            import_method = getattr(prefs, 'asset_import_method', 'APPEND')
        
        use_link = import_method == 'LINK'
        
        if hasattr(space.params, 'import_method_collections'):
            coll_method = space.params.import_method_collections
            instance_collections = coll_method == 'INSTANCE'
        elif hasattr(context.preferences.filepaths, 'collection_instance_empty'):
            instance_collections = context.preferences.filepaths.collection_instance_empty
        
        return use_link, instance_collections

    def execute(self, context):
        use_link, instance_collections = self._get_import_settings(context)

        selected_paths, _ = collect_selected_asset_files(context)
        if len(selected_paths) != 1:
            self.report({"WARNING"}, "Select exactly one asset to replace with")
            return {"CANCELLED"}

        asset_path = selected_paths[0]

        scene_objects = []
        for obj in bpy.data.objects:
            if obj.select_get():
                scene_objects.append(obj)

        if not scene_objects:
            self.report({"WARNING"}, "No objects selected in scene")
            return {"CANCELLED"}

        transforms = []
        for obj in scene_objects:
            transforms.append({
                'matrix_world': obj.matrix_world.copy(),
                'location': obj.location.copy(),
                'rotation_euler': obj.rotation_euler.copy(),
                'rotation_quaternion': obj.rotation_quaternion.copy(),
                'rotation_mode': obj.rotation_mode,
                'scale': obj.scale.copy(),
            })

        imported_objects = []
        
        try:
            with bpy.data.libraries.load(str(asset_path), link=use_link) as (data_from, data_to):
                has_objects = len(data_from.objects) > 0 if hasattr(data_from, 'objects') else False
                has_collections = len(data_from.collections) > 0 if hasattr(data_from, 'collections') else False
                
                if not has_objects and not has_collections:
                    self.report({"ERROR"}, "Asset contains no objects or collections (brushes/materials not supported)")
                    return {"CANCELLED"}
                
                if has_objects:
                    data_to.objects = list(data_from.objects)

            active_collection = context.view_layer.active_layer_collection.collection
            
            if hasattr(data_to, 'objects'):
                for obj in data_to.objects:
                    if obj is not None:
                        active_collection.objects.link(obj)
                        imported_objects.append(obj)

        except Exception as e:
            self.report({"ERROR"}, f"Failed to import asset: {e}")
            return {"CANCELLED"}

        if not imported_objects:
            self.report({"ERROR"}, "No objects found in asset file")
            return {"CANCELLED"}

        context.view_layer.update()

        root_objects = [obj for obj in imported_objects if obj.parent is None or obj.parent not in imported_objects]
        
        original_center = mathutils.Vector((0.0, 0.0, 0.0))
        for obj in root_objects:
            original_center += obj.location.copy()
        if root_objects:
            original_center /= len(root_objects)

        root_indices = [imported_objects.index(obj) for obj in root_objects]
        root_offsets = [obj.location.copy() - original_center for obj in root_objects]

        all_swapped_objects = []
        for i, transform_data in enumerate(transforms):
            target_pos = transform_data['matrix_world'].translation.copy()
            target_rot_mode = transform_data['rotation_mode']
            target_rot_euler = transform_data['rotation_euler']
            target_rot_quat = transform_data['rotation_quaternion']
            target_scale = transform_data['scale']

            if i == 0:
                objs_to_place = imported_objects
                for root_obj, offset in zip(root_objects, root_offsets):
                    root_obj.location = target_pos + offset
                    root_obj.rotation_mode = target_rot_mode
                    if target_rot_mode == 'QUATERNION':
                        root_obj.rotation_quaternion = target_rot_quat
                    else:
                        root_obj.rotation_euler = target_rot_euler
                    root_obj.scale = target_scale
            else:
                objs_to_place = []
                old_to_new = {}
                
                for obj in imported_objects:
                    if use_link:
                        new_obj = obj.copy()
                    else:
                        new_obj = obj.copy()
                        if obj.data:
                            new_obj.data = obj.data.copy()
                    active_collection.objects.link(new_obj)
                    old_to_new[obj] = new_obj
                    objs_to_place.append(new_obj)
                
                for obj in imported_objects:
                    if obj.parent and obj.parent in old_to_new:
                        old_to_new[obj].parent = old_to_new[obj.parent]
                        old_to_new[obj].matrix_parent_inverse = obj.matrix_parent_inverse.copy()
                
                for idx, offset in zip(root_indices, root_offsets):
                    new_root = old_to_new[imported_objects[idx]]
                    new_root.location = target_pos + offset
                    new_root.rotation_mode = target_rot_mode
                    if target_rot_mode == 'QUATERNION':
                        new_root.rotation_quaternion = target_rot_quat
                    else:
                        new_root.rotation_euler = target_rot_euler
                    new_root.scale = target_scale

            all_swapped_objects.extend(objs_to_place)

        for obj in scene_objects:
            bpy.data.objects.remove(obj, do_unlink=True)

        bpy.ops.object.select_all(action='DESELECT')
        for obj in all_swapped_objects:
            obj.select_set(True)
        if all_swapped_objects:
            context.view_layer.objects.active = all_swapped_objects[0]

        mode_str = "linked" if use_link else "appended"
        self.report({"INFO"}, f"Swapped {len(transforms)} object(s) ({mode_str})")
        return {"FINISHED"}


classes = (
    QAS_OT_swap_selected_with_asset,
)
