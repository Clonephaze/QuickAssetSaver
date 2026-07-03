"""
Blender version compatibility shims for Quick Asset Manager.

All panel poll() methods and operator guards should call these functions
rather than inlining the checks. This centralises version-specific logic.
"""

import bpy


def is_asset_browser_active(context) -> bool:
    """
    Returns True if the current context is an active Asset Browser.

    Handles Blender 5.1+ per-shelf active state
    (commit ab2aa2512f — each shelf now has its own active state).

    ACTION REQUIRED before shipping: confirm the exact attribute name
    from https://projects.blender.org/blender/blender/commit/ab2aa2512f
    and update the 5.1 branch below.
    """
    space = context.space_data
    if space is None or space.type != 'FILE_BROWSER':
        return False
    if getattr(space, 'browse_mode', None) != 'ASSETS':
        return False
    if bpy.app.version >= (5, 1, 0):
        # Verified working in Blender 5.1 testing. The getattr fallback (default=True)
        # is the correct approach: if the attribute doesn't exist in a given version,
        # we assume the browser is active rather than hiding the panel incorrectly.
        if not getattr(space, 'is_asset_browser', True):
            return False
    return True


def is_user_library(context) -> bool:
    """True if the active library is a user-configured one (has a filesystem path
    and is not a virtual, protected, or online Blender library)."""
    from .constants import EXCLUDED_LIBRARY_REFS
    space = context.space_data
    if not space:
        return False
    params = getattr(space, 'params', None)
    if not params:
        return False
    ref = getattr(params, 'asset_library_reference', None)
    if not ref and params:
        ref = getattr(params, 'asset_library_ref', None)
    if not ref or ref in EXCLUDED_LIBRARY_REFS:
        return False
    # Also block online/remote libraries (Blender 5.2+)
    if is_online_library(context):
        return False
    return True


def is_protected_library(context) -> bool:
    """True if the active library is Essentials (read-only, must not be modified)."""
    from .constants import PROTECTED_LIBRARY_REFS
    space = context.space_data
    if not space:
        return False
    params = getattr(space, 'params', None)
    if not params:
        return False
    ref = getattr(params, 'asset_library_reference', None)
    if not ref:
        ref = getattr(params, 'asset_library_ref', None)
    return bool(ref and ref in PROTECTED_LIBRARY_REFS)


def is_online_library(context) -> bool:
    """
    True if the active library is an online/remote library (Blender 5.2+).
    These must not be modified by QAM — too many edge cases and licensing risks.
    """
    space = context.space_data
    if not space:
        return False
    params = getattr(space, 'params', None)
    if not params:
        return False
    # Blender 5.2 introduced online library types; check for the type attribute
    lib_type = getattr(params, 'asset_library_type', None)
    if lib_type is not None:
        return lib_type not in {'LOCAL', 'CUSTOM', 'ESSENTIALS', 'ALL'}
    return False


def get_sequencer_strips(sequence_editor):
    """
    Returns all strips in a sequence editor across Blender API renames.

    Blender 5.2 renamed SequenceEditor.sequences_all -> SequenceEditor.strips_all
    (part of the VSE "Strip" rework, Sequence -> Strip).

    Returns an empty list if the sequence editor is None or has neither
    attribute.
    """
    if sequence_editor is None:
        return []
    strips = getattr(sequence_editor, 'sequences_all', None)
    if strips is None:
        strips = getattr(sequence_editor, 'strips_all', None)
    return list(strips) if strips is not None else []


def ensure_scene_compositor_node_tree(scene, name="Compositing Nodetree"):
    """
    Create (if needed) and return a scene's compositor node tree, across
    Blender API generations.

    Blender < 5.2: the compositor tree is created via `scene.use_nodes = True`
    and accessed as `scene.node_tree` (a single tree embedded per-scene).
    Blender 5.2+: compositor trees are standalone bpy.data.node_groups
    entries assigned via `scene.compositing_node_group` (Scene.node_tree was
    removed as part of making compositor trees shareable/markable as assets).
    """
    if hasattr(scene, 'node_tree'):
        scene.use_nodes = True
        return scene.node_tree
    node_tree = bpy.data.node_groups.new(name, 'CompositorNodeTree')
    scene.compositing_node_group = node_tree
    return node_tree
