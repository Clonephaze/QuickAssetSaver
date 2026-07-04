"""
Blender test runner for Quick Asset Manager.

Run with:
    blender --background --python tests/blender_test_runner.py

Or via the PowerShell launcher:
    .\run_tests.ps1
"""

import sys
import unittest
from pathlib import Path

# ── Path setup ────────────────────────────────────────────────────────────────
# Add the project root so `import QuickAssetSaver` works.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

TESTS_DIR = Path(__file__).resolve().parent

# ── Addon registration ─────────────────────────────────────────────────────────
import bpy  # noqa: E402 (must come after sys.path setup)

def _register_addon():
    """Register the addon if it is not already active (i.e. not installed)."""
    # If the addon is installed as a Blender extension it is already registered
    # before this script runs. Check for any of its WindowManager attributes.
    if hasattr(bpy.types.WindowManager, "qam_save_props"):
        print("[QAM Tests] Addon already registered (installed extension) — skipping manual register.")
        return
    import QuickAssetSaver
    try:
        QuickAssetSaver.register()
        print("[QAM Tests] Addon registered (source import).")
    except Exception as e:
        print(f"[QAM Tests] WARNING: Could not register addon: {e}")


def _unregister_addon():
    """Unregister only if we registered manually (i.e. addon is NOT installed)."""
    # If the addon was already registered by Blender's extension system,
    # let Blender manage unregistration — calling it here would double-unregister.
    if "QuickAssetSaver" in (getattr(bpy.context.preferences.addons, "keys", lambda: [])() if hasattr(bpy.context.preferences.addons, "keys") else []):
        print("[QAM Tests] Installed extension — skipping manual unregister.")
        return
    # Check if it was actually registered by us by looking for a known installed path
    import QuickAssetSaver
    addon_file = getattr(QuickAssetSaver, "__file__", "")
    if "extensions" in addon_file.replace("\\", "/"):
        print("[QAM Tests] Installed extension detected — skipping manual unregister.")
        return
    try:
        QuickAssetSaver.unregister()
        print("[QAM Tests] Addon unregistered.")
    except Exception as e:
        print(f"[QAM Tests] WARNING: Could not unregister addon (normal in test env): {e}")

# ── Test discovery and execution ───────────────────────────────────────────────
def main():
    _register_addon()

    loader = unittest.TestLoader()
    suite = loader.discover(start_dir=str(TESTS_DIR), pattern="test_*.py")

    print("\n" + "=" * 70)
    print("  Quick Asset Manager — Test Suite")
    print("=" * 70 + "\n")

    runner = unittest.TextTestRunner(verbosity=2, stream=sys.stdout)
    result = runner.run(suite)

    print("\n" + "=" * 70)
    passed  = result.testsRun - len(result.failures) - len(result.errors) - len(result.skipped)
    print(f"  {passed}/{result.testsRun} passed  |  "
          f"{len(result.failures)} failed  |  "
          f"{len(result.errors)} errors  |  "
          f"{len(result.skipped)} skipped")
    print("=" * 70 + "\n")

    _unregister_addon()
    sys.exit(0 if result.wasSuccessful() else 1)


if __name__ == "__main__":
    main()
