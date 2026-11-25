#!/usr/bin/env bash
# Test one isolated map/unmap, or attach the backing to a never-started graph.
set -euo pipefail
s=${1:?pass exact build state directory}
repo=$s/hardware
sound=/sys/firmware/devicetree/base/sound
mode=vphx
[[ ! -e $sound/microsoft,denali-fullio-ring-dma-audit ]] || mode=ring-dma
if [[ ${2:-} == ring-dma-taps ]]; then
    [[ $mode == ring-dma ]]
    mode=ring-dma-taps
else
    [[ $# == 1 ]]
fi
bash "$repo/tests/fullio-boot-preflight.sh" "$s" "$mode"
swr=/sys/firmware/devicetree/base/soc@0/soundwire@6b10000
[[ -e $sound/microsoft,denali-fullio-ring-map-audit ]]
sink_readback=false
if [[ -e $sound/microsoft,denali-fullio-sink-readback-audit ]]; then
    [[ $mode == vphx && -e $sound/microsoft,denali-fullio-ring-attach-audit ]]
    sink_readback=true
    for d in /sys/bus/platform/devices/{6b00000.codec,6b10000.soundwire}; do
        [[ $(<"$d/power/control") == on && $(<"$d/power/runtime_status") == active ]]
    done
    log=$(journalctl -kb --no-pager -o cat)
    if grep -Eq 'after-enter-clock-stop|before-exit-clock-stop' <<< "$log"; then
        echo 'Sink readback requires discovery hold without clock-stop/resume' >&2
        exit 1
    fi
fi
prior=$(journalctl -kb --no-pager -o cat)
if ! grep -Fq 'FullIO independent PCM: no legacy DSP map' <<< "$prior"; then
    echo 'No proof that the legacy DSP mapping was skipped; not opening PCM.' >&2
    exit 2
fi
if grep -Eq 'FullIO isolated PCM|FullIO independent ring|FullIO attached ring|FullIO PCM ring quarantined|snd_soc_pcm_component_prepare\(' <<< "$prior"; then
    echo 'Ring map fixture may have run already; not retrying.' >&2
    exit 2
fi
cursor=$(journalctl -kb --no-pager -n 0 --show-cursor | awk '/^-- cursor:/ {print $3}')
[[ -n $cursor ]]
al=/nix/store/90kcqvgk6gak7riqymc2sswa9bnmx7p9-alsa-utils-1.2.16/bin
lib=/nix/store/hs142rv75ssn0g6di4ivp94ii7kgywdp-alsa-lib-1.2.16.1/lib/libasound.so.2
rc=0
runuser -u keke -- bash "$repo/tests/fullio-mute-smoke.sh" "$al" "$lib" || rc=$?
log=$(journalctl -kb --no-pager -o short-monotonic --after-cursor "$cursor")
printf '%s\n' "$log"
((rc == 0))
if [[ -e $sound/microsoft,denali-fullio-ring-attach-audit ]]; then
    awk '
        /FullIO independent ring SET_CFG acknowledged; no START/ { ++cfg; cfg_at=NR }
        /FullIO GRAPH_CLOSE acknowledged/ { ++closed; close_at=NR }
        /FullIO independent ring released after CLOSE and both UNMAP ACKs/ { ++drop; drop_at=NR }
        END { exit !(cfg == 1 && closed == 1 && drop == 1 && cfg_at < close_at && close_at < drop_at) }
    ' <<< "$log"
    if grep -Fq 'never supplied to graph' <<< "$log"; then
        echo 'Isolated ring result contradicts an attached ring audit' >&2
        exit 1
    fi
else
    [[ $(grep -Fc 'FullIO isolated PCM data and position MAP/UNMAP acknowledged; never supplied to graph' <<< "$log") == 1 ]]
fi
[[ $(grep -Fc 'FullIO GRAPH_CLOSE acknowledged' <<< "$log") == 1 ]]
if grep -Eq 'FullIO GRAPH_CLOSE unverified|FullIO start audit failed|FullIO audit GRAPH_STOP unverified|FullIO PCM ring quarantined|Oops:|SWR bus clsh' <<< "$log"; then
    echo 'Unexpected ring teardown or link fault' >&2
    exit 1
fi
if [[ $mode == ring-dma* ]]; then
    soft_cycle=0
    if [[ -e $sound/microsoft,denali-fullio-soft-cycle-audit ]]; then
        [[ $mode == ring-dma-taps && -e $sound/microsoft,denali-fullio-ring-dma-held-audit ]]
        soft_cycle=1
    fi
    awk -v soft_cycle="$soft_cycle" '
        /FullIO independent ring SET_CFG acknowledged; no START/ { cfg_at=NR }
        /FullIO independent ring pull watermarks and SOFT_PAUSE events acknowledged/ { ++wm; wm_at=NR }
        /FullIO independent ring SHMEM media accepted/ { ++media; media_at=NR }
        /FullIO SP\/SPVI tags survived/ { ++tags; tags_at=NR }
        /FullIO independent ring: DSP byte cursor advanced: seq=/ { if (!dma++) dma_first=NR; dma_at=NR }
        /FullIO soft-pause command and completion verified/ { ++paused; pause_at=NR }
        /FullIO soft-resume command and completion verified/ { ++resumed; resume_at=NR }
        /FullIO independent ring GRAPH_STOP acknowledged/ { ++stop; stop_at=NR }
        /FullIO GRAPH_CLOSE acknowledged/ { close_at=NR }
        END { exit !(wm == 1 && media == 1 && tags == 1 && dma == 1+soft_cycle && stop == 1 &&
                     cfg_at && cfg_at < wm_at && wm_at < media_at && media_at < tags_at &&
                     tags_at < dma_first && dma_at < stop_at && stop_at < close_at &&
                     paused == soft_cycle && resumed == soft_cycle &&
                     (!soft_cycle || (dma_first < pause_at && pause_at < resume_at && resume_at < dma_at))) }
    ' <<< "$log"
    if [[ $mode == ring-dma-taps ]]; then
        [[ $(grep -Fc 'FullIO immediate VI/CPS taps configured' <<< "$log") == 1 ]]
        grep -Eq 'FullIO tap host window: start_ack_ns=[1-9][0-9]* stop_begin_ns=[1-9][0-9]* verify=0 stop=0' <<< "$log"
        if [[ -e $sound/microsoft,denali-fullio-rx0-tag-audit ]]; then
            rx_code=0x1586
            if [[ -e $sound/microsoft,denali-fullio-rx0-log-off-audit ]]; then rx_code=0x0; fi
            feedback_code=0x1586
            if [[ -e $sound/microsoft,denali-fullio-feedback-log-off-audit ]]; then feedback_code=0x0; fi
            cps_code=$feedback_code
            if [[ -e $sound/microsoft,denali-fullio-keep-cps-log-audit ]]; then cps_code=0x1586; fi
            awk -v rx_code="$rx_code" -v fb_code="$feedback_code" -v cps_code="$cps_code" '
                /FullIO immediate VI\/CPS taps configured/ { config=NR }
                index($0, "FullIO pre-START logger 0x4003 GET_CFG verified: code=" rx_code " tap=4 mode=1") { seen[++n]="pre-rx"; at[n]=NR }
                index($0, "FullIO pre-START logger 0x4025 GET_CFG verified: code=" fb_code " tap=2 mode=1") { seen[++n]="pre-vi"; at[n]=NR }
                index($0, "FullIO pre-START logger 0x402a GET_CFG verified: code=" cps_code " tap=3 mode=1") { seen[++n]="pre-cps"; at[n]=NR }
                index($0, "FullIO post-START logger 0x4003 GET_CFG verified: code=" rx_code " tap=4 mode=1") { seen[++n]="post-rx"; at[n]=NR }
                index($0, "FullIO post-START logger 0x4025 GET_CFG verified: code=" fb_code " tap=2 mode=1") { seen[++n]="post-vi"; at[n]=NR }
                index($0, "FullIO post-START logger 0x402a GET_CFG verified: code=" cps_code " tap=3 mode=1") { seen[++n]="post-cps"; at[n]=NR }
                /FullIO independent ring: DSP byte cursor advanced/ { progress=NR }
                /FullIO independent ring GRAPH_STOP acknowledged/ { stop=NR }
                END { exit !(config && n == 6 && seen[1] == "pre-rx" && seen[2] == "pre-vi" &&
                      seen[3] == "pre-cps" && seen[4] == "post-rx" && seen[5] == "post-vi" &&
                      seen[6] == "post-cps" && config < at[1] && at[3] < progress &&
                      progress < at[4] && at[6] < stop) }
            ' <<< "$log"
        fi
    fi
    if [[ -e $swr/qcom,denali-fullio-sidechain-audit ]]; then
        awk '
            /FullIO DP(10|11|13) bank [01] active Offset2=0 verified/ && !dma { seen[$0 ~ /DP10/ ? 10 : ($0 ~ /DP11/ ? 11 : 13)] = 1 }
            /FullIO independent ring: DSP byte cursor advanced: seq=/ { dma = NR }
            /FullIO independent ring GRAPH_STOP acknowledged/ { stop = NR }
            /FullIO CPS wake registers restored and verified/ { restore = NR }
            END { exit !(seen[10] && seen[11] && seen[13] && dma && dma < stop && stop < restore) }
        ' <<< "$log"
    fi
elif $sink_readback; then
    awk '
        /FullIO independent ring SET_CFG acknowledged; no START/ { cfg = NR }
        /FullIO Golden RX0 endpoint read back after GRAPH_PREPARE/ { ++reads; proof = NR }
        /FullIO GRAPH_CLOSE acknowledged/ { closed = NR }
        END { exit !(cfg && reads == 1 && cfg < proof && proof < closed) }
    ' <<< "$log"
    if grep -Eq 'GRAPH_START|FullIO start audit|before-exit-clock-stop|after-enter-clock-stop' <<< "$log"; then
        echo 'Sink readback unexpectedly crossed START or clock-stop/resume' >&2
        exit 1
    fi
else
    ! grep -Eq 'FullIO PCM_CNV|FullIO mute survived|GRAPH_START|FullIO start audit' <<< "$log"
fi
bash "$repo/tests/fullio-boot-preflight.sh" "$s" "$mode"
