#!/usr/bin/env python3
"""Build a private Denali installer ISO from a user-supplied Microsoft MSI.

Build on AArch64 Linux, or supply a locally built AArch64 base via --base-iso.
This never writes a USB or the installed system; the final ISO stays outside Nix.
"""

import argparse
import hashlib
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parent
PAYLOAD = "surface-install"
staging = runpy.run_path(str(ROOT / "scripts/surface-install-usb.py"))
inspection = runpy.run_path(str(ROOT / "scripts/inspect-live-iso.py"))


def build_base():
    result = subprocess.check_output(
        ["nix", "build", "--no-link", "--print-out-paths",
         ".#packages.aarch64-linux.surface-live-iso"], cwd=ROOT, text=True
    ).splitlines()
    if len(result) != 1:
        raise ValueError("Expected a single base ISO build output")
    return Path(result[0]) / "iso/nixos-surface-live-aarch64.iso"


def entries(iso):
    names = subprocess.check_output(["bsdtar", "-tf", str(iso)], text=True).splitlines()
    return {name.removeprefix("./").rstrip("/"): name for name in names}


def file_hash(iso, member):
    with subprocess.Popen(["bsdtar", "-xOf", str(iso), member], stdout=subprocess.PIPE) as proc:
        digest = hashlib.file_digest(proc.stdout, "sha256").hexdigest()
        status = proc.wait()
    if status:
        raise ValueError(f"Could not read {member} from {iso}")
    return digest


def remaster(base, staged, result):
    print(f"Inspecting base ISO: {base}", flush=True)
    inspect = inspection["report"]
    base_report = inspect(base, "nixos-uki")
    base_entries = entries(base)
    if any(name == PAYLOAD or name.startswith(f"{PAYLOAD}/") for name in base_entries):
        raise ValueError("Base ISO already contains a private payload")
    subprocess.run(["xorriso", "-indev", str(base), "-outdev", str(result),
                    "-boot_image", "any", "replay", "-map", str(staged), f"/{PAYLOAD}"], check=True)
    report = inspect(result, "nixos-uki")
    for key in ("esp_sha256", "loader", "uki", "volume_label", "live_root"):
        if report[key] != base_report[key]:
            raise ValueError(f"Remaster changed the base ISO's {key}")
    found = entries(result)
    # Check the unchanged boot/live files and check every embedded payload file.
    if not base_entries.keys() <= found.keys():
        raise ValueError("Remaster omitted base ISO entries")
    root = report["live_root"]
    if file_hash(base, base_entries[root]) != file_hash(result, found[root]):
        raise ValueError("Remaster changed the Live root squashfs")
    embedded = {f"{PAYLOAD}/{p.relative_to(staged)}": p for p in staged.rglob("*") if p.is_file()}
    for name, path in embedded.items():
        if name not in found or file_hash(result, found[name]) != staging["sha256"](path):
            raise ValueError(f"Missing or corrupt embedded file: {name}")
    return report["iso_sha256"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--msi", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path, help="New, private output ISO path")
    parser.add_argument("--base-iso", type=Path, help="Reuse a locally built base ISO without private firmware")
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("run as an unprivileged user")
    os.umask(0o077)
    out = args.out.absolute()
    if out.is_symlink() or out.exists() or out.suffix.lower() != ".iso":
        parser.error("--out must be a new .iso file")
    out = out.resolve()
    msi = args.msi.resolve()
    if any(path.is_relative_to("/nix/store") or path.is_relative_to(ROOT) for path in (msi, out)):
        parser.error("Keep the MSI and private ISO outside the repository and Nix store")
    for tool in ("msiextract", "xorriso", "mcopy", "bsdtar", "zstd"):
        if not shutil.which(tool):
            parser.error(f"{tool} is required; see the local installer build instructions")
    with tempfile.TemporaryDirectory(prefix=".surface-live-", dir=out.parent) as work:
        work = Path(work).resolve()
        staged = work / PAYLOAD
        staging["stage"](msi, staged)
        shutil.copyfile(ROOT / "live/install.txt", staged / "INSTALL.txt")
        base = args.base_iso.resolve(strict=True) if args.base_iso else build_base()
        result = work / "private.iso"
        digest = remaster(base, staged, result)
        result.chmod(0o600)
        os.link(result, out)  # Publish only the verified image, without overwriting.
    print(f"{digest}  {out}")
    print("Private Live ISO verified. No disk was written.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
