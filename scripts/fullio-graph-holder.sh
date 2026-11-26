#!/usr/bin/env bash
# Hold the protected Denali render graph alive for the whole session.
#
# A silent stream keeps the PipeWire sink, the ALSA PCM and the FullIO
# graph open across ordinary playback gaps, avoiding unnecessary PA
# starts when the same PCM epoch survives. This is not a fix for a startup
# transient or a guarantee against graph retirement. The stream itself
# contributes exactly zero samples.
#
# The feeder and the player are supervised as two explicit processes
# (a FIFO, not a pipeline: `$!` would otherwise capture the feeder) and
# both are recycled if the PCM fails to reach RUNNING, which covers the
# login race where the sink is not yet ready for linking.
set -u
pwcat=${1:?pass the exact pw-cat path}
state=${RUNTIME_DIRECTORY:?systemd RuntimeDirectory is required}
fifo="$state/holder.fifo"
status=/proc/asound/card0/pcm0p/sub0/status
[[ -p $fifo ]] || mkfifo "$fifo" || exit 1
while :; do
    cat /dev/zero > "$fifo" &
    feeder=$!
    "$pwcat" --playback --raw --format s16 --rate 48000 --channels 2 \
             --target alsa_output.platform-sound.HiFi__Speaker__sink \
             --properties 'node.name=fullio-graph-holder' - < "$fifo" &
    stream=$!
    idle=0
    while kill -0 "$stream" 2>/dev/null && kill -0 "$feeder" 2>/dev/null; do
        sleep 10
        if grep -q 'state: RUNNING' "$status" 2>/dev/null; then
            idle=0
        else
            idle=$((idle + 10))
            if (( idle >= 40 )); then
                echo "Holder PCM idle ${idle}s; recycling"
                break
            fi
        fi
    done
    kill "$stream" "$feeder" 2>/dev/null
    wait "$stream" 2>/dev/null
    wait "$feeder" 2>/dev/null
    echo 'Holder stream cycle ended; restarting'
    sleep 2
done
