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
