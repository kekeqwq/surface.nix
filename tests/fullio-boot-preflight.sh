#!/usr/bin/env bash
# Read-only gate for the dedicated PA-off integration fixture. Never selects a boot entry.
set -euo pipefail
export LC_ALL=C
s=${1:?pass exact native build state directory}
[[ $(id -u) == 0 && $(hostname -s) == surface && $s == /home/keke/.local/state/fullio-* ]]
[[ -L $s/system && $(<"$s/status") == 0 ]]
[[ $(readlink -f /run/booted-system) == $(readlink -f "$s/system") &&
   $(readlink -f /run/current-system) == $(readlink -f /run/booted-system) &&
   $(uname -r) == *-surface-fullio-muted-test ]]
[[ $(readlink /nix/var/nix/profiles/system) == system-20-link &&
   $(readlink -f /nix/var/nix/profiles/system-20-link) == /nix/store/v9w3nd9lchbr4x3bic25in474dk2iv3s-nixos-system-surface-26.11.20261121.56f282a ]]
boot=$(bootctl status --no-pager 2>/dev/null || true)
entry=$(awk '/^Default Boot Loader Entry:/ {d=1;next} d&&$1=="id:" {print $2;d=0}' <<< "$boot")
[[ $entry == nixos-3aae9950e05724a6f75ac7703476b7b4d3ceb0f8ea5bba8665aace82d3a98a62.conf ]]
for service in sshd greetd; do systemctl is-active --quiet "$service"; done
faults=$(journalctl -kb --no-pager -o cat | awk '/Oops:|BUG:|Kernel panic|Unable to handle kernel|hard LOCKUP|soft lockup|SWR bus clsh detected|Reached MAX_RETRY on port read/')
if [[ -n $faults ]]; then
    printf 'No PCM: unsafe boot diagnostics:\n%s\n' "$faults" >&2
    exit 2
fi
sound=/sys/firmware/devicetree/base/sound
[[ -e $sound/microsoft,denali-fullio-muted-test &&
   ! -e $sound/microsoft,denali-fullio-post-pa-test &&
   ! -e $sound/microsoft,denali-fullio-pa-on-smoke ]] || {
    printf 'No PCM: this preflight requires a PA-off fixture.\n' >&2
    exit 2
}
swr=/sys/firmware/devicetree/base/soc@0/soundwire@6b10000
case ${2:-start-audit} in
    start-audit) [[ -e $sound/microsoft,denali-fullio-clock-off-audit &&
                     -e $sound/microsoft,denali-fullio-dsp-start-audit ]] ;;
    ring-dma|ring-dma-taps) [[ -e $sound/microsoft,denali-fullio-clock-off-audit &&
                  -e $sound/microsoft,denali-fullio-dsp-prepare-audit &&
                  -e $sound/microsoft,denali-fullio-dsp-start-audit &&
                  -e $sound/microsoft,denali-fullio-ring-map-audit &&
                  -e $sound/microsoft,denali-fullio-ring-attach-audit &&
                  -e $sound/microsoft,denali-fullio-ring-dma-audit &&
                  -e $swr/qcom,denali-fullio-link-gate &&
                  -e $swr/qcom,denali-fullio-pm-transition-audit &&
                  ! -e $swr/qcom,denali-fullio-link-gate-test &&
                  ! -e $sound/microsoft,denali-fullio-dsp-stop-fault-audit &&
                  ! -e $sound/microsoft,denali-fullio-pa-off-fault-worker ]]
        if [[ ${2} == ring-dma-taps ]]; then
            [[ -e $sound/microsoft,denali-fullio-immediate-taps-audit && -e $swr/qcom,denali-fullio-sidechain-audit ]]
        else
            [[ ! -e $sound/microsoft,denali-fullio-immediate-taps-audit ]]
        fi
        if [[ -e $sound/microsoft,denali-fullio-ring-dma-held-audit ]]; then
            [[ ${2} == ring-dma-taps ]]
            for supplier in /sys/bus/platform/devices/{6b00000.codec,6b10000.soundwire}; do
                [[ $(<"$supplier/power/control") == on && $(<"$supplier/power/runtime_status") == active ]] || {
                    printf 'No PCM: discovery hold absent on %s\n' "$supplier" >&2
                    exit 2
                }
            done
            if [[ -n $(journalctl -kb --no-pager -o cat | awk '/FullIO PM transition (after-enter-clock-stop|before-exit-clock-stop)/') ]]; then
                printf 'No PCM: clock-stop transition observed on the held control boot.\n' >&2
                exit 2
            fi
        fi ;;
    link-gate) [[ -e $sound/microsoft,denali-fullio-clock-off-audit &&
                   ! -e $sound/microsoft,denali-fullio-dsp-start-audit &&
                   -e $swr/qcom,denali-fullio-link-gate-test ]] ;;
    vphx) [[ -e $sound/microsoft,denali-fullio-clock-off-audit &&
               -e $sound/microsoft,denali-fullio-dsp-prepare-audit &&
               -e $sound/microsoft,denali-fullio-vphx-audit &&
               ! -e $sound/microsoft,denali-fullio-dsp-start-audit ]] ;;
    passive-link) [[ -e $sound/microsoft,denali-fullio-capture-only &&
                      ! -e $sound/microsoft,denali-fullio-dsp-start-audit &&
                      -e $swr/qcom,denali-fullio-pm-transition-audit &&
                      -e $swr/qcom,denali-fullio-link-gate && ! -e $swr/qcom,denali-fullio-link-gate-test ]] ;;
    *) exit 64 ;;
esac
# The seeded link-gate fixture must reach its deliberate denial test.
# On all other fixtures, a sticky link fault is unsafe even after re-enumeration.
if [[ ${2:-start-audit} != link-gate ]]; then
    faults=$(journalctl -kb --no-pager -o cat | awk '/FullIO SoundWire new streams locked: first link error/')
    if [[ -n $faults ]]; then
        printf 'No PCM: previously latched SoundWire fault:\n%s\n' "$faults" >&2
        exit 2
    fi
fi
for codec in /sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:{0,1}; do
    [[ $(readlink -f "$codec/driver") == /sys/bus/soundwire/drivers/wsa884x-codec &&
       $(<"$codec/status") == Attached ]]
done
shopt -s nullglob
pcm=(/proc/asound/card*/pcm*/sub*/status)
[[ ${#pcm[@]} -ge 2 ]]
for status in "${pcm[@]}"; do [[ $(<"$status") == closed ]]; done
# A future wsa884x Speaker Switch can call the PA writer directly, outside
# the PCM gate. Do not run a PA-off experiment with that control exposed.
mapfile -t surface_cards < <(awk '/MultiMedia[13] (Playback|Capture)/ {sub(/-.*/, "", $1); print $1}' /proc/asound/pcm | sort -u)
[[ ${#surface_cards[@]} == 1 && ${surface_cards[0]} =~ ^[0-9]+$ ]]
amixer=/nix/store/90kcqvgk6gak7riqymc2sswa9bnmx7p9-alsa-utils-1.2.16/bin/amixer
controls=$("$amixer" -c "$((10#${surface_cards[0]}))" controls)
if grep -Eq "name='([^']* )?Speaker Switch'" <<< "$controls"; then
    printf 'No PCM: an unreviewed direct Speaker Switch control is exposed.\n' >&2
    exit 2
fi
printf 'PA-off preflight: exact fixture, Gen20 default, healthy SSH/greetd, both WSA attached, no PCM open.\n'
