# Denali OLED kernel configuration audit

`pkgs/config-denali-next.aarch64` targets the **native Surface test desktop** in
`nixosConfigurations.surface`. It is not a general arm64 distro configuration.
The benchmark is a full compile on the Surface, not an incremental Kbuild run.

## Scope and retained dependencies

The review used the evaluated host (including initrd requests, filesystem and
service options), the enabled nodes in the Denali OLED DT, and Kconfig/module
dependencies. The previous running module list can confirm device bindings but
is not a keep list. The resolved config **after the touch patch queue** is what
counts; an `olddefconfig` run on unpatched upstream loses `SPI_HID_OF`.

| Feature | Kernel choice |
| --- | --- |
| ARM64 zboot UKI, NVMe, ext4 root, VFAT ESP | Retain EFI, partitions and native storage, and a strict initrd module closure. Generic initrd suggestions are disabled for Denali, not missing-module checks. |
| Niri, early Plymouth, GPU tests | Keep MSM/DPU/Adreno, eDP, Samsung ATNA panel, DP PHY, simpledrm, console and debugfs/CRC. Remove unrelated DRM controllers and panels. |
| Denali dependencies | Keep RPMh, SCM, SMMU, GLINK, GPI, PHY, TLMM, QFPROM, SDAM, PMIC power key/RTC, thermal/ADC paths. `SC_LPASSCC_8280XP` and `SM_VIDEOCC_8550` are required by the DT despite their names. |
| Touch, keyboard, YubiKey | Keep SPI HID/QSPI, serdev, input/uinput, Surface SAM and ACPI (required by the SAM Kconfig), and USB HID. |
| Wi-Fi, Bluetooth, USB-C | Keep ath12k/WCN7850, UART/QCA Bluetooth, r8152 and common USB Ethernet, DWC3/xHCI, UCSI/GLINK, Type-C mux and DP altmode. |
| Audio and media | Keep native LPASS/SoundWire/WSA884x, USB and DP audio, Iris video engine and USB UVC; remove unrelated card, codec and capture drivers. Retaining a driver is not proof of working firmware or hardware. |
| Desktop and firewall | Keep namespaces, BPF LSM and its tracing dependencies, seccomp, cgroups, iptables/netfilter, multicast and filesystem notification. No VM or specialized networking drivers required. |
| Build speed | Remove DWARF and module/kernel BTF, plus unrelated drivers and optional tracing/test features. Keep debugfs, pstore, kallsyms and embedded config. This build lacks BTF-based debugging. |

Known regression in the pruned `next-20261120` config: both Denali WSA884x
codecs use LPASS GPIO 12 as a shared reset. Removing `GPIO_SHARED_PROXY=m`
left the GPIO proxy devices unbound, with `reset_gpio` and both codecs deferred.
The ALSA card was absent and PipeWire only exposed `Dummy Output`. The
standalone restore-and-rebuild trial was cancelled before validation in favor of
evaluating FullIO v19c. If returning to this kernel path, retain both
`RESET_GPIO` and `GPIO_SHARED_PROXY`.

The test host uses ext4/VFAT only. It no longer requests the default NTFS or
initrd LVM integrations. Btrfs and disk unlock are **not** deployed or covered
by this test. Review Kconfig and initrd dependencies again before adopting
LUKS2, Btrfs/zstd, and a separately enrolled security key in the formal
installation. No existing partition is converted.

## Build and checks

On the Surface use the proxy for both Nix client and daemon. Preload sources
and build dependencies, but not the kernel outputs. Run from the audited
main flake, pointing at the hardware checkout if not yet published:

```sh
bash ~/Repos/surface.nix/scripts/time-full-build.sh ~/Repos/flakes ~/surface-build-timing/new
```

The script rejects existing kernel outputs, disables kernel substitutes and
remote builders, and measures kernel plus desktop closure/boundary check time.
The acceptance threshold is under **600 seconds** with a prepared dependency
store; this is hardware-specific, not a promise for a cold Nix store. Then run
`tests/denali-kernel-config.py` against the built kernel's resolved `.config`
and an evaluated feature audit, and boot a one-shot UKI to check the real
screen, GPU, input, networking, and firmware. Build time alone is not boot or
hardware acceptance.

On the 12-core Surface with prepared dependencies and no compiler cache,
`next-20261120` completed the full kernel build in **514 s** and the system
closure and boundary check in **32 s** (total **546 s**). The built Kconfig
has **1,740** module-valued symbols versus **4,860** in the previous seed.
The resulting private UKI passed offline assembly and section verification;
physical boot validation is a separate step.
