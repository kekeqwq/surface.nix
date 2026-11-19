# surface.nix

Minimal NixOS support for the non-5G OLED Surface Pro 11 (Denali). No desktop, firmware flashing or disk layout policy is included.

Import `surface.nixosModules.surface-pro-11` and set `surface.devices.denali.enable = true;` to opt in. The module provides the pinned downstream kernel, OLED device tree, early USB drivers and Wi-Fi firmware. For a Type #2 UKI with compressed ARM64 zboot and embedded DTB, import `surface.nixosModules.denali-uki` instead. The host still owns its loader, disks and accounts. See the [independent installation test](https://github.com/kekeqwq/surface.nix.standalone.test.flake).

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
