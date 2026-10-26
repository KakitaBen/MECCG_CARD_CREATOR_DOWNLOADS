import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.delivery import Delivery, illustration_components, version


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
