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
    QAM_OT_refresh_catalog_list,
)

from .file_io import (  # noqa: F401
    collect_external_dependencies,
    collect_selected_assets_with_names,
    collect_selected_asset_files,
    count_assets_in_blend,
    write_blend_file,
)

from .save import (
    QAM_OT_save_asset_to_library_direct,
    QAM_OT_open_library_folder,
)

from .bundle import (
    QAM_OT_bundle_assets,
    QAM_OT_open_bundle_folder,
)

from .manage import (
    QAM_OT_move_selected_to_library,
    QAM_OT_delete_selected_assets,
)

from .swap import (
    QAM_OT_swap_selected_with_asset,
)

from .metadata import (
    QAM_OT_apply_metadata_changes,
    QAM_OT_toggle_edit_mode,
)


classes = (
    QAM_OT_save_asset_to_library_direct,
    QAM_OT_open_library_folder,
    QAM_OT_move_selected_to_library,
    QAM_OT_delete_selected_assets,
    QAM_OT_swap_selected_with_asset,
    QAM_OT_bundle_assets,
    QAM_OT_open_bundle_folder,
    QAM_OT_apply_metadata_changes,
    QAM_OT_toggle_edit_mode,
    QAM_OT_refresh_catalog_list,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
