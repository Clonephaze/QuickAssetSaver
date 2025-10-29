if "bpy" in locals():
    import importlib
    if "operators" in locals():
        importlib.reload(operators)  # noqa: F821
    if "properties" in locals():
        importlib.reload(properties)  # noqa: F821
    if "panels" in locals():
        importlib.reload(panels)  # noqa: F821
else:
    from . import operators
    from . import properties
    from . import panels

import bpy  # noqa: F401


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
