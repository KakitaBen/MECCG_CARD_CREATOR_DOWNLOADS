"""Public orchestration only. Application source and detailed logs stay on the runner."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import traceback

REPO = "KakitaBen/MECCG_CARD_CREATOR_DOWNLOADS"
PLATFORMS = ("windows-x64", "macos-x64", "macos-arm64", "linux-x64")


def version(value):
    if not re.fullmatch(r"v\d+\.\d+\.\d+", value):
        raise ValueError("Invalid release version")
    return value


def illustration_components(manifest):
    result = []
    for component in manifest["resources"]:
        files = component.get("files", {})
        if files and all(name.startswith("asset/illustrations/") for name in files):
            result.append(component)
    if len(result) != 16:
        raise ValueError("A complete illustration baseline is required")
    return result


class Delivery:
    def __init__(self, source):
        self.source = Path(source).resolve()
        self.build = self.source / "build/public-delivery"
        self.build.mkdir(parents=True, exist_ok=True)
        self.log = self.build / "private-build.log"
        self.downloads = self.build / "downloads"
        self.downloads.mkdir(exist_ok=True)

    def run(self, arguments, *, cwd=None, capture=False):
        with self.log.open("ab") as log:
            result = subprocess.run([str(item) for item in arguments], cwd=cwd or self.source,
                                    stdout=subprocess.PIPE if capture else log, stderr=log)
        if result.returncode:
            raise RuntimeError("Private command failed")
        return result.stdout.decode("utf-8").strip() if capture else None

    def python(self, script, *arguments):
        self.run([sys.executable, self.source / "standalone" / script, *arguments])

    def download(self, release, names, destination=None):
        destination = destination or self.downloads
        destination.mkdir(parents=True, exist_ok=True)
        for name in names:
            if Path(name).name != name or any(x in name for x in ("/", "\\", ":", "*", "?", "[")):
                raise ValueError("Invalid release asset name")
            self.run(["gh", "release", "download", release, "--repo", REPO,
                      "--pattern", name, "--dir", destination, "--clobber"])

    def upload(self, release, files):
        files = list(files)
        if not files:
            raise ValueError("No release assets produced")
        self.run(["gh", "release", "upload", release, *files, "--clobber", "--repo", REPO])

    def prepare(self, commit):
        if not re.fullmatch(r"[0-9a-f]{40}", commit):
            raise ValueError("A full source commit is required")
        if self.run(["git", "rev-parse", "HEAD"], capture=True) != commit:
            raise ValueError("Source commit differs from the selected commit")
        release = version((self.source / "VERSION.txt").read_text(encoding="utf-8-sig").strip())
        if self.run(["gh", "repo", "view", REPO, "--json", "visibility", "--jq", ".visibility"], capture=True) != "PUBLIC":
            raise ValueError("The download repository must be public")
        existing = json.loads(self.run(["gh", "api", f"repos/{REPO}/releases?per_page=100"], capture=True))
        match = next((item for item in existing if item["tag_name"] == release), None)
        if match and not match["draft"]:
            raise ValueError("Published releases cannot be replaced")
        if not match:
            self.run(["gh", "release", "create", release, "--repo", REPO, "--draft", "--prerelease",
                      "--title", f"MECCG Card Creator {release} — version de test",
                      "--notes", "Installateurs en cours de validation. Signatures de distribution à finaliser."])
        with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as stream:
            stream.write(f"version={release}\n")

    def resources(self, release, base, baseline):
        # Both checkouts use LFS_SKIP_SMUDGE. Compare Git trees before reusing
        # the already verified images, without another private LFS transfer.
        current = self.run(["git", "rev-parse", "HEAD:asset/illustrations"], capture=True)
        previous = self.run(["git", "rev-parse", "HEAD:asset/illustrations"], cwd=Path(baseline).resolve(), capture=True)
        if current != previous:
            raise ValueError("Illustrations changed; prepare a new verified baseline")
        base_folder = self.build / "baseline"
        self.download(base, ["manifest.json"], base_folder)
        manifest = json.loads((base_folder / "manifest.json").read_text(encoding="utf-8"))
        from distribution import Installer, atomic_json, digest, validate_manifest
        from package_delivery import make_component, make_update_patch
        validate_manifest(manifest, "windows-x64")
        if manifest.get("sample_assets") or manifest["version"] != base:
            raise ValueError("The baseline must contain the complete collection")
        components = illustration_components(manifest)
        for component in components:
            self.download(base, [component["name"]])
            archive = self.downloads / component["name"]
            if archive.stat().st_size != component["size"] or digest(archive) != component["sha256"]:
                raise ValueError("Baseline download checksum mismatch")
            # The old baseline predates file-level updates. Verify its original
            # inventory while extracting one lot at a time; retain the original
            # tarball, hashes and inventory and add only the indexed ZIP.
            if not component.get("patch"):
                with tempfile.TemporaryDirectory(prefix="index-", dir=self.build) as directory:
                    root = Path(directory)
                    Installer(self.build / "verification").extract(archive, component, root)
                    component["patch"] = make_update_patch(root, component["files"], self.downloads,
                                                           component["name"].removesuffix(".tar.gz"))
            else:
                self.download(base, [component["patch"]["name"]])
        data = [p for folder in ("data", "layouts") for p in (self.source / folder).rglob("*") if p.is_file()]
        data.extend(self.source / name for name in ("CHANGELOG.txt", "README.md", "project_services.json")
                    if (self.source / name).is_file())
        graphics = [p for p in (self.source / "asset").rglob("*") if p.is_file()
                    and not p.relative_to(self.source).as_posix().startswith("asset/illustrations/")]
        components = [make_component(self.source, data, self.downloads, "data-layouts"),
                      make_component(self.source, graphics, self.downloads, "graphics-fonts"), *components]
        atomic_json(self.downloads / "resources.json", components)
        self.upload(release, [self.downloads / name for c in components for name in (c["name"], c["patch"]["name"])]
                    + [self.downloads / "resources.json"])

    def program(self, release, platform):
        self.run([sys.executable, "-m", "pip", "install", "-r", "generator/requirements-gui.txt", "pyinstaller>=6.12,<7"])
        self.python("build_delivery_program.py", "--output", self.build / "program")
        self.python("package_delivery.py", "--program", self.build / "program", "--platform", platform, "--output", self.downloads)
        self.upload(release, [*self.downloads.glob("*.tar.gz"), *self.downloads.glob("*.update.zip"),
                              self.downloads / (platform + ".json")])

    def manifest(self, release):
        self.download(release, ["resources.json", *[key + ".json" for key in PLATFORMS]])
        self.python("assemble_delivery.py", "--downloads", self.downloads, "--version", release,
                    "--base-url", f"https://github.com/{REPO}/releases/download/{release}")
        files = [self.downloads / "manifest.json"]
        for key in PLATFORMS:
            target = self.downloads / ("installer-config-" + key + ".json")
            shutil.copyfile(self.downloads / (key + "-config/installer_config.json"), target)
            files.append(target)
        self.upload(release, files)

    def installer(self, release, platform):
        self.run([sys.executable, "-m", "pip", "install", "-r", "standalone/requirements-delivery.txt"])
        self.download(release, ["manifest.json", "installer-config-" + platform + ".json"])
        manifest = json.loads((self.downloads / "manifest.json").read_text(encoding="utf-8"))
        from distribution import validate_manifest
        package = validate_manifest(manifest, platform)
        self.download(release, [c["name"] for c in manifest["resources"] + package["components"]])
        config = self.build / "installer_config.json"
        shutil.copyfile(self.downloads / ("installer-config-" + platform + ".json"), config)
        proof = self.build / ("proof-" + platform + ".json")
        self.python("smoke_delivery.py", "--downloads", self.downloads, "--report", proof)
        output = self.build / "installers"
        self.python("build_installers.py", "--config", config, "--output", output, "--version", release, "--verify")
        report = json.loads(proof.read_text(encoding="utf-8"))
        if (report.get("status") != "passed" or not report.get("frozen_gui_started")
                or not report.get("pillow_tk_pixels") or not report.get("bundled_service_https")):
            raise ValueError("The installed application did not pass validation")
        report["bundled_https_verified"] = True
        proof.write_text(json.dumps(report, indent=2), encoding="utf-8")
        self.upload(release, [*output.glob("*.exe"), *output.glob("*.deb"), *output.glob("*.pkg"), proof])

    def mac(self, release):
        self.download(release, ["MECCG-arm64.pkg", "MECCG-x86_64.pkg"])
        output = self.build / "MECCG-Installer.pkg"
        self.run(["productbuild", "--distribution", self.source / "standalone/macos_distribution.xml",
                  "--package-path", self.downloads, output])
        self.run(["sudo", "installer", "-pkg", output, "-target", "/"])
        launcher = "/Applications/MECCG Card Creator.app/Contents/MacOS/MECCG Launcher"
        self.run([launcher, "--help"])
        self.run([launcher, "--check-https"])
        self.upload(release, [output])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "resources", "program", "manifest", "installer", "mac"))
    parser.add_argument("--source", type=Path, default=Path("source"))
    parser.add_argument("--commit")
    parser.add_argument("--release")
    parser.add_argument("--base", default="v0.59.46")
    parser.add_argument("--baseline", type=Path, default=Path("source-baseline"))
    parser.add_argument("--platform", choices=PLATFORMS)
    args = parser.parse_args()
    delivery = Delivery(args.source)
    sys.path[:0] = [str(delivery.source / "generator"), str(delivery.source / "standalone")]
    try:
        release = version(args.release) if args.release else None
        if args.mode == "prepare":
            delivery.prepare(args.commit)
        elif args.mode == "resources":
            delivery.resources(release, version(args.base), args.baseline)
        elif args.mode == "program":
            delivery.program(release, args.platform)
        elif args.mode == "manifest":
            delivery.manifest(release)
        elif args.mode == "installer":
            delivery.installer(release, args.platform)
        else:
            delivery.mac(release)
    except Exception as error:
        with delivery.log.open("a", encoding="utf-8") as log:
            traceback.print_exc(file=log)
        print(f"Build stopped ({type(error).__name__}). Detailed source logs are not published.", flush=True)
        return 1
    print("Completed: " + args.mode, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
