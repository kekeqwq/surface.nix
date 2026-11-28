#!/usr/bin/env bash
# At the private Live console: sudo bash /iso/surface-install/enroll-key.sh
set -euo pipefail
export PATH=/run/current-system/sw/bin:/run/wrappers/bin

fail() { printf '%s\n' "$*" >&2; exit 1; }
[[ $# == 0 && $EUID == 0 && -t 0 && -t 1 && -t 2 ]] || fail 'Run as root on the local Live console.'
disk=/dev/nvme0n1
esp=${disk}p1
part=${disk}p2
[[ $(uname -m) == aarch64 && $(findmnt -n -o FSTYPE /iso) == iso9660 ]] || fail 'Expected the ARM64 Live USB at /iso.'
[[ $(lsblk -dn -o MODEL "$disk" | xargs) == MZ9L41T0HBLB-00BMV-SAMSUNG && $(blockdev --getsz "$disk") == 2000409264 && $(blockdev --getss "$disk") == 512 ]] || fail 'Internal Samsung NVMe does not match.'
[[ -z $(lsblk -n -o MOUNTPOINTS "$disk" | xargs) && ! -e /dev/mapper/cryptroot ]] || fail 'Target disk is in use. Stop and check the mounts.'
if lsblk -nr -o TYPE "$disk" | grep -Ev '^(disk|part)$'; then fail 'Target has an active block mapping.'; fi

printf 'Fresh install: replace the partition table and LUKS on the internal Samsung NVMe.\n'
printf 'Confirm the data is backed up or disposable. Type ERASE /dev/nvme0n1 to continue: '
IFS= read -r answer
[[ $answer == "ERASE $disk" ]] || fail 'Cancelled.'

sfdisk --wipe always --wipe-partitions always "$disk" <<'PARTITIONS'
label: gpt
unit: sectors

start=2048, size=1820672, type=C12A7328-F81F-11D2-BA4B-00A0C93EC93B, name="surface-efi"
start=1822720, size=1998585856, type=CA7D7CCB-63ED-4C53-861C-1742536059CC, name="surface-cryptroot"
PARTITIONS
udevadm settle --timeout=20
[[ $(readlink -f /dev/disk/by-partlabel/surface-efi) == "$esp" && $(readlink -f /dev/disk/by-partlabel/surface-cryptroot) == "$part" ]] || fail 'Unexpected partition links; nothing formatted.'
mkfs.fat -F 32 -n SURFACEEFI "$esp"

printf '\n[1/3] Set a new independent recovery passphrase.\n'
cryptsetup luksFormat --batch-mode --verify-passphrase --type luks2 --cipher aes-xts-plain64 --key-size 512 "$part"
printf '\n[2/3] Insert only the intended YubiKey in the lower USB-C port; touch it when it blinks.\n'
systemd-cryptenroll --fido2-device=auto --fido2-with-client-pin=no --fido2-with-user-presence=yes --fido2-with-user-verification=no "$part"
printf '\n[3/3] Open the new cryptroot.\n'
cryptsetup open "$part" cryptroot
printf '\nReady: new LUKS2, touch-only key enrolled, cryptroot open. Btrfs and NixOS are not installed yet.\n'
