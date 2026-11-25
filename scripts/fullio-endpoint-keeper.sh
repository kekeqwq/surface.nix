#!/usr/bin/env bash
# Keep the protected Denali endpoint unmuted across FullIO graph reopens.
#
# Every new render graph starts with the reviewed DSP mute proof; only the
# pinned v19c endpoint transaction may unmute it. This keeper watches for
# new GRAPH_PREPARE completions and re-applies that fixed transaction once
# per graph, retrying while the stream settles. It sends no other DSP
# writes and never touches PA or protection state.
set -u
amixer=${1:?pass the exact amixer path}
vol=${2:?pass the pinned v19c volume data package}
helper=${0%/*}/fullio-reference-volume-once
status=/proc/asound/card0/pcm0p/sub0/status
last_trigger=
running_trigger() {
    awk '/^state:/ {running = ($2 == "RUNNING")}
         /^trigger_time:/ {trigger = $2}
         END {if (running && trigger + 0 > 0) print trigger}' "$status" 2>/dev/null
}
while :; do
    # PREPARE can expose trigger_time=0 before the paired PA START.
    trigger=$(running_trigger)
    if [[ -n $trigger && $trigger != "$last_trigger" ]]; then
        last_trigger=$trigger
        sleep 1
        for _ in 1 2 3 4 5 6; do
            [[ $(running_trigger) == "$trigger" ]] || break
            if python3 "$helper" --card hw:0 --endpoint-db -3 --mute off \
                --amixer "$amixer" --tlv-write "$vol/libexec/sp11-fullio/tlv_write" \
                --delta-table "$vol/share/sp11-fullio/gainstep-runtime-deltas.json"; then
                echo "Endpoint armed for trigger_time=$trigger"
                break
            fi
            sleep 2
        done
    fi
    sleep 1
done
