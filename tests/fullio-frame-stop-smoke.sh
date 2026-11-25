#!/usr/bin/env bash
# Inspect the first naturally occurring idle transition. Do not wake SoundWire or open PCM.
set -euo pipefail
s=${1:?pass exact native build state directory}
repo=$s/hardware
swr=/sys/firmware/devicetree/base/soc@0/soundwire@6b10000
[[ -e $swr/qcom,denali-fullio-wait-frame-stop ]]
bash "$repo/tests/fullio-boot-preflight.sh" "$s" passive-link
log=$(journalctl -kb --no-pager -o short-monotonic)
printf '%s\n' "$log" | grep -E 'FullIO PM transition|FullIO frame generator stopped|FullIO frame stop unverified'
if grep -Eq 'before-cgcr-reset|before-exit-clock-stop|frame stop unverified|FullIO independent ring|SWR bus clsh' <<< "$log"; then
    echo 'Not a healthy first idle transition; no PCM opened.' >&2
    exit 1
fi
awk '
    /FullIO PM transition after-enter-clock-stop: .*result=0 slaves=0x00000014/ { ++ack; at=NR }
    /FullIO frame generator stopped before iface gate: reads=[1-9][0-9]* status=/ { ++proof; verified=NR }
    END { exit !(ack == 1 && proof == 1 && at < verified) }
' <<< "$log"
for d in /sys/bus/platform/devices/{6b10000.soundwire,6b00000.codec} \
         /sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:{0,1}; do
    control=$(<"$d/power/control")
    status=$(<"$d/power/runtime_status")
    printf '%s control=%s runtime=%s\n' "${d##*/}" "$control" "$status"
    [[ $control == auto && $status == suspended ]]
done
bash "$repo/tests/fullio-boot-preflight.sh" "$s" passive-link
