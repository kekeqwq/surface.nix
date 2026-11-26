# surface.nix

Opt-in NixOS hardware support for the **Surface Pro 11 Denali non-5G OLED** (Snapdragon X1E80100 / Adreno X1-85). The regular system and desktop live in the consuming flake, not here. This replaces the standalone bring-up flake.

```nix
{
  imports = [ inputs.surface.nixosModules.default ];
  surface.devices.denali = {
    enable = true;
    privateFirmwareDirectory = "/var/lib/surface-firmware";
  };
  boot.loader.systemd-boot.enable = true;
}
```

Set `nixpkgs.hostPlatform` to `aarch64-linux`. Follow the consuming flake's `nixpkgs` input. The default kernel is kernel.org `next-20261124` with the audited Denali Kconfig and isolated SPI-HID/QSPI touch queue. The module supplies the OLED DTB, native device firmware, touch, and ARM64 zboot UKIs. The host owns its partitions, accounts, and desktop. `surface.devices.denali.niriOutputs` is an optional value to pass into an existing Niri configuration, not a compositor installation.

## Installer image

Build locally with native AArch64 Linux and an owner-downloaded Surface driver
MSI (see below):

```sh
nix develop .#surface-live -c \
  python3 build.py --msi '/path/to/SurfacePro11_ARM.msi' --out "$HOME/surface-private.iso"
```

`build.py` builds the text-only `surface-live-iso` base, then adds the three
private files and installation instructions under `/surface-install` outside
Nix. With `--base-iso /path/to/nixos-surface-live-aarch64.iso`, a locally built
AArch64 base can be reused without another Nix build. The remaster verifies
that the EFI payload and Live squashfs are unchanged and reads back the
embedded firmware hashes. It does not write a USB device.

The Live environment includes NetworkManager, Git, `fdisk`, `btrfs-progs`,
`cryptsetup`, `libfido2` and the `TER16x32` console font, but no desktop. Root
SSH accepts an empty password from any reachable host; boot only on an
isolated trusted network. Do not publish the private ISO. Installing to a new
disk is a separate step; see [`live/install.txt`](live/install.txt).

## Private firmware

Before building a boot entry, provision the owner-held firmware on the **root filesystem** in a root-managed directory, not in the flake, Nix store, or a public cache. Populate the applicable paths under the configured directory:

```text
qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn
qcom/x1e80100/microsoft/Denali/adsp_dtb.mbn
qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn
```

The Microsoft GPU zap file is required with this option; the two matching ADSP files enable native audio. Download the [official Surface Pro 11 Snapdragon driver MSI](https://www.microsoft.com/en-us/download/details.aspx?id=106119) yourself, then stage the three files offline without Windows:

```sh
nix shell nixpkgs#msitools nixpkgs#python3 -c \
  python3 scripts/surface-install-usb.py --msi /path/to/SurfacePro11_ARM.msi
```

The script leaves the MSI untouched and writes a private firmware tree and hash manifest beside it (or to `--out`). The known `26.094.41119.0` package passed [Denali OLED hardware regression](docs/gpu-rendering-investigation.md#msi-hardware-regression-2026-11-25). Other MSI hashes warn but aren't blocked solely by the hash; the required files still have to be present. This command does not build an ISO or write a USB device.

On boot the activation script makes the private/public firmware union available **before root coldplug**. The boot installer adds the private zap to the embedded initrd on the local ESP, outside Nix. Treat installed private UKIs as owner-only files; do not redistribute them. Use `nixos-rebuild switch --flake <system-flake>#<host>` and retain an independently verified recovery UKI. Recovery entries must not be named `nixos-*.conf` or store their payload under `/EFI/nixos/`, where the ordinary NixOS boot installer performs cleanup.

## Bluetooth

Some Denali WCN7850 controllers report a placeholder address, so the kernel
does not expose a configured controller to BlueZ. Set
`surface.devices.denali.bluetoothAddress` to this device's factory Bluetooth
address where available. A test host can instead choose a stable, distinct
locally administered address. On UART controller add, the module waits for
firmware setup and supplies the address only if the controller needs one.
BlueZ still owns power policy and pairing. This does not modify Wi-Fi or
unrelated Bluetooth adapters.

## Protected internal speakers (opt-in)

`nixosModules.fullio-reference-render` is the only FullIO profile. It extends
`nixosModules.default` on ARM64 Denali with the pinned v19c topology and
Golden v33 protected stereo route, and keeps MicArray available to the
desktop. The endpoint is set to −3 dB; use the desktop slider for normal
changes. The profile does not start an acoustic capture service.

Validate changes first with a private one-shot boot and keep an independent
recovery entry. The consuming Surface host selects this module explicitly;
it does not alter the default kernel for other consumers. On the test host,
`scripts/build-fullio-fixture.sh` builds only, `scripts/prepare-fullio-uki.py`
stages the reference UKI outside the ESP, and
`scripts/arm-fullio-reference-once.sh` performs the recovery preflight before
arming it. Do not put the private UKI in Git or the Nix store. See the
[listening checkpoint](docs/audio-protection-audit.md#listening-checkpoint--2026-11-25)
for evidence and remaining limits. The six kernel patches live in
[`pkgs/patches/fullio`](pkgs/patches/fullio); earlier experiment entry points
are available in Git history, not as current flake outputs.

## Validation and development

The native installation passed 2880×1920 at 120 Hz, finger touch, and Adreno UBWC scanning with no tiling/compression workaround. The early firmware fix and direct scanout evidence are recorded in the [validation notes](docs/gpu-rendering-investigation.md). Pen, suspend, Bluetooth persistence, and full audio acceptance are separate work. No repartitioning, firmware flashing, or speaker gain changes are performed here.

The persistent local Kbuild workbench is for development, not deployment:

```sh
nix develop .#surface-next -c bash scripts/surface-next-workbench.sh build
```

This retains writable source and Kbuild `O=` outputs for development. Production builds use the pinned Nix derivation without a compiler cache. See the [config audit and full-build timer](docs/denali-kernel-config.md).
