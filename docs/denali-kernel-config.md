# Denali linux-next configuration audit

Scope: the evaluated native Surface desktop, formerly the integration test
and now `nixosConfigurations.surface` in the consuming flake. This is not a
configuration for other Linux hosts. `config-denali-next.aarch64` is the one
maintained configuration. There is no vendor-keyword pruning script.

## Evidence and rules

Evaluate enabled services, filesystem types, supported filesystems, kernel and
initrd module lists, system packages and Home Manager packages. Then check the
Denali OLED DT and Kconfig dependencies. Absence of a service alone does not
justify deleting infrastructure needed by other programs. An unloaded module
is not evidence that its device is unnecessary.

The actual Denali DT uses X1E80100 MDSS/DPU/Adreno and Samsung ATNA eDP,
PCIe/NVMe, PCIe WCN7850, Qualcomm UART Bluetooth, Qualcomm SoundWire/WSA884x,
AudioReach/LPASS, Qualcomm PMIC GLINK, Parade PS8830 Type-C retimers and the
Surface EC. Preserve these chains, including touch/pen, USB-C display output,
USB storage and authentication hardware even when currently unloaded.

## Evaluated feature mapping

| Evaluated configuration/use | Kernel decision |
| --- | --- |
| `/` ext4, `/boot` vfat | Keep ext4/JBD2, FAT/VFAT, NVMe, EFI, partition support |
| `boot.supportedFilesystems` includes **ntfs** | Keep NTFS support; no assumption that only mounted filesystems matter |
| No NFS/SMB/network filesystem configuration | Disable network filesystems and unused distributed-storage clients |
| No Btrfs/XFS/F2FS root or configured mount | Disable those filesystem drivers; installing `f2fs-tools` alone does not require mounting F2FS |
| No optical/flash/legacy filesystem deployment | Disable ISO/UDF, raw-flash/legacy filesystem drivers; retain pstore and pseudo filesystems |
| No swap, zram, zswap deployment | Disable swap compression, zram and hibernation; retain suspend |
| No VM, emulation, Docker/Podman, Waydroid or NixOS containers | Disable KVM, Xen, VFIO, vhost/vDPA and virtual GPU drivers |
| Chrome, systemd, desktop portals, Nix sandbox | Retain namespaces, seccomp, cgroups, Unix sockets, event notification and required BPF interfaces despite no containers |
| NetworkManager, Wi-Fi, SSH, firewall; nftables service off | Retain IPv4/IPv6, DHCP/raw sockets, packet sockets, iptables/netfilter and connection tracking; do not delete firewall backend dependencies |
| No bridges, overlay networking, IPVS, WireGuard or tunnel deployment | Disable unused tunnel/bridge/virtual-link drivers and specialized network protocols |
| WCN7850, no native wired Ethernet controller | Keep ath12k, MHI/QRTR and QCA UART Bluetooth; remove unrelated native Ethernet and older WLAN hardware; USB networking remains separate |
| Niri/Ghostty/Waybar/Plymouth | Keep MSM/DPU/Adreno, dma-buf, DRM/KMS, DP AUX, native panel and early display; remove unrelated discrete/virtual GPUs |
| PipeWire, native sound and USB/DP audio | Preserve Qualcomm card, SoundWire, WSA884x, LPASS/APM dependencies and USB/HDMI audio; remove unrelated PCI/SOF sound platforms |
| Xremap, iptsd, Surface EC, YubiKey and pcscd/GnuPG | Keep uinput, evdev, HID/HIDRAW, SPI-HID, USB HID/CCID and required transports |
| fwupd and UDisks2 enabled | Keep firmware update, EFI variables and block-device/USB infrastructure |
| AppArmor/audit services disabled; runtime LSM list is landlock,yama,bpf | Remove unused alternative policy engines; retain actual LSMs and authentication/security plumbing |
| Initrd LVM enabled by default, `dm_mod` explicitly requested | **Do not remove device mapper just because the root mount is ext4**; review NixOS initrd defaults before changing this |
| GPU fault investigation | Keep debugfs, GPU state, CRC support, logging and recovery diagnostics; do not treat them as unused debug code |

## Current status

The flake evaluation and the first direct Kconfig edits are done. The previous
keyword-generated candidate was discarded and restarted from the original
seed. The first dependency normalization against next-20261119 and the hardware/flake
constraint tests passed. Module-valued symbols decreased from 6684 to 4858;
this is not a count of modules loaded at runtime. Subsequent selector checks
reduced this to 4858, with all explicit disabled options staying disabled.
The first pruning pass is frozen at next-20261119, the tested graphics
baseline. Remaining leaf-driver pruning is not represented as complete.

The dependency review caught selectors that would undo a naive parent switch:
NVMe/TCP and NVMe/FC re-enabled NVME_FABRICS; DM_RAID re-enabled software MD;
QAT VF crypto drivers re-enabled PCI_IOV; NitroX's device driver re-enabled its
core. The actual selectors were disabled, then olddefconfig and the constraints
were rerun. None of the explicitly disabled seed options were re-enabled.

Device-tree/driver matching also confirmed that X1E80100 requires
`SC_LPASSCC_8280XP` and `SM_VIDEOCC_8550`. They are not unrelated drivers just
because their Kconfig names mention other SoCs. Conversely, Qualcomm QAIC
cloud accelerators and other platforms' clock controllers are not Denali
hardware. This is why vendor-keyword removal is not an acceptable method.

Regression check:

```
python3 tests/denali-kernel-config.py pkgs/config-denali-next.aarch64 evaluated-flake-audit.json
```

Before compiling, run `olddefconfig` against next-20261119 plus the touch queue,
check all explicitly requested initrd modules and the retained hardware chains,
and ensure Kconfig has not re-enabled an unwanted backend. The development
workbench retains Kbuild outputs and a compiler cache.
