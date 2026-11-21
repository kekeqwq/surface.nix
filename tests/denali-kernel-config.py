#!/usr/bin/env python3
"""Validate the audited Denali Kconfig against an evaluated Surface flake.

This is a regression check, not a pruning heuristic or an lsmod whitelist.
"""
import argparse
import json
from pathlib import Path

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("config", type=Path)
p.add_argument("flake_audit", type=Path)
a = p.parse_args()
values = {}
for line in a.config.read_text().splitlines():
    if line.startswith("CONFIG_") and "=" in line:
        key, value = line.split("=", 1)
        values[key[7:]] = value
features = json.loads(a.flake_audit.read_text())
f = features["features"]
errors = []


def enabled(symbol):
    return values.get(symbol) in ("y", "m")


def require(symbol):
    if not enabled(symbol):
        errors.append(f"required: CONFIG_{symbol}")


def reject(symbol):
    if enabled(symbol):
        errors.append(f"unused feature still enabled: CONFIG_{symbol}")


# Hardware plus infrastructure actually needed by this desktop and diagnosis.
for symbol in """
ARM64 ARCH_QCOM EFI EFI_STUB PCI BLK_DEV_NVME EXT4_FS VFAT_FS
DRM DRM_MSM DRM_MSM_GPU_STATE DRM_MSM_DPU DRM_MSM_DP
DRM_PANEL_SAMSUNG_ATNA33XC20 DRM_SIMPLEDRM DMA_SHARED_BUFFER
ATH12K CFG80211 MAC80211 BT BT_HCIUART BT_HCIUART_QCA
QCOM_QSEECOM QCOM_QSEECOM_UEFISECAPP QCOM_SMEM QCOM_SCM
CLK_X1E80100_GCC CLK_X1E80100_DISPCC CLK_X1E80100_GPUCC CLK_X1E80100_TCSRCC
SC_LPASSCC_8280XP SM_VIDEOCC_8550 QCOM_CLK_RPMH
PINCTRL_X1E80100 PINCTRL_SM8550_LPASS_LPI QCOM_GPI_DMA SPI_QCOM_GENI
TYPEC_MUX_PS883X QCOM_PMIC_GLINK QCOM_Q6V5_PAS QCOM_APR
RPMSG_QCOM_GLINK_SMEM QCOM_PDR_HELPERS
PHY_QCOM_EDP PHY_QCOM_QMP_COMBO PHY_QCOM_QMP_PCIE
PHY_QCOM_EUSB2_REPEATER PHY_SNPS_EUSB2
SND SND_SOC_X1E80100 SND_SOC_QCOM_SDW SND_SOC_HDMI_CODEC
SND_SOC_LPASS_WSA_MACRO SND_SOC_LPASS_VA_MACRO SND_SOC_WSA884X
SND_SOC_QDSP6_APM SND_SOC_QDSP6_PRM
USB_XHCI_HCD USB_XHCI_PCI USB_DWC3 USB_STORAGE USB_UAS SCSI BLK_DEV_SD
HID HIDRAW USB_HID INPUT_EVDEV INPUT_UINPUT SURFACE_AGGREGATOR
PROC_FS SYSFS TMPFS DEVTMPFS CONFIGFS_FS EFIVAR_FS FUSE_FS
CGROUPS NAMESPACES USER_NS IPC_NS PID_NS NET_NS SECCOMP SECCOMP_FILTER
UNIX INET IPV6 PACKET INOTIFY_USER EPOLL BPF_SYSCALL BPF_LSM
NETFILTER NF_CONNTRACK IP_NF_IPTABLES IP6_NF_IPTABLES
SECURITY_LANDLOCK SECURITY_YAMA DEBUG_FS PSTORE
""".split():
    require(symbol)

if features["swapCount"] == 0 and not f["zramSwap.enable"]:
    for symbol in ("ZRAM", "ZSWAP", "HIBERNATION"):
        reject(symbol)
if not any(f[k] for k in (
    "virtualisation.libvirtd.enable", "virtualisation.virtualbox.host.enable",
)) and not f["boot.binfmt.emulatedSystems"]:
    for symbol in ("KVM", "XEN", "VFIO", "VDPA", "VHOST_MENU"):
        reject(symbol)
if not f["security.apparmor.enable"]:
    reject("SECURITY_APPARMOR")
if f["boot.initrd.services.lvm.enable"]:
    require("BLK_DEV_DM")
for fs, symbol in (("ntfs", "NTFS_FS"), ("ext4", "EXT4_FS"), ("vfat", "VFAT_FS")):
    if f["boot.supportedFilesystems"].get(fs):
        require(symbol)
for symbol in """
DRM_AMDGPU DRM_RADEON DRM_NOUVEAU NOVA_CORE DRM_XE DRM_AST
DRM_QXL DRM_VIRTIO_GPU DRM_VKMS DRM_VMWGFX
DRM_MSM_MDP4 DRM_MSM_MDP5 DRM_MSM_DSI DRM_MSM_HDMI
SND_PCI SND_SOC_SOF_TOPLEVEL SOUNDWIRE_INTEL SOUNDWIRE_AMD
SND_SOC_AMD_ACP SND_AMD_ACP_CONFIG PCI_IOV
CRYPTO_DEV_QAT_DH895xCCVF CRYPTO_DEV_QAT_C3XXXVF CRYPTO_DEV_QAT_C62XVF
NETWORK_FILESYSTEMS NVME_FABRICS NVME_TARGET BLK_DEV_MD
BTRFS_FS XFS_FS F2FS_FS JFS_FS GFS2_FS OCFS2_FS
ATM CAN NFC NET_9P CEPH_LIB IP_VS IP_SCTP RDS TIPC
WIREGUARD VXLAN GENEVE VETH BRIDGE NET_DSA BONDING NET_TEAM
CXL_BUS RAPIDIO INFINIBAND FIREWIRE MTD ATA MMC SCSI_UFSHCD
CLK_ELIZA_GCC CLK_GLYMUR_GCC CLK_NORD_GCC CRYPTO_DEV_NITROX
""".split():
    reject(symbol)

if errors:
    raise SystemExit("\n".join(errors))
print("PASS: audited Denali hardware and flake feature constraints")
print(f"Enabled tristates: {sum(v in ('y', 'm') for v in values.values())}; modules: {sum(v == 'm' for v in values.values())}")
