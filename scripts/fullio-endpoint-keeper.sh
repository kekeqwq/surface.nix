#!/usr/bin/env bash
# Keep the protected Denali endpoint unmuted across FullIO graph reopens.
#
# Every new render graph starts with the reviewed DSP mute proof; only the
# pinned v19c endpoint transaction may unmute it. Wait for a new running
# PCM trigger and apply the fixed transaction once. A failure may mean a
# DSP write took effect without an ACK; stop instead of replaying it.
# This service sends no other DSP writes and never touches PA or protection.
set -u
amixer=${1:?pass the exact amixer path}
vol=${2:?pass the pinned v19c volume data package}
endpoint_db=${3:--3}
case $endpoint_db in
    -3|0) ;;
    *) echo 'Unsupported FullIO endpoint dB' >&2; exit 2 ;;
esac
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
        if [[ $(running_trigger) == "$trigger" ]]; then
            echo "Endpoint arm attempt for trigger_time=$trigger"
            if ! python3 -u "$helper" --card hw:0 --endpoint-db "$endpoint_db" --mute off \
                --amixer "$amixer" --tlv-write "$vol/libexec/sp11-fullio/tlv_write" \
                --delta-table "$vol/share/sp11-fullio/gainstep-runtime-deltas.json"; then
                echo "Endpoint arm failed for trigger_time=$trigger; stopped without retry" >&2
                exit 1
            fi
            if [[ $(running_trigger) != "$trigger" ]]; then
                echo "Endpoint trigger changed during arm for trigger_time=$trigger; stopped without retry" >&2
                exit 1
            fi
            echo "Endpoint armed for trigger_time=$trigger"
        fi
    fi
    sleep 1
done
