#!/usr/bin/env bash
# Hold the protected Denali render graph alive for the whole session.
#
# A silent stream keeps the PipeWire sink, the ALSA PCM and the FullIO
# graph open across user playback gaps, so the PA enable transient (the
# audible start crack after long idle) happens once when this holder
# starts and never again on play or video switch. The stream contributes
# exactly zero samples and cannot affect mix level or channel mapping.
#
# The feeder and the player are supervised as two explicit processes
# (a FIFO, not a pipeline: `$!` would otherwise capture the feeder) and
# both are recycled if the PCM fails to reach RUNNING, which covers the
# login race where the sink is not yet ready for linking.
set -u
state=${1:?pass fixture state directory}
pwcat=$(ls /nix/store/*-pipewire-*/bin/pw-cat | head -1)
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
export DBUS_SESSION_BUS_ADDRESS=${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}
mkdir -p "$state"
log="$state/graph-holder.log"
zeros="$state/holder-zeros.raw"
fifo="$state/holder.fifo"
status=/proc/asound/card0/pcm0p/sub0/status
[[ -s $zeros ]] || head -c 1048576 /dev/zero > "$zeros"
[[ -p $fifo ]] || mkfifo "$fifo"
echo "$(date -Iseconds) holder start" >> "$log"
while :; do
    bash -c "while :; do cat '$zeros'; done" > "$fifo" &
    feeder=$!
    "$pwcat" --playback --raw --format s16 --rate 48000 --channels 2 \
             --properties 'node.name=fullio-graph-holder' - \
             < "$fifo" >> "$log" 2>&1 &
    stream=$!
    idle=0
    while kill -0 "$stream" 2>/dev/null && kill -0 "$feeder" 2>/dev/null; do
        sleep 10
        if grep -q 'state: RUNNING' "$status" 2>/dev/null; then
            idle=0
        else
            idle=$((idle + 10))
            if (( idle >= 40 )); then
                echo "$(date -Iseconds) holder PCM idle ${idle}s; recycling" >> "$log"
                break
            fi
        fi
    done
    kill "$stream" "$feeder" 2>/dev/null
    wait "$stream" 2>/dev/null
    wait "$feeder" 2>/dev/null
    echo "$(date -Iseconds) holder stream cycle ended; restarting" >> "$log"
    sleep 2
done
