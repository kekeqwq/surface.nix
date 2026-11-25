#!/usr/bin/env bash
# Inject a verification failure after muted START. Both PAs stay off.
set -euo pipefail
repo=${1:?pass the hardware source tree}
alsa=${2:?pass the alsa-utils bin directory}
lib=${3:?pass the pinned libasound.so.2}
sound=/sys/firmware/devicetree/base/sound
[[ -e $sound/microsoft,denali-fullio-dsp-stop-fault-audit &&
   -e $sound/microsoft,denali-fullio-dsp-start-audit &&
   -e $sound/microsoft,denali-fullio-clock-off-audit &&
   ! -e $sound/microsoft,denali-fullio-immediate-taps-audit &&
   ! -e $sound/microsoft,denali-fullio-post-pa-test ]]
mark() {
    journalctl -kb --no-pager -n 0 --show-cursor | awk '/^-- cursor:/ {print $3}'
}
evidence() { journalctl -kb --no-pager --after-cursor "$1" -g 'FullIO|ASoC'; }
verify_cleanup() {
    grep -Fq 'FullIO CPS wake registers restored and verified' <<< "$1"
    grep -Fq 'FullIO clock-off audit: TX0-TX3 hardware readback off' <<< "$1"
    ! grep -Eq 'clock-off audit found enabled|clock shutdown/audit failed|CPS probe wake restore failed' <<< "$1"
}
cursor=$(mark); [[ -n $cursor ]]
rc=0
bash "$repo/tests/fullio-mute-smoke.sh" "$alsa" "$lib" fault || rc=$?
log=$(evidence "$cursor"); printf '%s\n' "$log"
((rc == 0))
grep -Fq 'FullIO injected post-START verification failure; PAs and clocks off' <<< "$log"
grep -Fq 'FullIO start audit failed; GRAPH_STOP acknowledged' <<< "$log"
verify_cleanup "$log"
cursor=$(mark); [[ -n $cursor ]]
bash "$repo/tests/fullio-mute-smoke.sh" "$alsa" "$lib" fault-retry || rc=$?
log=$(evidence "$cursor"); printf '%s\n' "$log"
((rc == 0))
! grep -Eq 'post-START verification failure|silent START/STOP audit passed|GRAPH_STOP acknowledged' <<< "$log"
verify_cleanup "$log"
printf 'FullIO synthetic post-START fault stopped by DSP; a second START was rejected. No PA/load fault tested.\n'
