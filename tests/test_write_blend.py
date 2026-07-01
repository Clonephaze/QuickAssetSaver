"""
Integration tests for write_blend_file and count_assets_in_blend.
Creates real Blender datablocks, writes them, and verifies the output.
"""
import unittest
import tempfile
from pathlib import Path
import bpy
from QuickAssetSaver.operators.file_io import write_blend_file, count_assets_in_blend
from tests.fixtures import make_test_asset, remove_test_asset


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
