"""
Quick Asset Saver operators package.
"""

if "bpy" in locals():
    import importlib
    if "utils" in locals():
        importlib.reload(utils)  # noqa: F821
    if "catalog" in locals():
        importlib.reload(catalog)  # noqa: F821
    if "file_io" in locals():
        importlib.reload(file_io)  # noqa: F821
    if "save" in locals():
        importlib.reload(save)  # noqa: F821
    if "bundle" in locals():
        importlib.reload(bundle)  # noqa: F821
    if "move" in locals():
        importlib.reload(move)  # noqa: F821
    if "delete" in locals():
        importlib.reload(delete)  # noqa: F821
    if "manage" in locals():
        importlib.reload(manage)  # noqa: F821
    if "swap" in locals():
        importlib.reload(swap)  # noqa: F821
    if "metadata" in locals():
        importlib.reload(metadata)  # noqa: F821

from . import utils, catalog, file_io, save, bundle, move, delete, manage, swap, metadata  # noqa: F401

import bpy

from .utils import (  # noqa: F401
    DEBUG_MODE,
    debug_print,
    refresh_asset_browser,
    refresh_asset_browser_deferred,
    sanitize_name,
    build_asset_filename,
    increment_filename,
    MIN_BLEND_FILE_SIZE,
    MAX_INCREMENTAL_FILES,
    LARGE_SELECTION_WARNING_THRESHOLD,
    VERY_LARGE_BUNDLE_WARNING_MB,
    DEFAULT_MAX_BUNDLE_SIZE_MB,
)

from .catalog import (  # noqa: F401
    get_catalog_path_from_uuid,
    get_catalogs_from_cdf,
    clear_and_set_tags,
    clear_catalog_cache,
)

from .file_io import (  # noqa: F401
    collect_external_dependencies,
    collect_selected_assets_with_names,
    collect_selected_asset_files,
    count_assets_in_blend,
    write_blend_file,
)

from .save import (
    QAS_OT_save_asset_to_library_direct,
    QAS_OT_open_library_folder,
)

from .bundle import (
    QAS_OT_bundle_assets,
    QAS_OT_open_bundle_folder,
)

from .manage import (
    QAS_OT_move_selected_to_library,
    QAS_OT_delete_selected_assets,
)

from .swap import (
    QAS_OT_swap_selected_with_asset,
)

from .metadata import (
    QAS_OT_apply_metadata_changes,
)


classes = (
    QAS_OT_save_asset_to_library_direct,
    QAS_OT_open_library_folder,
    QAS_OT_move_selected_to_library,
    QAS_OT_delete_selected_assets,
    QAS_OT_swap_selected_with_asset,
    QAS_OT_bundle_assets,
    QAS_OT_open_bundle_folder,
    QAS_OT_apply_metadata_changes,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
