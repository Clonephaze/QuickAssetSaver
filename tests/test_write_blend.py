"""
Integration tests for write_blend_file and count_assets_in_blend.
Creates real Blender datablocks, writes them, and verifies the output.
"""
import unittest
import tempfile
from pathlib import Path
import bpy
from QuickAssetSaver.operators.file_io import write_blend_file, count_assets_in_blend
from tests.fixtures import make_test_asset, remove_test_asset, make_compositor_asset, remove_compositor_asset


class TestWriteBlendFile(unittest.TestCase):
    def setUp(self):
        self.obj = make_test_asset(
            name="QAM_WriteTest",
            description="Test description",
            author="Test Author",
        )

    def tearDown(self):
        remove_test_asset(self.obj)

    def test_returns_true_on_success(self):
        with tempfile.TemporaryDirectory() as d:
            result = write_blend_file(Path(d) / "out.blend", {self.obj})
            self.assertTrue(result)

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.blend"
            write_blend_file(out, {self.obj})
            self.assertTrue(out.exists())

    def test_file_is_not_empty(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.blend"
            write_blend_file(out, {self.obj})
            self.assertGreater(out.stat().st_size, 100)

    def test_returns_false_for_unwritable_path(self):
        bad = Path("/nonexistent_qam_test_dir/out.blend")
        result = write_blend_file(bad, {self.obj})
        self.assertFalse(result)

    def test_written_file_contains_asset(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "out.blend"
            write_blend_file(out, {self.obj})
            info = count_assets_in_blend(out)
            self.assertGreater(info["count"], 0)
            names = [a["name"] for a in info["assets"]]
            self.assertIn("QAM_WriteTest", names)

    def test_write_multiple_datablocks(self):
        obj2 = make_test_asset(name="QAM_WriteTest2")
        try:
            with tempfile.TemporaryDirectory() as d:
                out = Path(d) / "out.blend"
                write_blend_file(out, {self.obj, obj2})
                info = count_assets_in_blend(out)
                self.assertGreaterEqual(info["count"], 2)
        finally:
            remove_test_asset(obj2)


class TestWriteBlendPreservesMetadata(unittest.TestCase):
    """Metadata written to the .blend file must survive a round-trip load."""

    def setUp(self):
        self.obj = make_test_asset(
            name="QAM_MetaTest",
            description="A test description",
            author="Test Author",
        )
        self.obj.asset_data.license = "CC0"
        self.obj.asset_data.copyright = "2026 Test"

    def tearDown(self):
        remove_test_asset(self.obj)
        # Clean up anything that was loaded during the test
        for obj in list(bpy.data.objects):
            if obj.name.startswith("QAM_MetaTest") and obj != self.obj:
                remove_test_asset(obj)

    def test_description_survives_round_trip(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "meta.blend"
            write_blend_file(out, {self.obj})

            loaded = []
            with bpy.data.libraries.load(str(out), link=False, assets_only=True) as (src, dst):
                if src.objects:
                    dst.objects = list(src.objects)

            for obj in bpy.data.objects:
                if obj.name == "QAM_MetaTest" and obj.asset_data and obj is not self.obj:
                    self.assertEqual(obj.asset_data.description, "A test description")
                    self.assertEqual(obj.asset_data.author, "Test Author")
                    loaded.append(obj)

            for obj in loaded:
                remove_test_asset(obj)


class TestCountAssetsInBlend(unittest.TestCase):
    def setUp(self):
        self.obj = make_test_asset(name="QAM_CountTest")

    def tearDown(self):
        remove_test_asset(self.obj)

    def test_returns_count_dict_structure(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "count.blend"
            write_blend_file(out, {self.obj})
            result = count_assets_in_blend(out)
            self.assertIn("count", result)
            self.assertIn("assets", result)

    def test_count_matches_assets_list_length(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "count.blend"
            write_blend_file(out, {self.obj})
            result = count_assets_in_blend(out)
            self.assertEqual(result["count"], len(result["assets"]))

    def test_returns_zero_for_nonexistent_file(self):
        result = count_assets_in_blend(Path("/nonexistent/file.blend"))
        self.assertEqual(result["count"], 0)


class TestWriteBlendCompositorAssets(unittest.TestCase):
    """Regression test for issue #14: a compositor node group asset with a
    Render Layer node must not pull its referenced Scene (and everything the
    scene contains) into the written asset file."""

    def setUp(self):
        self.node_tree, self.scene, self.owner_scene = make_compositor_asset()

    def tearDown(self):
        remove_compositor_asset(self.node_tree, self.scene, self.owner_scene)

    def test_does_not_write_referenced_scene(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "compositor.blend"
            result = write_blend_file(out, {self.node_tree})
            self.assertTrue(result)

            with bpy.data.libraries.load(str(out), link=False) as (src, _dst):
                scene_names = list(src.scenes)

            self.assertNotIn(self.scene.name, scene_names)

    def test_render_layers_scene_pointer_restored_after_write(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "compositor.blend"
            write_blend_file(out, {self.node_tree})

            render_layers_node = next(
                n for n in self.node_tree.nodes if n.bl_idname == 'CompositorNodeRLayers'
            )
            self.assertEqual(render_layers_node.scene, self.scene)


class TestWriteBlendAllAssetTypes(unittest.TestCase):
    """Smoke-test write_blend_file against every datablock type the Asset
    Browser allows marking as an asset (see ASSET_DATABLOCK_COLLECTIONS).

    These are deliberately lightweight — just "does it write without
    error and produce a real file" — to catch type-specific writer bugs
    early. Object and NodeTree (compositor) have more thorough dedicated
    tests elsewhere in this file.
    """

    def _assert_write_succeeds(self, datablock):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "smoke.blend"
            self.assertTrue(write_blend_file(out, {datablock}))
            self.assertTrue(out.exists())
            self.assertGreater(out.stat().st_size, 100)

    def test_material_asset(self):
        mat = bpy.data.materials.new("QAM_SmokeMaterial")
        mat.asset_mark()
        try:
            self._assert_write_succeeds(mat)
        finally:
            bpy.data.materials.remove(mat)

    def test_world_asset(self):
        world = bpy.data.worlds.new("QAM_SmokeWorld")
        world.asset_mark()
        try:
            self._assert_write_succeeds(world)
        finally:
            bpy.data.worlds.remove(world)

    def test_action_asset(self):
        action = bpy.data.actions.new("QAM_SmokeAction")
        action.asset_mark()
        try:
            self._assert_write_succeeds(action)
        finally:
            bpy.data.actions.remove(action)

    def test_armature_asset(self):
        armature = bpy.data.armatures.new("QAM_SmokeArmature")
        armature.asset_mark()
        try:
            self._assert_write_succeeds(armature)
        finally:
            bpy.data.armatures.remove(armature)

    def test_curve_asset(self):
        curve = bpy.data.curves.new("QAM_SmokeCurve", type='CURVE')
        curve.asset_mark()
        try:
            self._assert_write_succeeds(curve)
        finally:
            bpy.data.curves.remove(curve)

    def test_collection_asset(self):
        collection = bpy.data.collections.new("QAM_SmokeCollection")
        collection.asset_mark()
        try:
            self._assert_write_succeeds(collection)
        finally:
            bpy.data.collections.remove(collection)

    def test_mesh_asset(self):
        mesh = bpy.data.meshes.new("QAM_SmokeMesh")
        mesh.asset_mark()
        try:
            self._assert_write_succeeds(mesh)
        finally:
            bpy.data.meshes.remove(mesh)

    def test_brush_asset(self):
        brush = bpy.data.brushes.new("QAM_SmokeBrush", mode='TEXTURE_PAINT')
        brush.asset_mark()
        try:
            self._assert_write_succeeds(brush)
        finally:
            bpy.data.brushes.remove(brush)

    def test_scene_asset(self):
        # Use a copy of the active scene rather than bpy.data.scenes.new():
        # a brand-new, never-initialized scene's view layer can be missing
        # data that some Blender versions' partial-write path dereferences
        # unconditionally, crashing the process (observed as a native
        # access violation on 5.2 alpha). A copy of an existing, fully
        # initialized scene is both safer and more representative of a
        # real Scene asset a user would actually save.
        scene = bpy.context.scene.copy()
        scene.asset_mark()
        try:
            self._assert_write_succeeds(scene)
        finally:
            bpy.data.scenes.remove(scene)
