#!/usr/bin/env bash
# Enable only software port-selection bits, then use the PREPARE-only audit.
set -euo pipefail
s=${1:?pass exact native build state directory}
repo=$s/hardware
sound=/sys/firmware/devicetree/base/sound
bash "$repo/tests/fullio-boot-preflight.sh" "$s" vphx
[[ -e $sound/microsoft,denali-fullio-sink-bank-audit ]]
log=$(journalctl -kb --no-pager -o cat)
! grep -Eq 'FullIO PA-off (VPHX_STATUS|sink bank)' <<< "$log"
pcm=$(awk '/MultiMedia1 Playback/ && /playback [1-9]/ {print $1}' /proc/asound/pcm)
[[ $pcm =~ ^([0-9]+)-[0-9]+:$ ]]
card=$((10#${BASH_REMATCH[1]}))
am=/nix/store/90kcqvgk6gak7riqymc2sswa9bnmx7p9-alsa-utils-1.2.16/bin/amixer
controls=()
prior=()
changed=0
get() { "$am" -c "$card" cget "name=$1" | awk -F= '/^[[:space:]]*: values=/ {print $2}'; }
for side in Left Right; do
    for port in DAC COMP BOOST; do
        name="Spkr$side $port Switch"
        value=$(get "$name")
        [[ $value == on || $value == off ]]
        controls+=("$name")
        prior+=("$value")
    done
done
cleanup() {
    local rc=$? i
    for ((i=changed-1; i>=0; i--)); do
        if ! "$am" -q -c "$card" cset "name=${controls[i]}" "${prior[i]}" ||
           [[ $(get "${controls[i]}") != "${prior[i]}" ]]; then
            printf 'Failed to restore %s\n' "${controls[i]}" >&2
            rc=1
        fi
    done
    ((rc != 0)) || echo 'All six port switches restored and read back.'
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
cursor=$(journalctl -kb --no-pager -n 0 --show-cursor | awk '/^-- cursor:/ {print $3}')
[[ -n $cursor ]]
for i in "${!controls[@]}"; do
    changed=$((i+1))
    "$am" -q -c "$card" cset "name=${controls[i]}" on
    [[ $(get "${controls[i]}") == on ]]
done
rc=0
bash "$repo/tests/fullio-vphx-smoke.sh" "$s" || rc=$?
log=$(journalctl -kb --no-pager -o short-monotonic --after-cursor "$cursor")
grep -E 'PA-off sink bank|FullIO.*START|SWR bus clsh|MAX_RETRY|Oops:' <<< "$log" || true
((rc == 0))
for amp in 0 1; do
    grep -Eq "sdw:1:0:0217:0204:00:$amp: FullIO PA-off sink bank [01]: enabled DP1 BlockCtrl3=0x00 DP2 Offset2=0x07 DP3 Offset2=0x1f verified" <<< "$log"
done
printf 'Both physical codecs verified their active rendering bank with PAs off.\n'
