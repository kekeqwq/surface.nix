#!/usr/bin/env python3
"""Stage the protected FullIO reference UKI privately after verifying its DTB."""

import argparse
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile


REFERENCE_RELEASE_SUFFIX = "-surface-fullio"
CHECKED_CAPTURE_SUFFIX = "-surface-fullio-checked-capture"
CHECKED_CAPTURE_MARKER = "microsoft,denali-fullio-checked-capture"
WSA_NODE = "/soc@0/soundwire@6b10000"
FEEDBACK_PARITY_MARKER = "qcom,denali-fullio-sidechain-audit"
GOLDEN_TOPOLOGY_SHA = "e7bb06a03e7bd9b869825a51775355a6743477d1579d78eb09fad5881cfb20f0"
PRE_SP_MARKER = "microsoft,denali-fullio-pre-sp-logger-audit"
PRE_SP_SHA = "86cc8afb4100c4713d077bbb0c3d71ebab910c25e75f2e29dbffcaec26a73a6c"
TOPOLOGY = "qcom/x1e80100/X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0-tplg.bin"
ZAP = "qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn"


def verify_reference_dtb(dtb, fdtget, *, checked_capture=False, pre_sp=False, feedback_parity=False):
    properties = set(subprocess.check_output([fdtget, "-p", dtb, "/sound"], text=True).splitlines())
    if "microsoft,denali-fullio-reference-render" not in properties:
        raise ValueError("DTB is missing the reference-render marker")
    if (CHECKED_CAPTURE_MARKER in properties) != checked_capture:
        raise ValueError("DTB checked-capture marker does not match the explicit experiment selection")
    if (PRE_SP_MARKER in properties) != pre_sp or (pre_sp and not checked_capture):
        raise ValueError("DTB pre-SP marker does not match the explicit checked-capture experiment")
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
    wsa = set(subprocess.check_output([fdtget, "-p", dtb, WSA_NODE], text=True).splitlines())
    if (FEEDBACK_PARITY_MARKER in wsa) != feedback_parity:
        raise ValueError("DTB feedback parity marker does not match the explicit experiment")
    if feedback_parity and (pre_sp or not checked_capture or "qcom,denali-fullio-feedback-capture-test" in wsa or not {
        "qcom,denali-fullio-feedback", "qcom,denali-fullio-link-gate", "qcom,denali-fullio-wait-frame-stop",
    } <= wsa):
        raise ValueError("DTB feedback parity requires protected checked capture and frame-stop admission")
    for node in (f"{WSA_NODE}/speaker@0,0", f"{WSA_NODE}/speaker@0,1"):
        node_properties = set(subprocess.check_output([fdtget, "-p", dtb, node], text=True).splitlines())
        if "qcom,denali-fullio-reference-codec" not in node_properties:
            raise ValueError(f"DTB node {node} is missing the reference-codec marker")


def keyboard_cmdline(line, kernel_params, enabled):
    prefix = "surface_hid_core.denali_hhkb="
    expected = prefix + "1"
    selection = [p for p in kernel_params.split() if p.startswith(prefix)]
    if selection != ([expected] if enabled else []):
        raise ValueError("candidate keyboard parameter does not match the explicit experiment selection")
    if any(p.startswith(prefix) for p in line.split()):
        raise ValueError("stage the keyboard experiment from a normal boot")
    return line + " " + expected if enabled else line


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("system", type=Path, help="built candidate toplevel")
    cli.add_argument("private_firmware", type=Path)
    cli.add_argument("stage_parent", type=Path, help="private directory off the ESP")
    cli.add_argument("--fdtget", default="fdtget", help="DTB reader from dtc (default: fdtget on PATH)")
    cli.add_argument("--checked-capture", action="store_true", help="require the checked MicArray experiment")
    cli.add_argument("--pre-sp-logger-audit", action="store_true", help="require the pre-SP topology diagnostic")
    cli.add_argument("--feedback-parity-audit", action="store_true", help="require the feedback parity diagnostic")
    cli.add_argument("--denali-hhkb", action="store_true", help="require the opt-in Denali keyboard configuration")
    cli.add_argument("--zstd", default="zstd", help="firmware decompressor (default: zstd on PATH)")
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
    expected_suffix = CHECKED_CAPTURE_SUFFIX if args.checked_capture else REFERENCE_RELEASE_SUFFIX
    if not version.endswith(expected_suffix):
        cli.error("candidate does not have the expected FullIO kernel release")
    # Require the protected render DTB, not just a matching release string.
    try:
        verify_reference_dtb(pieces / "dtb", args.fdtget, checked_capture=args.checked_capture,
                             pre_sp=args.pre_sp_logger_audit, feedback_parity=args.feedback_parity_audit)
        if args.pre_sp_logger_audit or args.feedback_parity_audit:
            path = candidate / "firmware" / TOPOLOGY
            packed = path.with_suffix(".bin.zst")
            if path.exists() and packed.exists():
                raise ValueError("ambiguous diagnostic topology packaging")
            data = path.read_bytes() if path.exists() else subprocess.check_output(
                [args.zstd, "-dc", packed.resolve(strict=True)]
            )
            expected = PRE_SP_SHA if args.pre_sp_logger_audit else GOLDEN_TOPOLOGY_SHA
            if hashlib.sha256(data).hexdigest() != expected:
                raise ValueError("candidate does not contain the exact diagnostic topology")
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        cli.error(f"cannot verify reference fixture DTB: {exc}")
    line = Path("/proc/cmdline").read_text().strip()
    match = re.findall(r"(?:^|\s)init=(\S+)", line)
    if match != [str(active / "init")] or "firmware_class.path=/surface-firmware" not in line.split():
        cli.error("the running Denali command line does not match its booted closure")
    line = re.sub(r"(?<!\S)init=\S+", f"init={candidate}/init", line, count=1)
    try:
        line = keyboard_cmdline(line, (candidate / "kernel-params").read_text(), args.denali_hhkb)
    except (OSError, ValueError) as exc:
        cli.error(str(exc))
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location("install_ukis", here / "install-ukis.py")
    installer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(installer)
    with tempfile.TemporaryDirectory(prefix=".build-", dir=parent) as tmp:
        stage = Path(tmp) / "fullio-reference.efi"
        installer.private_uki(here / "inspect-efi-payload.py", pieces, line, firmware, [], stage, candidate)
        # Publish only through an exclusive hardlink; no existing UKI is replaced.
        output = parent / stage.name
        stage.chmod(0o600)
        os.link(stage, output)
    print(f"Verified private UKI: {output} (not installed or selected)")


if __name__ == "__main__":
    main()
