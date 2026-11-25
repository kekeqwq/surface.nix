#!/usr/bin/env bash
# Native MicArray capture alone or across a PA-off, zero-render DSP audit.
# This is not audible duplex; never open ALSA for normal playback.
set -euo pipefail
repo=${1:?pass the hardware source tree}
alsa=${2:?pass the alsa-utils bin directory}
lib=${3:?pass the pinned libasound.so.2}
mode=${4:-normal}
sound=/sys/firmware/devicetree/base/sound
[[ -e $sound/microsoft,denali-fullio-clock-off-audit &&
   ! -e $sound/microsoft,denali-fullio-post-pa-test &&
   ! -e $sound/microsoft,denali-fullio-dsp-stop-fault-audit ]]
render=false
if [[ $mode != link-gate-capture ]]; then
    [[ -e $sound/microsoft,denali-fullio-dsp-start-audit ]]
fi
case $mode in
    normal) [[ ! -e $sound/microsoft,denali-fullio-pa-off-fault-worker ]]; render=true ;;
    worker-fault) [[ -e $sound/microsoft,denali-fullio-pa-off-fault-worker ]]; render=true ;;
    capture-only) [[ -e $sound/microsoft,denali-fullio-pa-off-fault-worker ]] ;;
    link-gate-capture)
        [[ ! -e $sound/microsoft,denali-fullio-dsp-start-audit &&
           -e /sys/firmware/devicetree/base/soc@0/soundwire@6b10000/qcom,denali-fullio-link-gate-test ]]
        log=$(journalctl -kb --no-pager -o cat)
        grep -Fq 'FullIO SoundWire new streams locked: first link error -125' <<< "$log"
        ;;
    *) echo 'Unknown coexistence mode' >&2; exit 1 ;;
esac
if "$render" &&
   journalctl -kb --no-pager -g 'FullIO (silent START/STOP audit|start audit failed|audit GRAPH_STOP unverified)' -n 1 -o cat | grep -q 'FullIO'; then
    echo 'Mic coexistence audit requires an unused START/STOP fixture' >&2
    exit 1
fi
pcm=$(python3 "$repo/tests/fullio-micarray.py")
[[ $pcm =~ ^hw:([0-9]+),([0-9]+)$ ]]
card=${BASH_REMATCH[1]}
alsa_state=/proc/asound/card$card/pcm${BASH_REMATCH[2]}c/sub0/status
controls=(
    'TX DMIC MUX0' 'TX DMIC MUX1' 'TX DEC0 MUX' 'TX DEC1 MUX'
    'TX_AIF1_CAP Mixer DEC0' 'TX_AIF1_CAP Mixer DEC1'
    'MultiMedia3 Mixer TX_CODEC_DMA_TX_3'
)
# The diagnostic disables WirePlumber auto-probing, so use the same route
# as the native UCM profile and restore it after raw ALSA capture.
values=(DMIC1 DMIC0 MSM_DMIC MSM_DMIC 1 1 1,1)
prior=()
changed=0
mixer_value() { "$alsa/amixer" -c "$card" cget "name=$1" | awk -F= '/^[[:space:]]*: values=/ {print $2}'; }
for control in "${controls[@]}"; do
    value=$(mixer_value "$control")
    [[ $value =~ ^([0-9]+|on|off)(,([0-9]+|on|off))*$ ]]
    prior+=("$value")
done
if [[ $mode != normal && ( ${prior[4]} != off || ${prior[5]} != off ) ]]; then
    echo 'Both MicArray DEC route controls must start off for a complete cycle' >&2
    exit 1
fi
umask 077
tmp=$(mktemp -d "${XDG_RUNTIME_DIR:?}/fullio-mic-coexistence.XXXXXX")
recorder=
cleanup() {
    local rc=$? i restored
    if [[ -n $recorder ]]; then
        kill "$recorder" 2>/dev/null || true
        wait "$recorder" 2>/dev/null || true
    fi
    for ((i=changed-1; i>=0; i--)); do
        if ! "$alsa/amixer" -q -c "$card" cset "name=${controls[i]}" "${prior[i]}" ||
           ! restored=$(mixer_value "${controls[i]}") || [[ $restored != "${prior[i]}" ]]; then
            printf 'Could not verify restored %s\n' "${controls[i]}" >&2
            rc=1
        fi
    done
    rm -rf -- "$tmp"
    ((rc != 0)) || printf 'Every temporary MicArray control restored and read back.\n'
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
cursor=$(journalctl -kb --no-pager -n 0 --show-cursor | awk '/^-- cursor:/ {print $3}')
[[ -n $cursor ]]
for i in "${!controls[@]}"; do
    changed=$((i+1))
    "$alsa/amixer" -q -c "$card" cset "name=${controls[i]}" "${values[i]}"
done
for dec in 0 1; do
    [[ $(mixer_value "TX_AIF1_CAP Mixer DEC$dec") == on ]]
done
"$alsa/arecord" -q -D "$pcm" -t wav -f S16_LE -c 2 -r 48000 -d 6 "$tmp/mic.wav" 2>"$tmp/recorder.log" &
recorder=$!
snapshot() {
    awk -v pid="$recorder" '
        $1=="state:" { state=$2 }
        $1=="owner_pid" { owner=$3 }
        $1=="hw_ptr" { frames=$3 }
        $1=="trigger_time:" { started=$2 }
        END {
            if (state!="RUNNING" || owner!=pid || frames !~ /^[0-9]+$/ || started=="") exit 1
            print frames, started
        }
    ' "$alsa_state"
}
for i in {1..40}; do
    if read -r before started < <(snapshot) && ((before > 0)); then break; fi
    kill -0 "$recorder" 2>/dev/null || break
    sleep .05
done
if [[ ! ${before:-} =~ ^[0-9]+$ ]] || ((before <= 0)); then
    head -20 "$tmp/recorder.log" >&2
    echo 'MicArray not running; no DSP START attempted' >&2
    exit 1
fi
rc=0
case $mode in
    worker-fault) bash "$repo/tests/fullio-gain-audit-smoke.sh" "$repo" "$alsa" "$lib" || rc=$? ;;
    normal) bash "$repo/tests/fullio-mute-smoke.sh" "$alsa" "$lib" || rc=$? ;;
    capture-only|link-gate-capture) sleep 0.2 ;;
esac
read -r after still_started < <(snapshot) || rc=1
if "$render"; then
    log=$(journalctl -kb --no-pager --after-cursor "$cursor" -g 'FullIO|ASoC')
    # The worker audit already emitted its monotonic journal for DAPM correlation.
    [[ $mode == worker-fault ]] || printf '%s\n' "$log"
fi
wait "$recorder" || rc=1
recorder=
[[ ! -s $tmp/recorder.log ]] || { head -20 "$tmp/recorder.log" >&2; exit 1; }
((rc == 0 && after > before))
[[ $started == "$still_started" ]]
if "$render"; then
    if [[ $mode == worker-fault ]]; then
        grep -Fq 'FullIO start audit failed; GRAPH_STOP acknowledged' <<< "$log"
    else
        grep -Fq 'FullIO silent START/STOP audit passed; no PA enable or PCM writes' <<< "$log"
    fi
    grep -Fq 'FullIO CPS wake registers restored and verified' <<< "$log"
    ! grep -Eq 'clock-off audit found enabled|clock shutdown/audit failed|CPS probe wake restore failed' <<< "$log"
fi
printf 'MicArray hardware pointer progressed (%s): %s -> %s frames.\n' "$mode" "$before" "$after"
python3 "$repo/tests/fullio-micarray.py" "$tmp/mic.wav"
if "$render"; then
    printf 'Native stereo capture coexisted with PA-off DSP START/STOP (%s); not audible duplex.\n' "$mode"
fi
