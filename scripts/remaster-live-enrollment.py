#!/usr/bin/env python3
"""Add the fresh-install console script to the verified, private Denali r4 ISO."""

import argparse
import hashlib
import os
from pathlib import Path
import runpy
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
R4_SHA256 = "05bbdeb12d62583c3114564b897c456ccc806034d9df1bf598d0c403b8825b73"
MEMBER = "surface-install/enroll-key.sh"


def sha256(path):
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--r4", required=True, type=Path, help="Original verified private r4 ISO")
    parser.add_argument("--out", required=True, type=Path, help="New private ISO outside Git and the Nix store")
    args = parser.parse_args()
    os.umask(0o077)
    base = args.r4.resolve(strict=True)
    out = args.out.absolute()
    if os.geteuid() == 0 or out.exists() or out.is_symlink() or out.suffix != ".iso":
        parser.error("Run unprivileged and specify a new output ending in .iso")
    out = out.resolve()
    if any(path.is_relative_to(parent) for path in (base, out) for parent in (ROOT, Path("/nix/store"))):
        parser.error("Keep the private images outside the repository and the Nix store")
    if sha256(base) != R4_SHA256:
        parser.error("Input is not the byte-verified original r4 ISO")

    helpers = runpy.run_path(str(ROOT / "build.py"))
    report = helpers["inspection"]["report"]
    entries, file_hash = helpers["entries"], helpers["file_hash"]
    script = ROOT / "live/enroll-key.sh"
    subprocess.run(["bash", "-n", str(script)], check=True)
    before = report(base, "nixos-uki")
    original = entries(base)
    if MEMBER in original:
        raise ValueError("Enrollment script already present in the source")

    with tempfile.TemporaryDirectory(prefix=".denali-enrollment-", dir=out.parent) as directory:
        candidate = Path(directory) / "live.iso"
        subprocess.run(["xorriso", "-indev", str(base), "-outdev", str(candidate),
                        "-boot_image", "any", "replay", "-map", str(script), f"/{MEMBER}"], check=True)
        after = report(candidate, "nixos-uki")
        for key in ("esp_sha256", "loader", "uki", "volume_label", "live_root"):
            if before[key] != after[key]:
                raise ValueError(f"Remaster changed {key}")
        result = entries(candidate)
        if set(result) != set(original) | {MEMBER}:
            raise ValueError("The enrollment script must be the only addition")
        preserved = [before["live_root"], "surface-install/manifest.txt"]
        preserved += sorted(name for name in original if name.startswith("surface-install/firmware/") and name.endswith(".mbn"))
        if len(preserved) != 5:
            raise ValueError("Expected three private firmware files")
        for name in preserved:
            if file_hash(base, original[name]) != file_hash(candidate, result[name]):
                raise ValueError(f"Remaster changed {name}")
        if file_hash(candidate, result[MEMBER]) != sha256(script):
            raise ValueError("Embedded script differs from the local source")
        candidate.chmod(0o600)
        os.link(candidate, out)
    print(f"{after['iso_sha256']}  {out}")
    print("Verified image. Original ISO unchanged; no USB written.")


if __name__ == "__main__":
    main()
