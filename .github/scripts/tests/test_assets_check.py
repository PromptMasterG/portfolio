"""Tests for the supplied-assets guard, using a throwaway git repository."""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import assets_check  # noqa: E402

ENTRY = {"file": "assets/a/one.png", "project": "a", "width": 1, "height": 1, "alt": "One.", "caption": "One."}
OTHER = {"file": "assets/a/two.png", "project": "a", "width": 1, "height": 1, "alt": "Two.", "caption": "Two."}


@unittest.skipUnless(shutil.which("git"), "needs git")
class AssetsGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.git("init", "-q", "-b", "main")
        (self.root / "assets/a").mkdir(parents=True)
        (self.root / "assets/a/one.png").write_bytes(b"one")
        (self.root / "assets/a/two.png").write_bytes(b"two")
        self.write_manifest([ENTRY, OTHER])
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "base")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True)

    def write_manifest(self, entries):
        (self.root / "assets-manifest.json").write_text(json.dumps(entries), encoding="utf-8")

    def run_check(self):
        return assets_check.check(self.root, "main")

    def test_unchanged_passes(self):
        self.assertEqual(self.run_check(), ([], []))

    def test_removing_an_image_with_its_entry_passes(self):
        (self.root / "assets/a/two.png").unlink()
        self.write_manifest([ENTRY])
        self.assertEqual(self.run_check(), ([], ["assets/a/two.png"]))

    def test_removing_the_entry_but_keeping_the_file_fails(self):
        self.write_manifest([ENTRY])
        self.assertTrue(self.run_check()[0])

    def test_removing_the_file_but_keeping_the_entry_fails(self):
        (self.root / "assets/a/two.png").unlink()
        self.assertTrue(self.run_check()[0])

    def test_changing_an_image_fails(self):
        (self.root / "assets/a/one.png").write_bytes(b"changed")
        self.assertTrue(self.run_check()[0])

    def test_changing_a_caption_fails(self):
        self.write_manifest([{**ENTRY, "caption": "Different."}, OTHER])
        self.assertTrue(self.run_check()[0])

    def test_adding_an_image_fails(self):
        (self.root / "assets/a/three.png").write_bytes(b"three")
        self.write_manifest([ENTRY, OTHER, {**OTHER, "file": "assets/a/three.png"}])
        self.assertTrue(self.run_check()[0])

    def supply(self, name, data):
        """Commit a file on a separate branch, as the owner does, then come back to main."""
        self.git("checkout", "-q", "-b", "supplied")
        (self.root / "incoming").mkdir(exist_ok=True)
        (self.root / "incoming" / name).write_bytes(data)
        self.git("add", "-A")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "supplied")
        self.git("checkout", "-q", "main")

    def test_adding_a_supplied_image_with_its_entry_passes(self):
        self.supply("three.png", b"three")
        (self.root / "assets/a/three.png").write_bytes(b"three")
        self.write_manifest([ENTRY, OTHER, {**OTHER, "file": "assets/a/three.png"}])
        self.assertEqual(assets_check.check(self.root, "main", "supplied:incoming"), ([], []))

    def test_adding_an_image_that_was_not_supplied_fails(self):
        self.supply("three.png", b"three")
        (self.root / "assets/a/three.png").write_bytes(b"something else")
        self.write_manifest([ENTRY, OTHER, {**OTHER, "file": "assets/a/three.png"}])
        self.assertTrue(assets_check.check(self.root, "main", "supplied:incoming")[0])

    def test_adding_an_entry_without_its_image_fails(self):
        self.supply("three.png", b"three")
        self.write_manifest([ENTRY, OTHER, {**OTHER, "file": "assets/a/three.png"}])
        self.assertTrue(assets_check.check(self.root, "main", "supplied:incoming")[0])

    def test_a_missing_supplied_branch_means_no_additions(self):
        (self.root / "assets/a/three.png").write_bytes(b"three")
        self.write_manifest([ENTRY, OTHER, {**OTHER, "file": "assets/a/three.png"}])
        self.assertTrue(assets_check.check(self.root, "main", "nowhere:incoming")[0])


if __name__ == "__main__":
    unittest.main()
