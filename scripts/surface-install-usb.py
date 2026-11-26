#!/usr/bin/env python3
"""Stage Surface firmware from a manually downloaded driver MSI.

The public live ISO cannot contain these files. Download the package yourself,
then pass its path. This does not read an old installation or a previous USB.

    python3 scripts/surface-install-usb.py --msi ~/Downloads/SurfacePro11_....msi

It stages only the required firmware in a private tree and prints hashes.
This command does not build a Live CD or write a USB disk.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

DOWNLOAD_PAGE = "https://www.microsoft.com/en-us/download/details.aspx?id=106119"
DOWNLOAD_URL = (
    "https://download.microsoft.com/download/92821b24-203a-4ce5-9a3a-5df3160a2fe3/"
    "SurfacePro11_ARM_Win11_26100_26.094.41119.0.msi"
)
EXPECTED_NAME = "SurfacePro11_ARM_Win11_26100_26.094.41119.0.msi"
EXPECTED_BYTES = 647004160

# Resolve the Windows filenames using MSI metadata, not raw CAB member IDs.
REQUIRED = {
    "qcom/x1e80100/microsoft/Denali/adsp_dtb.mbn": "SurfaceUpdate/proextadsp/adsp_dtbs.elf",
    "qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn": "SurfaceUpdate/proextadsp/qcadsp8380.mbn",
    "qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn": "SurfaceUpdate/qcdx/qcdxkmsuc8380.mbn",
}

# SHA-256 of complete MSI -> SHA-256 of each staged file. Informational, not
# a pin: other MSI versions can be staged if they have the expected layout.
VERIFIED = {
    # Denali non-5G OLED, FullIO Gen25 test closure; see firmware provenance docs.
    "8b299016027a4a87f50cf168f69ca1fb8dedc9a0612fcd6cff89b9bc64135ec2": {
        "qcom/x1e80100/microsoft/Denali/adsp_dtb.mbn": "544bd795cb06cf8dee8119ede2a667f01066b2f1b9e4348f1772d080e2026ff4",
        "qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn": "921870a839ee2aba647b04598d62ed96f3d2d5dfbb2499fc842f9a6ff0e0da13",
        "qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn": "c89711a60240f29cb5df13f7b904642b78b7d9d6e614473751f7bf4049fab137",
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def guide() -> None:
    print("Download the Surface Pro 11 Snapdragon driver MSI yourself:")
    print(f"  page: {DOWNLOAD_PAGE}")
    print(f"  file: {DOWNLOAD_URL}")
    print(f"  name: {EXPECTED_NAME}")
    print(f"  size: {EXPECTED_BYTES} bytes")
    print("Then run:")
    print("  python3 scripts/surface-install-usb.py --msi /path/to/that.msi")


def select(root: Path) -> dict[str, Path]:
    chosen = {}
    for destination, name in REQUIRED.items():
        path = root / name
        if path.resolve() != path or not path.is_file() or path.stat().st_size == 0:
            raise SystemExit(f"Missing or invalid firmware at MSI path: {name}")
        with path.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                raise SystemExit(f"Expected an ELF firmware image at MSI path: {name}")
        chosen[destination] = path
    return chosen


def stage(msi: Path, output: Path) -> None:
    if not msi.is_file():
        raise SystemExit(f"MSI not found: {msi}")
    digest = sha256(msi)
    print(f"MSI: {msi}")
    print(f"bytes: {msi.stat().st_size}")
    print(f"sha256: {digest}")
    if output.exists() or output.is_symlink():
        raise SystemExit(f"Refusing to overwrite existing output: {output}")
    expected = VERIFIED.get(digest)
    if expected is None:
        print("WARNING: this MSI hash has not passed Surface hardware regression testing. Use at your own risk.", file=sys.stderr)
    tool = shutil.which("msiextract")
    if not tool:
        raise SystemExit("Need msiextract from msitools (e.g. nix shell nixpkgs#msitools).")
    with tempfile.TemporaryDirectory(prefix="surface-msi-") as temporary:
        extracted = Path(temporary).resolve()
        subprocess.run([tool, "-C", str(extracted), str(msi)], check=True, stdout=subprocess.DEVNULL)
        chosen = select(extracted)
        hashes = {destination: sha256(source) for destination, source in chosen.items()}
        if sha256(msi) != digest:
            raise SystemExit("MSI changed during extraction; refusing to stage it.")
        if expected is not None and hashes != expected:
            raise SystemExit("Extracted firmware does not match the known MSI manifest.")
        output.mkdir(mode=0o700)
        firmware = output / "firmware"
        lines = [f"msi.name {msi.name}", f"msi.bytes {msi.stat().st_size}", f"msi.sha256 {digest}"]
        for destination, source in chosen.items():
            target = firmware / destination
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            print(f"{hashes[destination]}  {destination}  <= {source.name}")
            lines.append(f"file {hashes[destination]} {target.stat().st_size} {destination}")
        (output / "manifest.txt").write_text("\n".join(lines) + "\n")
    if expected is not None:
        print("MSI and all three files match the hardware-tested hashes.")
    print(f"Staged private firmware: {firmware}")
    print(f"Manifest: {output / 'manifest.txt'}")
    print("No USB was written.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--msi", type=Path, help="Path to the manually downloaded MSI")
    parser.add_argument("--out", type=Path, help="Directory for the extracted firmware tree")
    args = parser.parse_args()
    os.umask(0o077)
    if os.geteuid() == 0:
        parser.error("run offline extraction as an unprivileged user")
    if args.msi is None:
        guide()
        raise SystemExit(2)
    output = args.out or args.msi.with_suffix(".firmware")
    stage(args.msi.resolve(), output.absolute())


if __name__ == "__main__":
    main()
