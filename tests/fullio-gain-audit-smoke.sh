#!/usr/bin/env bash
# Observe the real DRE register settings during a PA-off, zero-ring audit.
# This does not certify gain or protection with the PA active.
set -euo pipefail
repo=${1:?pass the hardware source tree}
alsa=${2:?pass the alsa-utils bin directory}
lib=${3:?pass the pinned libasound.so.2}
sound=/sys/firmware/devicetree/base/sound
[[ -e $sound/microsoft,denali-fullio-pa-off-gain-audit &&
   -e $sound/microsoft,denali-fullio-clock-off-audit &&
   -e $sound/microsoft,denali-fullio-dsp-start-audit &&
   ! -e $sound/microsoft,denali-fullio-post-pa-test ]]
cursor=$(journalctl -kb --no-pager -n 0 --show-cursor | awk '/^-- cursor:/ {print $3}')
[[ -n $cursor ]]
rc=0
mode=normal
if [[ -e $sound/microsoft,denali-fullio-pa-off-missing-stop-proof ]]; then
    mode=missing-proof
elif [[ -e $sound/microsoft,denali-fullio-pa-off-fault-worker ]]; then
    mode=worker-fault
fi
bash "$repo/tests/fullio-mute-smoke.sh" "$alsa" "$lib" "$mode" || rc=$?
log=$(journalctl -kb --no-pager -o short-monotonic --after-cursor "$cursor" -g 'FullIO|ASoC')
printf '%s\n' "$log"
((rc == 0))
if [[ $mode == missing-proof ]]; then
    [[ $(grep -Fc 'FullIO injected missing PA-off proof after both hardware checks' <<< "$log") == 2 ]]
    grep -Fq 'FullIO start audit failed; GRAPH_STOP acknowledged' <<< "$log"
    grep -Fq 'FullIO paired PA shutdown unverified: PA=-61, graph audit=-61; render locked' <<< "$log"
    ! grep -Eq 'synthetic fault notice: paired PA-off worker verified|silent START/STOP audit passed' <<< "$log"
    printf 'Missing proof remained a hard render failure despite the DSP STOP acknowledgement.\n'
elif [[ $mode == worker-fault ]]; then
    awk '
        /FullIO PA-off teardown verified/ {
            if ($0 ~ /0204:00:0:/) left=1
            if ($0 ~ /0204:00:1:/) right=1
        }
        /FullIO synthetic fault notice: paired PA-off worker verified before DSP STOP/ { if (left && right) worker=1 }
        /FullIO start audit failed; GRAPH_STOP acknowledged/ { if (worker) stop=1 }
        END { exit !stop }
    ' <<< "$log"
    printf 'Synthetic fault notice reached paired PA-off work before token-matched DSP STOP.\n'
else
    grep -Fq 'FullIO silent START/STOP audit passed; no PA enable or PCM writes' <<< "$log"
fi
grep -Fq 'FullIO CPS wake registers restored and verified' <<< "$log"
! grep -Eq 'clock-off audit found enabled|clock shutdown/audit failed|CPS probe wake restore failed|PA shutdown not fully verified|PA-off teardown failed:' <<< "$log"
for amp in 0 1; do
    grep -Eq "sdw:1:0:0217:0204:00:$amp: FullIO PA-off gain snapshot: DRE0=" <<< "$log"
done
printf 'Both WSA PA-off gain snapshots recorded; active analogue gain remains unverified.\n'
grep -Eq 'FullIO pre-START master gain verified: 0x[0-9a-f]+ \(Q13 unity=0x2000\)' <<< "$log"
grep -Eq 'FullIO post-START master gain verified: 0x[0-9a-f]+ \(Q13 unity=0x2000\)' <<< "$log"
printf 'DSP master gain readback within Q13 unity bound before and after START.\n'
if [[ -e $sound/microsoft,denali-fullio-pa-stop-audit ]]; then
    for amp in 0 1; do
        grep -Fq "sdw:1:0:0217:0204:00:$amp: FullIO PA-off teardown verified; clock audit and PA readback passed" <<< "$log"
    done
    if [[ $mode == missing-proof ]]; then
        printf 'Both real PA-off readbacks present; the fixture deliberately withheld their proof.\n'
    else
        printf 'Both verified PA teardowns executed while the playback transport was still owned; no PA-on fault tested.\n'
    fi
fi
