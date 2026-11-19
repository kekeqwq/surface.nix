# surface.nix

Minimal NixOS support for the non-5G OLED Surface Pro 11 (Denali). No desktop, firmware flashing or disk layout policy is included.

Import `surface.nixosModules.surface-pro-11` and set `surface.devices.denali.enable = true;` to opt in. The module provides the pinned downstream kernel, OLED device tree, early USB drivers and Wi-Fi firmware. For a Type #2 UKI with compressed ARM64 zboot and embedded DTB, import `surface.nixosModules.denali-uki` instead. The host still owns its loader, disks and accounts. See the [independent installation test](https://github.com/kekeqwq/surface.nix.standalone.test.flake).

Nixpkgs tracks `nixos-unstable-small`. Maintainers run `nix flake update nixpkgs` and commit the resulting lock file. The lock records the exact revision used for each build; changing it does not replace an already-built or tested Live USB.

## Validated installed candidates

The independent test host has booted kernel.org `next-20261118` with no local
patches, then a separate `surface-next-touch` candidate with the required
SPI-HID/QSPI patch queue. The latter passed user-confirmed finger touch in Niri;
2880×1920 at 120 Hz and Adreno X1-85 acceleration are retained. The hardware
module's conservative default remains `linux-sp11`; the test flake explicitly
selects `surface.devices.denali.kernel = "surface-next-touch"` and enables iptsd.

Graphics requires privately provisioned Microsoft GPU firmware and the current
`FD_MESA_DEBUG=noubwc,notile` workaround. This is not a claim of a fully
reproducible desktop or complete hardware support. See
[touch bring-up](docs/touch-bringup.md) and the test host's desktop notes.
Internal audio is audible but too quiet; [protection work](docs/audio-protection-audit.md)
is deferred. Pen, detailed multitouch, suspend/resume and external audio still
need separate acceptance.

### Incremental kernel development

`surface.devices.denali.kernel = "surface-next"` selects the experimental kernel.org snapshot without a local patch queue. The default remains `linux-sp11`.

On AArch64 Linux, use the workbench to iterate without discarding Kbuild outputs:

```sh
nix develop .#surface-next -c bash scripts/surface-next-workbench.sh config
nix develop .#surface-next -c bash scripts/surface-next-workbench.sh build
```

The script prints the writable source and persistent `O=` directory. Apply experimental patches to that source tree and rerun `build` without cleaning it. The directory is keyed by the pinned source archive; `ccache` is shared across snapshots. Changed headers, Kconfig, or compilers can still trigger a broad rebuild. Workbench outputs are local diagnostics, not inputs to the release build. Record any accepted patch in Nix and build the final UKI through the standalone flake.

### Live USB

On AArch64 Linux, build the public Live ISO (SSH disabled):

```sh
nix build .#denali-live-iso -L
```

For a private test image with SSH, place **only a public key** in `authorized_keys` in an external directory:

```sh
nix build .#denali-live-iso-local -L --no-write-lock-file \
  --override-input localFiles "path:$HOME/.local/share/denali-live"
```

The result includes `boot-contract.json` and the ISO under `result/iso/`. Raw-write to the test USB only. With Secure Boot disabled, use Surface UEFI **Boot configuration → USB Storage** and swipe left to boot. Use `nmtui` from the Live TTY. The privately keyed variant passed TTY, Wi-Fi and SSH on real hardware; see [the acceptance record](docs/jovian-porting-model.md#live-acceptance-passed).
