#!/usr/bin/env bash
# One PA-off ALSA prepare after natural clock-stop; no runtime-PM holds.
set -euo pipefail
s=${1:?pass exact native fixture state}
repo=$s/hardware/tests
sound=/sys/firmware/devicetree/base/sound
swr=/sys/firmware/devicetree/base/soc@0/soundwire@6b10000
[[ $EUID == 0 && -e $swr/qcom,denali-fullio-wait-frame-stop &&
   ! -e $sound/microsoft,denali-fullio-ring-dma-held-audit &&
   ! -e $sound/microsoft,denali-fullio-soft-cycle-audit ]]
bash "$repo/fullio-boot-preflight.sh" "$s" ring-dma-taps
prior=$(journalctl -kb --no-pager -o cat)
[[ $(grep -Fc 'FullIO frame generator stopped before iface gate:' <<< "$prior") == 1 ]]
! grep -Eq 'FullIO PM transition before-cgcr-reset:|FullIO PM transition before-exit-clock-stop:' <<< "$prior"
for d in /sys/bus/platform/devices/{6b00000.codec,6b10000.soundwire} /sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:{0,1}; do
    [[ $(<"$d/power/control") == auto && $(<"$d/power/runtime_status") == suspended ]]
done
boot_id=$(</proc/sys/kernel/random/boot_id)
[[ $boot_id =~ ^[0-9a-f-]{36}$ ]]
mkdir "$s/frame-stop-render-$boot_id"
rc=0
bash "$repo/fullio-ring-map-smoke.sh" "$s" ring-dma-taps || rc=$?
if ((rc)); then
    printf 'PA-off prepare/teardown did not pass (status=%d); no second open.\n' "$rc" >&2
    exit "$rc"
fi
log=$(journalctl -kb --no-pager -o short-monotonic)
awk '
    /FullIO frame generator stopped before iface gate:/ && !pre { idle=NR }
    /FullIO PM transition before-exit-clock-stop: clash=0 frame=1 result=0 slaves=0x00000014/ { ++pre; before=NR }
    /FullIO PM transition after-exit-clock-stop: clash=0 frame=1 result=0 slaves=0x00000014/ { ++post; after=NR }
    /FullIO independent ring SET_CFG acknowledged/ { ++cfg; cfg_at=NR }
    END { exit !(idle && pre == 1 && post == 1 && cfg == 1 && idle < before && before < after && after < cfg_at) }
' <<< "$log"
bash "$repo/fullio-boot-preflight.sh" "$s" ring-dma-taps
printf 'Natural-idle PA-off resume and ring smoke passed; no PCM samples written.\n'
