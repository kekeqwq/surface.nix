#!/usr/bin/env bash
# Keep the protected Denali endpoint unmuted across FullIO graph reopens.
#
# Every new render graph starts with the reviewed DSP mute proof; only the
# pinned v19c endpoint transaction may unmute it. This keeper watches for
# new GRAPH_PREPARE completions and re-applies that fixed transaction once
# per graph, retrying while the stream settles. It sends no other DSP
# writes and never touches PA or protection state.
set -u
state=${1:?pass fixture state directory}
vol=$(ls -d /nix/store/*-sp11-fullio-v19c-volume-transaction-*/ 2>/dev/null | grep -v '\.drv' | head -1)
amixer=$(ls /nix/store/*-alsa-utils-*/bin/amixer | head -1)
helper=$(ls "$(dirname "$0")"/fullio-reference-volume-once* | head -1)
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}
log="$state/endpoint-keeper.log"
status=/proc/asound/card0/pcm0p/sub0/status
last_trigger=none
echo "$(date -Iseconds) keeper start" >> "$log"
while :; do
    # A new trigger_time means a fresh stream/graph start (sub-second poll).
    trigger=$(awk '/^trigger_time/ {print $2}' "$status" 2>/dev/null)
    if [[ -n $trigger && $trigger != "$last_trigger" ]]; then
        [[ $last_trigger != none ]] && echo "$(date -Iseconds) new stream trigger_time=$trigger" >> "$log"
        last_trigger=$trigger
        sleep 1
        for _ in 1 2 3 4 5 6; do
            if python3 "$helper" --card hw:0 --endpoint-db -3 --mute off \
                --amixer "$amixer" --tlv-write "$vol/libexec/sp11-fullio/tlv_write" \
                --delta-table "$vol/share/sp11-fullio/gainstep-runtime-deltas.json" >> "$log" 2>&1; then
                echo "$(date -Iseconds) endpoint armed for trigger_time=$trigger" >> "$log"
                break
            fi
            sleep 2
        done
    fi
    sleep 1
done
