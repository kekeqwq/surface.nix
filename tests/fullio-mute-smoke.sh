#!/usr/bin/env bash
# Open and prepare the muted calibration graph; never trigger or write samples.
set -euo pipefail
alsa=${1:?pass the alsa-utils bin directory}
lib=${2:?pass the pinned libasound.so.2}
[[ $alsa == /nix/store/*/bin && $lib == /nix/store/*/lib/libasound.so.2 ]]
[[ $(uname -r) == *-surface-fullio-muted-test ]]
[[ $(tr -d '\0' </sys/firmware/devicetree/base/sound/model) == X1E80100-Microsoft-Surface-Pro-11-FullIO-v19c0 ]]
sound=/sys/firmware/devicetree/base/sound
[[ -e $sound/microsoft,denali-fullio-muted-test &&
   ! -e $sound/microsoft,denali-fullio-post-pa-test &&
   ! -e $sound/microsoft,denali-fullio-pa-on-smoke ]] || {
    printf 'No PCM: this test requires a PA-off fixture.\n' >&2
    exit 2
}
mode=${3:-normal}
swr=/sys/firmware/devicetree/base/soc@0/soundwire@6b10000
case $mode in
    normal) [[ ! -e $sound/microsoft,denali-fullio-dsp-stop-fault-audit && ! -e $sound/microsoft,denali-fullio-pa-off-fault-worker ]] ;;
    fault|fault-retry) [[ -e $sound/microsoft,denali-fullio-dsp-stop-fault-audit ]] ;;
    worker-fault) [[ -e $sound/microsoft,denali-fullio-pa-off-fault-worker && ! -e $sound/microsoft,denali-fullio-dsp-stop-fault-audit && ! -e $sound/microsoft,denali-fullio-pa-off-missing-stop-proof ]] ;;
    missing-proof|latched-reopen) [[ -e $sound/microsoft,denali-fullio-pa-off-fault-worker && -e $sound/microsoft,denali-fullio-pa-off-missing-stop-proof && ! -e $sound/microsoft,denali-fullio-dsp-stop-fault-audit ]] ;;
    link-gate) [[ -e $swr/qcom,denali-fullio-link-gate-test && -e $swr/qcom,denali-fullio-link-gate && ! -e $sound/microsoft,denali-fullio-dsp-start-audit ]] ;;
    *) echo 'Unknown audit mode' >&2; exit 1 ;;
esac
pcm=$(awk '/MultiMedia1 Playback/ && /playback [1-9]/ {print $1}' /proc/asound/pcm)
[[ $pcm =~ ^([0-9]+)-([0-9]+):$ ]]
card=$((10#${BASH_REMATCH[1]}))
device=$((10#${BASH_REMATCH[2]}))
controls=(
    'SpkrLeft VISENSE Switch' 'SpkrRight VISENSE Switch'
    'SpkrLeft CPS Switch' 'SpkrRight CPS Switch'
    'WSA_CODEC_DMA_RX_0 Audio Mixer MultiMedia1'
)
# The second open must fail without touching a route or reaching hw_params.
if [[ $mode == latched-reopen ]]; then controls=(); fi
prior=()
for control in "${controls[@]}"; do
    value=$("$alsa/amixer" -c "$card" cget "name=$control" | awk -F= '/^[[:space:]]*: values=/ {print $2}')
    [[ $value =~ ^(on|off)(,(on|off))*$ ]]
    prior+=("$value")
done
restore() {
    local rc=$? i value
    for ((i=${#controls[@]}-1; i>=0; i--)); do
        if ! "$alsa/amixer" -q -c "$card" cset "name=${controls[i]}" "${prior[i]}" ||
           ! value=$("$alsa/amixer" -c "$card" cget "name=${controls[i]}" | awk -F= '/^[[:space:]]*: values=/ {print $2}') ||
           [[ $value != "${prior[i]}" ]]; then
            printf 'Could not verify restored %s\n' "${controls[i]}" >&2
            rc=1
        fi
    done
    exit "$rc"
}
trap restore EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
values=(on on on on 1,1)
# The topology mixer uses the first slot for route state; do not require
# its unused second slot to echo the value written by amixer.
expected=(on on on on on,off)
for i in "${!controls[@]}"; do
    "$alsa/amixer" -q -c "$card" cset "name=${controls[i]}" "${values[i]}"
done
for i in "${!controls[@]}"; do
    value=$("$alsa/amixer" -c "$card" cget "name=${controls[i]}" | awk -F= '/^[[:space:]]*: values=/ {print $2}')
    [[ $value == "${expected[i]}" ]] || {
        printf 'Test route did not take effect: %s=%s\n' "${controls[i]}" "$value" >&2
        exit 1
    }
done
timeout 24 python3 - "$lib" "hw:$card,$device" "$mode" <<'PY'
import ctypes as c
import errno
import sys

lib = c.CDLL(sys.argv[1])
lib.snd_strerror.restype = c.c_char_p
pcm = c.c_void_p()
rc = lib.snd_pcm_open(c.byref(pcm), sys.argv[2].encode(), 0, 1)
if sys.argv[3] == 'latched-reopen':
    if rc == -errno.ENOTRECOVERABLE:
        print('reopen denied by sticky shutdown-proof latch (-131); no params or trigger')
        sys.exit(0)
    if rc >= 0:
        lib.snd_pcm_close(pcm)
    sys.exit(f'expected latched reopen denial, got {rc}')
if rc < 0:
    if sys.argv[3] == 'link-gate' and rc == -errno.ENOTRECOVERABLE:
        print('open denied by sticky link gate (-131); no params or trigger')
        sys.exit(0)
    sys.exit(f'open: {lib.snd_strerror(rc).decode()} ({rc})')
try:
    rc = lib.snd_pcm_set_params(pcm, 2, 3, 2, 48000, 0, 80000)
    print(f'prepare only: {lib.snd_strerror(rc).decode()} ({rc}); no trigger or samples')
finally:
    lib.snd_pcm_close(pcm)
if rc == 0:
    sys.exit('Unexpected prepare success on the muted calibration fixture')
wanted = {'normal': errno.EOPNOTSUPP, 'fault': errno.ECANCELED,
          'fault-retry': errno.EALREADY, 'worker-fault': errno.ECANCELED,
          'missing-proof': errno.ENOTRECOVERABLE, 'link-gate': errno.ENOTRECOVERABLE}
if rc != -wanted[sys.argv[3]]:
    sys.exit('Prepare stopped for a reason other than the expected diagnostic result')
PY
