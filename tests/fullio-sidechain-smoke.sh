#!/usr/bin/env bash
# Capture only an isolated sidechain PCM, not the microphone or a playback graph.
set -euo pipefail
umask 077
alsa=${1:?pass the absolute path to the alsa-utils bin directory}
[[ $alsa == /nix/store/*/bin && -x $alsa/arecord && -x $alsa/amixer ]]
sound=/sys/firmware/devicetree/base/sound
case $(tr -d '\0' <"$sound/microsoft,denali-fullio-feedback-probe") in
    vi)
        kind=VI; rate=8000; port=0; sense=VISENSE
        macro=('WSA WSA_AIF_VI Mixer WSA_SPKR_VI_1' 'WSA WSA_AIF_VI Mixer WSA_SPKR_VI_2')
        ;;
    cps)
        kind=CPS; rate=24000; port=1; sense=CPS; macro=()
        ;;
    *) echo 'Not an isolated FullIO probe.' >&2; exit 1 ;;
esac
[[ $(tr -d '\0' <"$sound/model") == "Denali-FullIO-$kind-Probe" ]]
[[ -r /proc/asound/pcm ]]
if grep -q 'playback [1-9]' /proc/asound/pcm; then
    echo 'Refusing to test while a playback PCM is present.' >&2
    exit 1
fi
pcm=$(awk '/MultiMedia3 Capture/ && /capture [1-9]/ {print $1}' /proc/asound/pcm)
[[ $pcm =~ ^([0-9]+)-([0-9]+):$ ]]
card=$((10#${BASH_REMATCH[1]}))
device=$((10#${BASH_REMATCH[2]}))
work=$(mktemp -d "/run/user/$(id -u)/fullio-${kind,,}.XXXXXX")
controls=(
    "SpkrLeft $sense Switch" "SpkrRight $sense Switch"
    "${macro[@]}"
    "MultiMedia3 Mixer WSA_CODEC_DMA_TX_$port"
)
prior=()
for control in "${controls[@]}"; do
    value=$("$alsa/amixer" -c "$card" cget "name=$control" | awk -F= '/^[[:space:]]*: values=/ {print $2}')
    [[ $value =~ ^(on|off)(,(on|off))*$ ]]
    prior+=("$value")
done
restore() {
    local i
    for ((i=${#controls[@]}-1; i>=0; i--)); do
        "$alsa/amixer" -q -c "$card" cset "name=${controls[i]}" "${prior[i]}" ||
            printf 'Could not restore %s\n' "${controls[i]}" >&2
    done
}
trap restore EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
for i in "${!controls[@]}"; do
    "$alsa/amixer" -q -c "$card" cset "name=${controls[i]}" "${prior[i]//off/on}"
done
period=${2:-960}
case $period in 960|1920|2880) ;; *) echo 'Unsupported diagnostic period.' >&2; exit 1 ;; esac
if [[ -n ${3:-} ]]; then
    [[ $kind == CPS && $3 == /nix/store/*/lib/libasound.so.2 ]]
    timeout 12 python3 "$(dirname -- "$0")/fullio-cps-nonblock.py" "$3" "hw:$card,$device" "$work/samples.raw"
else
    timeout 12 "$alsa/arecord" -D "hw:$card,$device" -t raw -f S32_LE -c 2 -r "$rate" \
        --period-size="$period" --buffer-size="$((period * 4))" -d 2 "$work/samples.raw"
fi
python3 - "$work/samples.raw" "$kind" "$((rate * 2))" <<'PY'
from array import array
from pathlib import Path
import sys

samples = array('i', Path(sys.argv[1]).read_bytes())
if sys.byteorder != 'little':
    samples.byteswap()
kind, frames = sys.argv[2], int(sys.argv[3])
if len(samples) != frames * 2:
    raise SystemExit(f'Unexpected {kind} frame count: {len(samples) // 2}')
counts = [len(set(samples[lane::2])) for lane in (0, 1)]
print(f'{kind}: {frames} frames; unique sample values per lane: {counts}')
for lane, count in enumerate(counts):
    if count == 1:
        print(f'lane {lane} constant: {samples[lane] & 0xffffffff:#010x}')
print(f'Private raw samples: {sys.argv[1]}')
PY
