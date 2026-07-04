from . import operators, panels, properties

# import bpy Temp comment out, testing if needed  # noqa: F401


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
