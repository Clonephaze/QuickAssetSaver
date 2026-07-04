"""
Shared constants for Quick Asset Manager.
"""

# Library references with no filesystem path — bulk/move/delete not applicable
VIRTUAL_LIBRARY_REFS = frozenset({"LOCAL", "CURRENT", "ALL"})

# Libraries that exist on disk but must never be modified by QAM
PROTECTED_LIBRARY_REFS = frozenset({"ESSENTIALS"})

# All library refs where QAM edit operations are not permitted
EXCLUDED_LIBRARY_REFS = VIRTUAL_LIBRARY_REFS | PROTECTED_LIBRARY_REFS

# Companion folder names (conservative — false positives delete user data)
# Each inner list is a group of equivalent casing variants for the same concept.
# Do not expand without explicit review.
COMPANION_FOLDER_GROUPS = [
    ['textures', 'Textures', 'TEXTURES'],
    ['maps', 'Maps', 'MAPS'],
    ['materials', 'Materials', 'MATERIALS'],
    ['shaders', 'Shaders', 'SHADERS'],
    ['images', 'Images', 'IMAGES'],
    ['hdri', 'HDRI', 'hdris', 'HDRIs'],
    ['references', 'References', 'ref', 'Ref'],
    ['documentation', 'Documentation', 'docs', 'Docs'],
    ['resources', 'Resources', 'RESOURCES'],
]
COMPANION_FOLDER_NAMES = [
    name for group in COMPANION_FOLDER_GROUPS for name in group
]

THUMBNAIL_EXTENSIONS = ['.png', '.webp', '.jpg', '.jpeg']
METADATA_EXTENSIONS = ['.json', '.txt', '.md', '.xml']

MIN_BLEND_FILE_SIZE = 100          # bytes — files smaller than this are ignored
MAX_INCREMENTAL_FILES = 9999       # upper bound for _001 suffix generation
LARGE_SELECTION_WARNING_THRESHOLD = 25  # show warning when selecting more than this
MAX_FILENAME_AFFIX_LENGTH = 32

DEFAULT_MAX_BUNDLE_SIZE_MB = 4096
VERY_LARGE_BUNDLE_WARNING_MB = 5000  # legacy name used in bundle.py
LARGE_BUNDLE_WARNING_MB = int(DEFAULT_MAX_BUNDLE_SIZE_MB * 0.75)  # 3072 MB
