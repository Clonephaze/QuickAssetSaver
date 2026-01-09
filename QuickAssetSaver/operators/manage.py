"""
Asset management operators for Quick Asset Saver.

This module re-exports operators from their individual modules for
backwards compatibility. The actual implementations are in:
- move.py: Move operator and companion file handling
- delete.py: Delete operator
"""

from .move import QAS_OT_move_selected_to_library
from .delete import QAS_OT_delete_selected_assets

# Re-export classes tuple for registration
classes = (
    QAS_OT_move_selected_to_library,
    QAS_OT_delete_selected_assets,
)

__all__ = [
    'QAS_OT_move_selected_to_library',
    'QAS_OT_delete_selected_assets',
    'classes',
]
