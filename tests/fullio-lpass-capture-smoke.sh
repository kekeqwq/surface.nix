#!/usr/bin/env bash
# One bounded DIAG session around the PA-off audit. Raw records never leave runtime tmpfs.
set -euo pipefail
state=${1:?pass the diagnostic state directory}
hardware=${2:?pass the hardware source snapshot}
alsa=${3:?pass the pinned alsa-utils bin directory}
lib=${4:?pass the pinned libasound}
expect=${5:-feedback}
[[ $expect == feedback || $expect == observe ]]
[[ $(uname -r) == *-surface-fullio-muted-test ]]
sound=/sys/firmware/devicetree/base/sound
[[ -e $sound/microsoft,denali-fullio-dsp-start-audit && -e $sound/microsoft,denali-fullio-clock-off-audit ]]
[[ ! -e $sound/microsoft,denali-fullio-post-pa-test ]]
if [[ $expect == observe ]]; then
    [[ -e $sound/microsoft,denali-fullio-immediate-taps-audit && -e $sound/microsoft,denali-fullio-pa-stop-audit &&
       ! -e $sound/microsoft,denali-fullio-pa-off-fault-worker && ! -e $sound/microsoft,denali-fullio-dsp-stop-fault-audit ]]
fi
[[ $(readlink -f /run/booted-system) == $(readlink -f "$state/system") ]]
if journalctl -kb --no-pager -n 1 -g 'silent START/STOP audit passed|start audit failed|GRAPH_STOP unverified' | grep -q 'FullIO'; then
    echo 'This boot already attempted the PA-off START/STOP transaction.' >&2
    exit 1
fi
umask 077
work=$(mktemp -d "${XDG_RUNTIME_DIR:?}/fullio-diag-XXXXXX")
collector=''
cleanup() {
    if [[ -n $collector ]]; then
        kill -TERM "$collector" 2>/dev/null || true
        wait "$collector" 2>/dev/null || true
    fi
    rm -rf -- "$work"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"$state/fullio-qrtr-discovery" > "$work/before"
! grep -Eq 'service=4097 instance=(64|65|66|68) ' "$work/before"
"$state/fullio-qrtr-lpass-discovery" --capture-1586 "$work/taps.archive" > "$work/collector.log" 2>&1 &
collector=$!
for i in {1..30}; do
    grep -Fq 'capture armed' "$work/collector.log" && break
    kill -0 "$collector" 2>/dev/null || break
    sleep 0.1
done
cursor=$(journalctl -kb --no-pager -n 0 --show-cursor | awk '/^-- cursor:/ {print $3}')
smoke=1
if grep -Fq 'capture armed' "$work/collector.log"; then
    smoke=0
    bash "$hardware/tests/fullio-mute-smoke.sh" "$alsa" "$lib" || smoke=$?
fi
capture=0
wait "$collector" || capture=$?
collector=''
grep -E 'LPASS (command service|passive FEATURE|FEATURE reply|DIAG-ID|0x1586|zero mask|data datagrams|capture failed)' "$work/collector.log" || true
evidence=$(journalctl -kb --no-pager -o short-monotonic --after-cursor "$cursor" -g 'FullIO|ASoC')
printf '%s\n' "$evidence"
sleep 1
"$state/fullio-qrtr-discovery" > "$work/after"
! grep -Eq 'service=4097 instance=(64|65|66|68) ' "$work/after"
(( capture == 0 && smoke == 0 ))
grep -Fq 'FullIO silent START/STOP audit passed; no PA enable or PCM writes' <<< "$evidence"
! grep -Eq 'clock-off audit found enabled|clock shutdown/audit failed|CPS probe wake restore failed|PA shutdown not fully verified|PA-off teardown failed:' <<< "$evidence"
if [[ $expect == observe ]]; then
    grep -Fq 'FullIO immediate VI/CPS taps configured' <<< "$evidence"
    grep -Fq 'FullIO CPS wake registers restored and verified' <<< "$evidence"
    for amp in 0 1; do
        grep -Fq "sdw:1:0:0217:0204:00:$amp: FullIO PA-off teardown verified" <<< "$evidence"
    done
    python3 "$hardware/tests/fullio-feedback-samples.py" --archive "$work/taps.archive" --allow-empty-archive
else
    python3 "$state/fullio-feedback-samples.py" --archive "$work/taps.archive"
fi
