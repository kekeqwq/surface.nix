#!/usr/bin/env bash
# Arm the verified FullIO reference-render fixture exactly once, then reboot.
# Gen20 default entry, profile and archive bytes must be unchanged first.
set -euo pipefail
export LC_ALL=C
umask 077
s=$1
candidate=${2:?pass verified candidate closure}
uki_sha=${3:?pass verified private UKI hash}
u=$s/fullio-reference.efi
base=/nix/store/v9w3nd9lchbr4x3bic25in474dk2iv3s-nixos-system-surface-26.11.20261121.56f282a
id=surface-fullio-reference-render-once.conf
rel=/EFI/surface/surface-fullio-reference-render-once.efi
entry=/boot/loader/entries/$id
image=/boot$rel
default=nixos-3aae9950e05724a6f75ac7703476b7b4d3ceb0f8ea5bba8665aace82d3a98a62.conf
[[ $EUID == 0 && $(hostname -s) == surface ]]
[[ $(readlink -f /run/booted-system) == "$base" && $(readlink -f /run/current-system) == "$base" \
   && $(readlink -e /nix/var/nix/profiles/system-20-link) == "$base" \
   && $(readlink /nix/var/nix/profiles/system) == system-20-link ]]
[[ $(readlink -e "$s/system") == "$candidate" && $(<"$s/status") == 0 && $(stat -c '%a' "$u") == 600 ]]
[[ $(findmnt -n -o FSTYPE --mountpoint /boot) == vfat ]]
for service in sshd greetd; do systemctl is-active --quiet "$service"; done
shopt -s nullglob
for f in /proc/asound/card*/pcm*/sub*/status; do [[ $(<"$f") == closed ]]; done
for d in /sys/bus/platform/devices/{6b00000.codec,6b10000.soundwire}; do
    [[ $(<"$d/power/control") == auto && $(<"$d/power/runtime_status") == suspended ]]
done
for d in /sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:{0,1}; do
    state=$(<"$d/status")
    # Gen20's kernel carries the documented WSA reset-probe regression, so
    # the running baseline may show a clean failed-probe idle state. The
    # candidate boot binds and verifies both amplifiers itself. Accept
    # only Attached or that idle state; anything else is unsafe.
    [[ $state == Attached || $state == UNATTACHED ]] || {
        echo "unsafe SoundWire state on $d: $state" >&2
        exit 1
    }
done
log=$(journalctl -kb --no-pager -o cat)
if grep -Eq 'Oops:|BUG:|Kernel panic|Unable to handle kernel|hard LOCKUP|soft lockup|FullIO SoundWire new streams locked' <<< "$log"; then
    echo 'Unsafe running kernel state: refusing to arm' >&2
    exit 1
fi
# Gen20 carries the documented WSA reset-probe regression: each failed amp
# probe raises one bus clash and leaves its device UNATTACHED. Accept only
# clashes fully accounted for by those failed probes; anything more is a
# real bus fault and blocks the arm.
if grep -q 'SWR bus clsh' <<< "$log"; then
    clashes=$(grep -c 'SWR bus clsh' <<< "$log")
    reset_probes=$(grep -c 'wsa884x-codec: Failed to get reset' <<< "$log")
    if (( reset_probes < 2 || clashes > reset_probes )); then
        echo "Unexpected SoundWire clash activity ($clashes clashes, $reset_probes failed probes): refusing to arm" >&2
        exit 1
    fi
fi
# The running Gen20 description is not the fixture; verify the CANDIDATE DT
# markers from its staged UKI instead (done by prepare-fullio-uki). Here only
# reject an obviously unsafe running state.
[[ ! -e /sys/firmware/devicetree/base/sound/microsoft,denali-fullio-post-pa-test ]]
boot=$(bootctl status --no-pager 2>/dev/null || true)
[[ $(awk '/^Default Boot Loader Entry:/ {d=1;next} d&&$1=="id:" {print $2;d=0}' <<< "$boot") == "$default" ]]
grep -Fxq 'efi /EFI/surface/generation-0df77b46b7e2b4e3486e66812bed5f2bd1c00e5a9440392584b0ac95e5f27d41.efi' "/boot/loader/entries/$default"
[[ -s /boot/EFI/surface/generation-0df77b46b7e2b4e3486e66812bed5f2bd1c00e5a9440392584b0ac95e5f27d41.efi && ! -e $entry && ! -e $image ]]
backup=/var/lib/surface-recovery/esp-before-open-test-prune-IH7MS7/esp.tar
baseline_file=$(awk '$1 == "efi" { print "." $2 }' "/boot/loader/entries/$default")
tar -xOf "$backup" "$baseline_file" | cmp -s - "/boot/${baseline_file#./}"
[[ $(sha256sum "$u" | awk '{print $1}') == "$uki_sha" ]]
oneshot=(/sys/firmware/efi/efivars/LoaderEntryOneShot-*)
((${#oneshot[@]} == 0))
available=$(df -B1 --output=avail /boot | tail -1)
(( available >= $(stat -c %s "$u") + 16 * 1024 * 1024 )) || { echo 'Insufficient ESP space with reserve' >&2; exit 1; }
stage=$(mktemp /boot/EFI/surface/.fullio-reference-XXXXXX)
conf=$(mktemp /boot/loader/entries/.fullio-reference-XXXXXX)
keep=0
cleanup() {
    rm -f -- "${stage:-}" "${conf:-}"
    if (( ! keep )); then rm -f -- "$entry" "$image"; fi
}
trap cleanup EXIT
install -m 600 -- "$u" "$stage"
cmp -s "$u" "$stage"
printf 'title Surface FullIO protected reference render (one-shot)\nsort-key zz-surface-fullio-test\nefi %s\n' "$rel" > "$conf"
mv -- "$stage" "$image"
mv -- "$conf" "$entry"
sync -f /boot
cmp -s "$u" "$image"
bootctl set-oneshot "$id"
keep=1
printf 'Protected reference render fixture selected exactly once. Gen20 default and profile verified unchanged.\n'
if ! systemctl reboot; then
    bootctl set-oneshot ''
    keep=0
    exit 1
fi
