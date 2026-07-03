"""
Shared test fixtures and helpers for the QAM test suite.
All helpers here work inside a running Blender instance.
"""

import tempfile
import shutil
import uuid
from pathlib import Path


# ── Temporary library helper ───────────────────────────────────────────────────

class TempLibrary:
    """
    Context manager that creates a temporary directory laid out like a
    Blender asset library (with an optional blender_assets.cats.txt).

    Usage::

        with TempLibrary() as lib:
            lib.add_catalog("Materials/Metal")
            path = lib.path
    """

    def __init__(self, catalogs=None):
        """
        Args:
            catalogs: optional list of catalog path strings to pre-populate,
                      e.g. ["Materials/Metal", "Characters/Heroes"]
        """
        self._tmpdir = None
        self._initial_catalogs = catalogs or []

    def __enter__(self):
        self._tmpdir = tempfile.mkdtemp(prefix="qam_test_lib_")
        self.path = Path(self._tmpdir)
        self.cdf_path = self.path / "blender_assets.cats.txt"

        lines = ["VERSION 1", ""]
        self._catalog_map = {}  # path → uuid

        for cat_path in self._initial_catalogs:
            cat_uuid = str(uuid.uuid4())
            self._catalog_map[cat_path] = cat_uuid
            display = cat_path.split("/")[-1]
            lines.append(f"{cat_uuid}:{cat_path}:{display}")

        self.cdf_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return self

    def __exit__(self, *_):
        if self._tmpdir:
            shutil.rmtree(self._tmpdir, ignore_errors=True)

    def add_catalog(self, catalog_path: str) -> str:
        """Add a catalog entry and return its UUID."""
        cat_uuid = str(uuid.uuid4())
        self._catalog_map[catalog_path] = cat_uuid
        display = catalog_path.split("/")[-1]
        with open(self.cdf_path, "a", encoding="utf-8") as f:
            f.write(f"{cat_uuid}:{catalog_path}:{display}\n")
        return cat_uuid

    def uuid_for(self, catalog_path: str) -> str:
        """Return the UUID assigned to a pre-created catalog path."""
        return self._catalog_map[catalog_path]


# ── Mock Blender context helpers ───────────────────────────────────────────────

class MockParams:
    """Minimal stand-in for space_data.params."""
    def __init__(self, lib_ref=None):
        self.asset_library_reference = lib_ref


class MockSpace:
    """Minimal stand-in for context.space_data."""
    def __init__(self, space_type="FILE_BROWSER", browse_mode="ASSETS", lib_ref=None):
        self.type = space_type
        self.browse_mode = browse_mode
        self.params = MockParams(lib_ref) if lib_ref is not None else None


class MockContext:
    """Minimal stand-in for bpy.context."""
    def __init__(self, space_data=None):
        self.space_data = space_data


def make_asset_browser_context(lib_ref="My Library"):
    """Return a MockContext that looks like an Asset Browser showing lib_ref."""
    return MockContext(MockSpace(lib_ref=lib_ref))


# ── Mock addon preferences ─────────────────────────────────────────────────────

class MockPrefs:
    """Minimal stand-in for QuickAssetManagerPreferences."""
    filename_prefix: str = ""
    filename_suffix: str = ""
    include_date_in_filename: bool = False
    use_catalog_subfolders: bool = True
    auto_refresh: bool = True
    max_bundle_size_mb: int = 4096
    default_author: str = ""
    default_description: str = ""
    default_license: str = ""
    default_copyright: str = ""


# ── Blender datablock helpers ──────────────────────────────────────────────────

def make_test_asset(name="QAM_TestAsset", description="", author=""):
    """
    Create a simple mesh object, mark it as an asset, and return it.
    Caller is responsible for cleanup via bpy.data.objects.remove(...).
    """
    import bpy
    bpy.ops.mesh.primitive_cube_add()
    obj = bpy.context.active_object
    obj.name = name
    obj.asset_mark()
    if description:
        obj.asset_data.description = description
    if author:
        obj.asset_data.author = author
    return obj


def remove_test_asset(obj):
    """Remove a test asset object and its mesh from bpy.data."""
    import bpy
    mesh = obj.data if obj.type == 'MESH' else None
    bpy.data.objects.remove(obj, do_unlink=True)
    if mesh and mesh.users == 0:
        bpy.data.meshes.remove(mesh)


def make_compositor_asset(name="QAM_CompositorTest", scene_name="QAM_CompositorTest_Scene"):
    """
    Create a compositor node group asset containing a Render Layer node
    that points at a dedicated Scene, and mark the node group as an asset.

    Mirrors the real-world setup that triggers the "whole project copied"
    bug (issue #14): a Render Layer node holds a direct pointer to a Scene,
    which bpy.data.libraries.write() will otherwise pull in wholesale.

    A Render Layers node can only live in "the compositing node tree of a
    scene in the file" (a hard restriction enforced by Blender itself, not
    just newer versions), so the node tree we mark as an asset must be a
    scene's own compositor tree rather than a free-floating node group.
    ensure_scene_compositor_node_tree() handles both the pre-5.2 API
    (scene.use_nodes / scene.node_tree) and 5.2+ (scene.compositing_node_group).

    Returns (node_tree, scene, owner_scene). Caller is responsible for
    cleanup via remove_compositor_asset(node_tree, scene, owner_scene).
    """
    import bpy
    from QuickAssetSaver.compatibility import ensure_scene_compositor_node_tree
    owner_scene = bpy.data.scenes.new(f"{name}_Owner")
    node_tree = ensure_scene_compositor_node_tree(owner_scene)

    scene = bpy.data.scenes.new(scene_name)
    # Give the scene something non-trivial so an accidental copy is detectable.
    bpy.ops.mesh.primitive_cube_add()
    cube = bpy.context.active_object
    assert cube is not None
    for coll in list(cube.users_collection):
        coll.objects.unlink(cube)
    scene.collection.objects.link(cube)

    render_layers_node = next(
        (n for n in node_tree.nodes if n.bl_idname == 'CompositorNodeRLayers'), None
    )
    if render_layers_node is None:
        render_layers_node = node_tree.nodes.new('CompositorNodeRLayers')
    render_layers_node.scene = scene

    node_tree.asset_mark()
    return node_tree, scene, owner_scene


def remove_compositor_asset(node_tree, scene, owner_scene):
    """Remove a compositor node group asset and its associated scenes/objects."""
    import bpy
    for obj in list(scene.collection.objects):
        mesh = obj.data if obj.type == 'MESH' else None
        bpy.data.objects.remove(obj, do_unlink=True)
        if mesh and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
    bpy.data.scenes.remove(scene)
    # asset_mark() sets a fake user, which would otherwise keep the node
    # tree alive indefinitely — clear it either way.
    node_tree.use_fake_user = False
    try:
        # Blender 5.2+: the compositor tree is a standalone bpy.data.node_groups
        # entry, so it must be removed explicitly (do_unlink clears
        # owner_scene's pointer to it).
        bpy.data.node_groups.remove(node_tree, do_unlink=True)
    except RuntimeError:
        # Older Blender versions embed the compositor tree in the scene
        # (not a standalone bpy.data.node_groups entry) — it's freed
        # automatically when the owning scene is removed below.
        pass
    bpy.data.scenes.remove(owner_scene)
