import contextlib
import json
from types import SimpleNamespace
from unittest.mock import Mock, patch
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.delivery import Delivery, BuildFailure, illustration_components, version


class DeliveryTests(unittest.TestCase):
    def test_private_command_output_never_reaches_public_streams(self):
        with tempfile.TemporaryDirectory() as directory:
            delivery = Delivery(directory)
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                with self.assertRaises(RuntimeError):
                    delivery.run([sys.executable, "-c", "import sys;print('PRIVATE_SOURCE');print('PRIVATE_TRACEBACK',file=sys.stderr);sys.exit(7)"])
            self.assertEqual(output.getvalue(), "")
            self.assertIn("PRIVATE_SOURCE", delivery.log.read_text())
            self.assertIn("PRIVATE_TRACEBACK", delivery.log.read_text())

    def test_public_diagnostic_contains_only_allowlisted_step_and_category(self):
        with tempfile.TemporaryDirectory() as directory:
            delivery = Delivery(directory)
            script = Path(directory) / "standalone/build_installers.py"
            script.parent.mkdir()
            script.write_text("import os,json,sys\nfrom pathlib import Path\n"
                "Path(os.environ['MECCG_BUILD_STATUS_FILE']).write_text(json.dumps("
                "{'step':'silent-install','state':'failed','category':'subprocess-failed'}))\n"
                "print('PRIVATE_SOURCE');print('PRIVATE_TOKEN',file=sys.stderr);sys.exit(7)\n")
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
                with self.assertRaises(BuildFailure) as caught:
                    delivery.python("build_installers.py")
            self.assertEqual(output.getvalue(), "")
            self.assertEqual((caught.exception.step, caught.exception.category), ("silent-install", "subprocess-failed"))
            self.assertNotIn("PRIVATE", str(caught.exception))
            self.assertIn("PRIVATE_SOURCE", delivery.log.read_text())
            self.assertIn("PRIVATE_TOKEN", delivery.log.read_text())

    def test_untrusted_status_cannot_publish_private_strings(self):
        with tempfile.TemporaryDirectory() as directory:
            delivery = Delivery(directory)
            script = Path(directory) / "standalone/build_installers.py"
            script.parent.mkdir()
            script.write_text("import os,json,sys\nfrom pathlib import Path\n"
                "Path(os.environ['MECCG_BUILD_STATUS_FILE']).write_text(json.dumps("
                "{'step':'PRIVATE_SOURCE','state':'failed','category':'PRIVATE_TOKEN'}))\nsys.exit(1)\n")
            with self.assertRaises(BuildFailure) as caught:
                delivery.python("build_installers.py")
            self.assertEqual((caught.exception.step, caught.exception.category), ("build-installers", "subprocess-failed"))

    def test_independent_software_build_skips_legacy_assets_and_lfs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "data").mkdir()
            (root / "data/book.xlsx").write_bytes(b"literal")
            (root / "asset/illustrations/SET").mkdir(parents=True)
            (root / "asset/illustrations/SET/art.png").write_bytes(b"unmaterialized LFS pointer")
            (root / "asset/font.ttf").write_bytes(b"font")
            delivery = Delivery(root)
            delivery.collection_reference = Mock(return_value=({"version":"1.00"}, {}))
            delivery.legacy_resources = Mock(side_effect=AssertionError("Old application assets must not be used"))
            delivery.upload = Mock()
            delivery.run = Mock(side_effect=AssertionError("Software packaging must not fetch LFS"))
            def component(source, paths, output, label):
                self.assertTrue(all("illustrations" not in p.parts for p in paths))
                return {"name":label+".tar.gz","patch":{"name":label+".update.zip"}}
            def write(path,value): path.write_text(json.dumps(value))
            with patch.dict(sys.modules, {"distribution":SimpleNamespace(atomic_json=write),
                                         "package_delivery":SimpleNamespace(make_component=component)}):
                delivery.resources("v1.0.0", "unused", root, "1.00")
            self.assertEqual(json.loads((delivery.downloads / "illustrations-reference.json").read_text()), {"version":"1.00"})
            delivery.legacy_resources.assert_not_called()
            delivery.run.assert_not_called()

    def test_library_archive_references_cannot_download_arbitrary_urls(self):
        with tempfile.TemporaryDirectory() as directory:
            delivery = Delivery(directory)
            delivery.download = Mock()
            for url in ("http://github.com/owner/repo/file", "https://outside.test/archive.tar.gz",
                        "https://github.com/KakitaBen/MECCG_CARD_CREATOR_DOWNLOADS/releases/download/v0.60.31/archive.tar.gz"):
                with self.assertRaises(ValueError): delivery.download_library_asset(url,"archive.tar.gz")
            delivery.download_library_asset("https://github.com/KakitaBen/MECCG_CARD_CREATOR_DOWNLOADS/releases/download/meccg-illustrations-v1.2/archive.tar.gz","archive.tar.gz")
            delivery.download.assert_called_once_with("meccg-illustrations-v1.2", ["archive.tar.gz"])

    def test_reference_contains_only_illustrations_and_all_sixteen_lots(self):
        images = [{"name": f"illustrations-{index}.tar.gz", "files": {f"asset/illustrations/{index}.png": {}}} for index in range(16)]
        data = {"name": "old-workbook.tar.gz", "files": {"data/meccg_cartes.xlsx": {}}}
        self.assertEqual(illustration_components({"resources": [data, *images]}), images)
        with self.assertRaises(ValueError):
            illustration_components({"resources": images[:-1]})

    def test_release_input_cannot_be_used_as_a_shell_fragment(self):
        self.assertEqual(version("v0.59.48"), "v0.59.48")
        for value in ("v0.59.48;echo secret", "../v0.59.48", "main", "v0.59.48\n"):
            with self.assertRaises(ValueError):
                version(value)

    def test_release_asset_downloads_reject_paths_and_globs(self):
        with tempfile.TemporaryDirectory() as directory:
            delivery = Delivery(directory)
            for name in ("../source.zip", "all*", "data\\file", "file?[0]"):
                with self.assertRaises(ValueError):
                    delivery.download("v0.59.48", [name])


if __name__ == "__main__":
    unittest.main()
