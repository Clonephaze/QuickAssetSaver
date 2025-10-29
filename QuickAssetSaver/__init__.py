"""
Quick Asset Saver - Blender Addon
==================================
Enables saving assets from the Current File Asset Browser directly to a user 
asset library folder as individual .blend files with full metadata support.

Author: Quick Asset Saver Team
License: GPL
"""

bl_info = {
    "name": "Quick Asset Saver",
    "author": "Quick Asset Saver Team",
    "version": (1, 0, 0),
    "blender": (5, 0, 0),
    "location": "Asset Browser > Context Menu > Save to Library",
    "description": "Save Current File assets directly to a library folder as individual .blend files",
    "category": "Asset Management",
    "doc_url": "",
    "tracker_url": "",
}

# Import submodules
if "bpy" in locals():
    import importlib
    if "operators" in locals():
        importlib.reload(operators)
    if "properties" in locals():
        importlib.reload(properties)
    if "panels" in locals():
        importlib.reload(panels)
else:
    from . import operators
    from . import properties
    from . import panels

import bpy


def register():
    """Register all addon classes and UI elements."""
    properties.register()
    operators.register()
    panels.register()
    
    print("Quick Asset Saver registered successfully")


def unregister():
    """Unregister all addon classes and UI elements."""
    panels.unregister()
    operators.unregister()
    properties.unregister()
    
    print("Quick Asset Saver unregistered")


if __name__ == "__main__":
    register()
