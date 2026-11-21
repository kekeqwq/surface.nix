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

Set `nixpkgs.hostPlatform` to `aarch64-linux`. Follow the consuming flake's `nixpkgs` input. The default and only kernel is kernel.org `next-20261120` with the audited Denali Kconfig and isolated SPI-HID/QSPI touch queue. The module supplies the OLED DTB, native device firmware, touch, and ARM64 zboot UKIs. The host owns its partitions, accounts, and desktop. `surface.devices.denali.niriOutputs` is an optional value to pass into an existing Niri configuration, not a compositor installation.

## Private firmware

Before building a boot entry, provision the owner-held firmware on the **root filesystem** in a root-managed directory, not in the flake, Nix store, or a public cache. Populate the applicable paths under the configured directory:

```text
qcom/x1e80100/microsoft/qcdxkmsuc8380.mbn
qcom/x1e80100/microsoft/Denali/adsp_dtb.mbn
qcom/x1e80100/microsoft/Denali/qcadsp8380.mbn
```

The Microsoft GPU zap file is required with this option; the two matching ADSP files enable native audio. They can be extracted offline from the [official Surface Pro 11 Snapdragon driver MSI](https://www.microsoft.com/en-us/download/details.aspx?id=106119), without installing Windows or running the installer. Windows names its ADSP DT file `adsp_dtbs.elf`. Keep the two ADSP files from the same driver package. The tested installation retained its previously extracted WOA zap; Microsoft's `31.0.137.0` zap was extracted and checked structurally, not hardware-accepted in that test. See [graphics validation](docs/gpu-rendering-investigation.md).

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

## Validation and development

The native installation passed 2880×1920 at 120 Hz, finger touch, and Adreno UBWC scanning with no tiling/compression workaround. The early firmware fix and direct scanout evidence are recorded in the [validation notes](docs/gpu-rendering-investigation.md). Pen, suspend, Bluetooth persistence, and full audio acceptance are separate work. No repartitioning, firmware flashing, or speaker gain changes are performed here.

The persistent local Kbuild workbench is for development, not deployment:

```sh
nix develop .#surface-next -c bash scripts/surface-next-workbench.sh build
```

This retains writable source and Kbuild `O=` outputs for development. Production builds use the pinned Nix derivation without a compiler cache. See the [config audit and full-build timer](docs/denali-kernel-config.md).
