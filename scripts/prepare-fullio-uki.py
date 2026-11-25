#!/usr/bin/env python3
"""Build a verified FullIO test UKI privately; never touch the ESP.

The muted mode stages a PA-off fixture; the reference mode stages the
protected reference-render fixture after verifying its exact DT markers.
"""

import argparse
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile


RELEASE_SUFFIXES = ("-surface-fullio-muted-test", "-surface-fullio-feedback-probe")
ZAP = "qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn"


def verify_pa_off_dtb(dtb, fdtget):
    properties = set(subprocess.check_output([fdtget, "-p", dtb, "/sound"], text=True).splitlines())
    if "microsoft,denali-fullio-muted-test" not in properties:
        raise ValueError("DTB is missing the FullIO muted marker")
    forbidden = {"microsoft,denali-fullio-post-pa-test", "microsoft,denali-fullio-pa-on-smoke"}
    if unsafe := properties & forbidden:
        raise ValueError(f"DTB carries PA-enabling markers: {', '.join(sorted(unsafe))}")


def verify_reference_dtb(dtb, fdtget):
    properties = set(subprocess.check_output([fdtget, "-p", dtb, "/sound"], text=True).splitlines())
    if "microsoft,denali-fullio-reference-render" not in properties:
        raise ValueError("DTB is missing the reference-render marker")
    forbidden = {
        "microsoft,denali-fullio-muted-test",
        "microsoft,denali-fullio-post-pa-test",
        "microsoft,denali-fullio-pa-on-smoke",
        "microsoft,denali-fullio-capture-only",
        "microsoft,denali-fullio-dsp-start-audit",
        "microsoft,denali-fullio-dsp-prepare-audit",
        "microsoft,denali-fullio-clock-off-audit",
        "microsoft,denali-fullio-ring-map-audit",
        "microsoft,denali-fullio-sidechain-audit",
    }
    if unsafe := properties & forbidden:
        raise ValueError(f"DTB carries fixture/audit markers: {', '.join(sorted(unsafe))}")
    for node in ("/soc@0/soundwire@6b10000/speaker@0,0", "/soc@0/soundwire@6b10000/speaker@0,1"):
        node_properties = set(subprocess.check_output([fdtget, "-p", dtb, node], text=True).splitlines())
        if "qcom,denali-fullio-reference-codec" not in node_properties:
            raise ValueError(f"DTB node {node} is missing the reference-codec marker")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("system", type=Path, help="built candidate toplevel")
    cli.add_argument("private_firmware", type=Path)
    cli.add_argument("stage_parent", type=Path, help="private directory off the ESP")
    cli.add_argument("--mode", choices=("muted", "reference"), default="muted",
                     help="muted PA-off fixture (default) or protected reference-render fixture")
    cli.add_argument("--fdtget", default="fdtget", help="DTB reader from dtc (default: fdtget on PATH)")
    args = cli.parse_args()
    os.umask(0o077)
    parent = args.stage_parent.resolve(strict=True)
    firmware = (args.private_firmware / ZAP).resolve(strict=True)
    store = Path("/nix/store")
    if not parent.is_dir() or parent.stat().st_uid != os.getuid() or parent.stat().st_mode & 0o077:
        cli.error("stage parent must be owned by the caller with no group/other access")
    if any(parent.is_relative_to(p) for p in (Path("/boot"), Path("/efi"), store)):
        cli.error("stage parent must be off the ESP and outside the Nix store")
    fs = subprocess.check_output(["findmnt", "-n", "-o", "FSTYPE", "--target", parent], text=True)
    if fs.strip() in {"vfat", "msdos", "exfat"}:
        cli.error("refusing to stage private payloads on a FAT filesystem")
    if firmware.is_relative_to(store) or not firmware.is_file():
        cli.error("expected private zap outside the Nix store")
    candidate = args.system.resolve(strict=True)
    active = Path("/run/booted-system").resolve(strict=True)
    if candidate == active or candidate.parent != store:
        cli.error("expected an unbooted candidate from the local Nix store")
    pieces = candidate / "surface-boot"
    version = (pieces / "uname").read_text().strip()
    if not version.endswith(RELEASE_SUFFIXES):
        cli.error("candidate is not a muted FullIO build")
    # The suffix is shared by historical PA-on candidates. Verify the exact
    # binary DTB that private_uki() will embed before creating any output.
    try:
        if args.mode == "reference":
            verify_reference_dtb(pieces / "dtb", args.fdtget)
        else:
            verify_pa_off_dtb(pieces / "dtb", args.fdtget)
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        cli.error(f"cannot verify {args.mode} fixture DTB: {exc}")
    line = Path("/proc/cmdline").read_text().strip()
    match = re.findall(r"(?:^|\s)init=(\S+)", line)
    if match != [str(active / "init")] or "firmware_class.path=/surface-firmware" not in line.split():
        cli.error("the running Denali command line does not match its booted closure")
    line = re.sub(r"(?<!\S)init=\S+", f"init={candidate}/init", line, count=1)
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("install_ukis", here / "install-ukis.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    with tempfile.TemporaryDirectory(prefix=".build-", dir=parent) as tmp:
        stage = Path(tmp) / f"fullio-{args.mode}.efi"
        installer.private_uki(here / "inspect-efi-payload.py", pieces, line, firmware, [], stage, candidate)
        # Publish only through an exclusive hardlink; no existing UKI is replaced.
        output = parent / f"fullio-{args.mode}.efi"
        stage.chmod(0o600)
        os.link(stage, output)
    print(f"Verified private UKI: {output} (not installed or selected)")


if __name__ == "__main__":
    main()
