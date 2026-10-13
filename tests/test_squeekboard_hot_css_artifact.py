"""C3 GitHub ARM64 artifact preflight: exact hashes, provenance and no execution."""
from __future__ import annotations

import hashlib
import importlib.util
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/inspect-squeekboard-hot-css-artifact.py"
C2 = ROOT / "scripts/inspect-squeekboard-overlay-artifact.py"
spec = importlib.util.spec_from_file_location("acp_c3_readonly_abi", SCRIPT)
assert spec and spec.loader
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def mock_zip(root: Path, *, corrupt_manifest: bool = False, extra: bool = False):
    original = {"squeekboard-c3-hot-css-arm64": b"ELFtest",
                "squeekboard-c3-hot-css-arm64.deb": b"DEBtest"}
    attestation = (
        "HOT CSS SOURCE PATCH: APPLIED TO DISPOSABLE CI ONLY\n"
        "Vendor extracted C SHA-256: " + mod.VENDOR_C_SHA256 + "\n"
        "Patched compiler-input C SHA-256: " + mod.PATCHED_C_SHA256 + "\n"
        "Accepted C2 keyboard, Pi OSK, 23 immutable CSS palettes: UNCHANGED\n"
    )
    if corrupt_manifest:
        attestation = attestation.replace(mod.PATCHED_C_SHA256, "0" * 64)
    report = (
        "C3 hot-CSS candidate only. NEVER install this .deb on the commissioned Pi.\n"
        "Architecture: arm64\nVersion: 1.43.1-1+rpt1\n"
        "Hash of new C3 candidate .deb and ELF:\n"
        + hashlib.sha256(original["squeekboard-c3-hot-css-arm64"]).hexdigest()
        + "\n" + hashlib.sha256(original["squeekboard-c3-hot-css-arm64.deb"]).hexdigest()
    )
    files = dict(original, **{
        "ABI-AND-PACKAGE-REPORT.txt": report.encode(),
        "PATCH-ATTESTATION.txt": attestation.encode(),
        "PROVENANCE.txt": b"Vendor version: 1.43.1-1+rpt1\n",
        "build-depends.txt": b"cargo, python3\n",
        "build.log": b"compiled\n",
    })
    if extra:
        files["unexpected.bin"] = b"extra"
    archive = root / "dummy-c3.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for name, data in files.items():
            bundle.writestr(name, data)
    sizes = {name: (len(data), hashlib.sha256(data).hexdigest())
             for name, data in original.items()}
    return archive, sizes


class C3ArtifactTargetPreflightTests(unittest.TestCase):
    def test_zip_and_binary_hashes_pinned_to_verified_actions_artifact(self):
        self.assertEqual(mod.ARTIFACT_ZIP_SHA256,
                         "a2f615d31f7006a71867a92553c2aca02ee58ef130867856aeefcff0e2a59274")
        self.assertEqual(mod.EXPECTED_FILES["squeekboard-c3-hot-css-arm64"][1],
                         "fdd1da08861bbc45331e66a70996953ed6ebfb52915a0a5abeb21c585f40bfd5")
        self.assertEqual(mod.EXPECTED_FILES["squeekboard-c3-hot-css-arm64.deb"][1],
                         "4eaad98634a44dfdfe64c5038283688e34cf55ee1be59eb0cfff1724f4fb8e14")
        self.assertEqual(mod.VENDOR_C_SHA256, "bc1076aa72c9b56ab752bd84815593c1228f13e74033de87f231597b27e97353")
        self.assertEqual(mod.PATCHED_C_SHA256, "f4f45a776e11cc3d1e35631e5f19451e7746a6e53173467bf46580c688759f40")

    def test_good_synthetic_attested_zip_parses_without_writing(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, fake_expected = mock_zip(Path(tmp))
            before = archive.read_bytes()
            with mock.patch.object(mod, "ARTIFACT_ZIP_SHA256", mod.digest(before)), \
                 mock.patch.object(mod, "EXPECTED_FILES", fake_expected):
                contents = mod.checked_archive(archive)
                self.assertEqual(set(contents), mod.ALL_NAMES)
                self.assertEqual(contents["squeekboard-c3-hot-css-arm64"], b"ELFtest")
            self.assertEqual(before, archive.read_bytes())

    def test_rejects_unexpected_zip_sha_before_decompression(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, _ = mock_zip(Path(tmp))
            with self.assertRaisesRegex(mod.PreflightError, "ZIP SHA-256 mismatch"):
                mod.checked_archive(archive)

    def test_rejects_wrong_attested_patch(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, expected = mock_zip(Path(tmp), corrupt_manifest=True)
            with mock.patch.object(mod, "ARTIFACT_ZIP_SHA256", mod.digest(archive.read_bytes())), \
                 mock.patch.object(mod, "EXPECTED_FILES", expected):
                with self.assertRaisesRegex(mod.PreflightError, "patch attestation mismatch"):
                    mod.checked_archive(archive)

    def test_refuses_unexpected_extra_archive_member(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive, expected = mock_zip(Path(tmp), extra=True)
            with mock.patch.object(mod, "ARTIFACT_ZIP_SHA256", mod.digest(archive.read_bytes())), \
                 mock.patch.object(mod, "EXPECTED_FILES", expected):
                with self.assertRaisesRegex(mod.PreflightError, "unexpected C3 artifact entry"):
                    mod.checked_archive(archive)

    def test_target_inspection_rejects_root_or_non_arm64_before_decompression(self):
        with mock.patch.object(mod.os, "geteuid", return_value=0), \
             mock.patch.object(mod.platform, "machine", return_value="aarch64"):
            with self.assertRaisesRegex(mod.PreflightError, "never sudo"):
                mod.inspect(Path("/nonexistent.zip"))
        with mock.patch.object(mod.os, "geteuid", return_value=1000), \
             mock.patch.object(mod.platform, "machine", return_value="x86_64"):
            with self.assertRaisesRegex(mod.PreflightError, "never sudo"):
                mod.inspect(Path("/nonexistent.zip"))

    def test_readonly_check_reuses_separate_c2_inspector_without_changing_c2_file(self):
        before = C2.read_bytes()
        c2 = mod.c2_inspector()
        self.assertIn("squeekboard-overlay-arm64", c2.EXPECTED)
        self.assertEqual(before, C2.read_bytes())
        self.assertNotIn("squeekboard-c3-hot-css-arm64", c2.EXPECTED)

    def test_target_check_isolation_and_existing_c2_trial_remains_pinned(self):
        source = SCRIPT.read_text()
        for illegal in (
            "systemctl", "systemd-run", "pkill", "os.kill(", "dpkg -i",
            "gsettings set", "apt-get", "subprocess.Popen", "chmod(",
            ".unlink(", "squeekboard-overlay-arm64-test-only.zip",
        ):
            with self.subTest(illegal=illegal):
                self.assertNotIn(illegal, source)
        old_trial = (ROOT / "scripts/try-squeekboard-overlay.py").read_text()
        self.assertNotIn("inspect-squeekboard-hot-css-artifact", old_trial)
        self.assertNotIn("squeekboard-c3-hot-css", old_trial)

    def test_wrapper_reuses_old_abi_checker_with_c3_only_values(self):
        with mock.patch.object(mod.os, "geteuid", return_value=1000), \
             mock.patch.object(mod.platform, "machine", return_value="aarch64"), \
             mock.patch.object(mod, "checked_archive", return_value={"safe": b"ok"}), \
             mock.patch.object(mod, "c2_inspector") as loader, \
             mock.patch("builtins.print"):
            c2 = mock.Mock()
            c2.InspectionError = ValueError
            loader.return_value = c2
            mod.inspect(Path("/synthetic-c3.zip"))
            self.assertEqual(c2.EXPECTED, mod.EXPECTED_FILES)
            c2.inspect.assert_called_once_with(Path("/synthetic-c3.zip"))


if __name__ == "__main__":
    unittest.main()
