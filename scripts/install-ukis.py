"""Finish systemd-boot installation using Denali zboot UKIs, not raw Images.

The stock installer owns generation selection/labels. We replace its generated
entry payloads after verifying the matching UKI. All private UKIs are written
only to the locally mounted ESP, never during a Nix build.
"""

import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ZAP = "qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn"


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def private_uki(inspector, components, cmdline, firmware, extra, target, system):
    with tempfile.TemporaryDirectory(prefix="surface-uki-") as tmp:
        work = Path(tmp)
        initrd = work / "initrd"
        initrd.write_bytes((components / "initrd").read_bytes())
        with initrd.open("ab") as output:
            if firmware is not None:
                payload = work / "payload"
                dest = payload / "surface-firmware" / ZAP
                dest.parent.mkdir(parents=True)
                dest.write_bytes(firmware.read_bytes())
                # Use the corresponding generation's public SQE/GMU alongside
                # the private zap, as in the accepted early-boot test.
                for microcode in ("gen70500_sqe.fw", "gen70500_gmu.bin"):
                    public = system / "firmware/qcom" / microcode
                    output_fw = payload / "surface-firmware/qcom" / microcode
                    if public.is_file():
                        output_fw.write_bytes(public.read_bytes())
                    else:
                        with output_fw.open("wb") as stream:
                            run("zstd", "-qdc", public.with_suffix(public.suffix + ".zst").resolve(strict=True), stdout=stream)
                paths = b"\0".join(os.fsencode(x.relative_to(payload)) for x in sorted(payload.rglob("*"))) + b"\0"
                archive = run("cpio", "--quiet", "-o", "-H", "newc", "-R", "+0:+0", "--null",
                              input=paths, cwd=payload, stdout=subprocess.PIPE).stdout
                # Pad to a four-byte boundary, as required for newc members.
                output.write(b"\0" * (-output.tell() % 4))
                output.write(archive)
            for path in extra:
                output.write(b"\0" * (-output.tell() % 4))
                output.write(path.read_bytes())
        release = (components / "uname").read_text().strip()
        run(os.environ.get("SURFACE_UKIFY", "ukify"), "build", "--linux", components / "linux", "--initrd", initrd,
            "--devicetree", components / "dtb", "--cmdline", cmdline,
            "--stub", components / "stub", "--os-release", "@" + str(system / "etc/os-release"),
            "--uname", release, "--output", target)
        run(sys.executable, inspector, target, "--expect-uki", release,
            "--expect-linux", components / "linux", "--expect-dtb", components / "dtb",
            "--expect-initrd", initrd, "--expect-cmdline", cmdline, stdout=subprocess.DEVNULL)


def finish(inspector, boot, current, firmware):
    run("mountpoint", "-q", boot)
    entries = boot / "loader/entries"
    destination = boot / "EFI/surface"
    destination.mkdir(parents=True, exist_ok=True)
    if firmware is not None and not firmware.is_file():
        raise FileNotFoundError(firmware)
    pending = []
    keep = set()
    current_entry = None
    for entry in sorted(entries.glob("nixos-*.conf")):
        lines = entry.read_text().splitlines()
        match = re.search(r"^options\s+init=(/nix/store/[^ /]+)/(?:init)(?:\s|$)", "\n".join(lines), re.M)
        if not match:
            # Remove stale custom entries whose old UKI no longer exists.
            # Valid rescue entries are not named nixos-* and are preserved.
            efi = re.search(r"^efi\s+(/\S+)", "\n".join(lines), re.M)
            if efi and not (boot / efi.group(1).lstrip("/")).is_file():
                pending.append((entry, None))
            continue
        system = Path(match[1])
        components = system / "surface-boot"
        if not components.is_dir():
            if system == current:
                raise ValueError(f"missing current Denali boot components: {system}")
            pending.append((entry, None))
            continue
        cmdline = next(line[8:] for line in lines if line.startswith("options "))
        # The generation's stage-1 initrd is already in its components.
        initrds = [line.split(None, 1)[1] for line in lines if line.startswith("initrd ")]
        extra = []
        for path in initrds[1:]:
            candidate = (boot / path.lstrip("/")).resolve()
            if not candidate.is_relative_to(boot.resolve()):
                raise ValueError(f"external initrd path: {path}")
            if candidate.is_file():
                extra.append(candidate)
        dig = hashlib.sha256(str(system).encode() + b"\0" + cmdline.encode())
        for path in ([firmware] if firmware is not None else []) + extra:
            dig.update(hashlib.file_digest(path.open("rb"), "sha256").digest())
        name = "generation-" + dig.hexdigest() + ".efi"
        dst = destination / name
        if not dst.exists():
            with tempfile.TemporaryDirectory(dir=destination, prefix=".install-") as tmp:
                staged = Path(tmp) / name
                private_uki(inspector, components, cmdline, firmware, extra, staged, system)
                os.replace(staged, dst)
        keep.add(dst)
        text = "\n".join([line for line in lines if line.startswith(("title ", "version ", "sort-key ", "machine-id "))]
                         + ["efi /EFI/surface/" + name]) + "\n"
        pending.append((entry, text))
        if system == current:
            current_entry = entry
    if current_entry is None:
        raise ValueError(f"systemd-boot did not emit the current generation: {current}")
    for entry, text in pending:
        if text is None:
            entry.unlink()
        else:
            tmp = entry.with_suffix(".tmp")
            tmp.write_text(text)
            os.replace(tmp, entry)
    # Exclude manually protected rescue entries and files from all cleanup.
    refs = set()
    for entry in entries.glob("*.conf"):
        for line in entry.read_text().splitlines():
            if line.startswith("efi /EFI/surface/"):
                refs.add(boot / line[4:].lstrip("/"))
    for path in destination.glob("generation-*.efi"):
        if path not in keep and path not in refs:
            path.unlink()
    run("sync", "-f", boot)
    print(f"Surface systemd-boot: {current_entry.name} -> verified Denali UKI")


if __name__ == "__main__":
    os.umask(0o077)
    inspector, boot, current = map(Path, sys.argv[1:4])
    finish(inspector, boot, current.resolve(), Path(sys.argv[4]) / ZAP if sys.argv[4] else None)
