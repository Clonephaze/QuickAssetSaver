if "bpy" in locals():
    import importlib
    if "operators" in locals():
        importlib.reload(operators)  # noqa: F821
    if "properties" in locals():
        importlib.reload(properties)  # noqa: F821
    if "panels" in locals():
        importlib.reload(panels)  # noqa: F821
else:
    from . import operators, panels, properties

import bpy  # noqa: F401


def register():
    properties.register()
    operators.register()
    panels.register()


def unregister():
    panels.unregister()
    operators.unregister()
    properties.unregister()


if __name__ == "__main__":
    register()
