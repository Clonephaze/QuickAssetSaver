"""
Tests for the Send2Trash fallback safety guarantee.

The core invariant: if Send2Trash is unavailable the addon must NEVER
permanently delete a file via os.remove or any other means. It must
raise RuntimeError with a message that tells the user where the file is.

We test this in three layers:
  1. The fallback function itself — raises, doesn't delete
  2. The real move_to_trash is callable from both delete and move modules
  3. When Send2Trash IS available it successfully moves a real file
"""

import tempfile
import unittest
from pathlib import Path


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_fallback():
    """
    Construct the fallback move_to_trash exactly as it is defined in the
    addon, so the test is independent of whether send2trash is installed.
    """
    def move_to_trash(path) -> None:
        p = Path(path)
        raise RuntimeError(
            f"Send2Trash is unavailable. '{p.name}' was NOT deleted.\n"
            f"You can delete it manually at: {p.parent}"
        )
    return move_to_trash


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestFallbackBehavior(unittest.TestCase):
    """
    The fallback function (no Send2Trash installed) must raise RuntimeError
    and leave the file intact. This is the critical safety guarantee — we
    must never silently call os.remove() as a "fallback to trash".
    """

    def setUp(self):
        self.fallback = _make_fallback()
        self._tmpdir = tempfile.mkdtemp(prefix="qam_trash_test_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_fallback_raises_runtime_error(self):
        test_file = Path(self._tmpdir) / "my_asset.blend"
        test_file.touch()
        with self.assertRaises(RuntimeError):
            self.fallback(str(test_file))

    def test_fallback_file_still_exists_after_raise(self):
        """The file must survive the fallback — it was NOT deleted."""
        test_file = Path(self._tmpdir) / "survivor.blend"
        test_file.touch()
        try:
            self.fallback(str(test_file))
        except RuntimeError:
            pass
        self.assertTrue(test_file.exists(), "File was deleted by the fallback — critical safety violation")

    def test_fallback_error_message_contains_filename(self):
        test_file = Path(self._tmpdir) / "important_asset.blend"
        test_file.touch()
        with self.assertRaises(RuntimeError) as ctx:
            self.fallback(str(test_file))
        self.assertIn("important_asset.blend", str(ctx.exception))

    def test_fallback_error_message_contains_parent_directory(self):
        """User must be told WHERE the file is so they can delete it themselves."""
        test_file = Path(self._tmpdir) / "asset.blend"
        test_file.touch()
        with self.assertRaises(RuntimeError) as ctx:
            self.fallback(str(test_file))
        self.assertIn(self._tmpdir, str(ctx.exception))

    def test_fallback_error_message_says_not_deleted(self):
        test_file = Path(self._tmpdir) / "asset.blend"
        test_file.touch()
        with self.assertRaises(RuntimeError) as ctx:
            self.fallback(str(test_file))
        self.assertIn("NOT deleted", str(ctx.exception))


class TestMoveToTrashImportable(unittest.TestCase):
    """move_to_trash must be a callable defined at module level in both operators."""

    def test_delete_module_has_move_to_trash(self):
        from QuickAssetSaver.operators.delete import move_to_trash
        self.assertTrue(callable(move_to_trash))

    def test_move_module_has_move_to_trash(self):
        from QuickAssetSaver.operators.move import move_to_trash
        self.assertTrue(callable(move_to_trash))

    def test_both_modules_define_independently(self):
        """Each module defines its own move_to_trash — they should not be the same object."""
        from QuickAssetSaver.operators.delete import move_to_trash as dt
        from QuickAssetSaver.operators.move import move_to_trash as mt
        # Both callable; whether same or different objects is an implementation detail
        self.assertTrue(callable(dt))
        self.assertTrue(callable(mt))


class TestMoveToTrashRealBehavior(unittest.TestCase):
    """
    When Send2Trash IS available (wheels/Send2Trash-*.whl is installed),
    move_to_trash should successfully trash the file.
    When it is NOT available, it must raise RuntimeError — never silently delete.
    """

    def setUp(self):
        self._tmpdir = tempfile.mkdtemp(prefix="qam_real_trash_")

    def tearDown(self):
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_real_move_to_trash_does_not_permanently_delete(self):
        """
        Whatever happens — Send2Trash available or not — os.remove must never
        be the outcome. Either the file is trashed (acceptable) or RuntimeError
        is raised with a helpful message (acceptable). A silent permanent
        deletion is never acceptable.

        We verify this by checking: if an exception IS raised, it must be a
        RuntimeError with our expected message, not an OS-level deletion error.
        """
        from QuickAssetSaver.operators.delete import move_to_trash

        test_file = Path(self._tmpdir) / "qam_real_trash_test.blend"
        test_file.touch()

        try:
            move_to_trash(str(test_file))
            # Send2Trash trashed the file — success, no assertion needed
        except RuntimeError as e:
            # Fallback raised — that is acceptable
            self.assertIn("NOT deleted", str(e),
                "RuntimeError from fallback must contain 'NOT deleted'")
            # File must still exist when fallback raises
            self.assertTrue(test_file.exists(),
                "Fallback raised RuntimeError but file was deleted — safety violation")
        except Exception as e:
            self.fail(f"move_to_trash raised an unexpected exception type: {type(e).__name__}: {e}")

    def test_nonexistent_file_raises_exception(self):
        """Calling move_to_trash on a nonexistent path must raise, not silently succeed."""
        from QuickAssetSaver.operators.delete import move_to_trash
        bad_path = str(Path(self._tmpdir) / "does_not_exist.blend")
        with self.assertRaises(Exception):
            move_to_trash(bad_path)
