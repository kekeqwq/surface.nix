#!/usr/bin/env python3
"""Offline staging contract, with a fake msiextract (no firmware required)."""

import contextlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


script = Path(__file__).resolve().parents[1] / "scripts/surface-install-usb.py"
spec = importlib.util.spec_from_file_location("surface_install_usb", script)
staging = importlib.util.module_from_spec(spec)
spec.loader.exec_module(staging)


class Staging(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.msi = self.root / "my drivers.msi"
        self.msi.write_bytes(b"fixture")
        self.output = self.root / "out"
        self.err = io.StringIO()
        self.stdout = io.StringIO()
        for manager in (
            patch.object(staging.shutil, "which", return_value="msiextract"),
            patch.object(staging.subprocess, "run", side_effect=self.extract),
            contextlib.redirect_stderr(self.err),
            contextlib.redirect_stdout(self.stdout),
        ):
            self.enterContext(manager)

    def extract(self, args, *, check, stdout):
        self.assertEqual(args[:2], ["msiextract", "-C"])
        self.assertEqual(args[3], str(self.msi))
        for name in staging.REQUIRED.values():
            target = Path(args[2]) / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"\x7fELF" + name.encode())
        (Path(args[2]) / "unrelated-file").touch()

    def test_unknown_warns_but_stages_exactly_three(self):
        staging.stage(self.msi, self.output)
        self.assertIn("WARNING: this MSI hash has not passed", self.err.getvalue())
        files = {
            str(path.relative_to(self.output / "firmware"))
            for path in (self.output / "firmware").rglob("*") if path.is_file()
        }
        self.assertEqual(files, set(staging.REQUIRED))
        with self.assertRaisesRegex(SystemExit, "Refusing to overwrite"):
            staging.stage(self.msi, self.output)

    def test_known_msi_verifies_each_extracted_hash(self):
        fixture_output = self.root / "fixture"
        staging.stage(self.msi, fixture_output)
        expected = {name: staging.sha256(fixture_output / "firmware" / name) for name in staging.REQUIRED}
        with patch.dict(staging.VERIFIED, {staging.sha256(self.msi): expected}):
            self.err.truncate(0)
            self.err.seek(0)
            staging.stage(self.msi, self.output)
            self.assertEqual(self.err.getvalue(), "")
            self.assertIn("hardware-tested hashes", self.stdout.getvalue())
            expected[next(iter(expected))] = "0" * 64
            bad = self.root / "bad"
            with self.assertRaisesRegex(SystemExit, "does not match"):
                staging.stage(self.msi, bad)
            self.assertFalse(bad.exists())


if __name__ == "__main__":
    unittest.main()
