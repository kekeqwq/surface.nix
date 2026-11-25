#!/usr/bin/env bash
# Observe WSA DAPM edges around the PA-off deferred fault audit.
set -euo pipefail
s=${1:?pass exact native build state directory}
route=${2:-plain}
mode=${3:-gain}
[[ $route == plain || $route == rx-route ]]
[[ $mode == gain || $mode == worker-mic || ( $mode == routed-taps && $route == rx-route ) ]]
tests=$(dirname -- "${BASH_SOURCE[0]}")
bash "$tests/fullio-boot-preflight.sh" "$s"
sound=/sys/firmware/devicetree/base/sound
if [[ $mode == routed-taps ]]; then
    [[ -e $sound/microsoft,denali-fullio-immediate-taps-audit &&
       ! -e $sound/microsoft,denali-fullio-pa-off-fault-worker ]]
else
    [[ -e $sound/microsoft,denali-fullio-pa-off-fault-worker ]]
fi
for d in /sys/bus/platform/devices/6b00000.codec /sys/bus/platform/devices/6b10000.soundwire; do
    [[ $(<"$d/power/control") == on && $(<"$d/power/runtime_status") == active ]]
done
t=/sys/kernel/tracing/instances/fullio-wsa-dapm-$$
mkdir "$t"
prior=()
cleanup() {
    local rc=$? i verify
    for ((i=${changed:-0}-1; i>=0; i--)); do
        if ! "$amixer" -q -c "$card" cset "name=${controls[i]}" "${prior[i]}" ||
           ! verify=$(mixer_value "${controls[i]}") || [[ $verify != "${prior[i]}" ]]; then
            printf 'Could not verify restored DAPM control %s\n' "${controls[i]}" >&2
            rc=1
        fi
    done
    printf '0\n' > "$t/tracing_on"
    rmdir "$t"
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf '0\n' > "$t/tracing_on"
printf 'mono\n' > "$t/trace_clock"
printf '16\n' > "$t/buffer_size_kb"
for event in snd_soc_dapm_widget_power snd_soc_dapm_widget_event_done; do
    f=$t/events/asoc/$event
    printf '%s\n' 'name ~ "*SPKR*" || name ~ "*WSA*" || name ~ "*VIINPUT*" || name ~ "*CPS*"' > "$f/filter"
    printf '1\n' > "$f/enable"
done
printf '1\n' > "$t/tracing_on"
if [[ $route == rx-route ]]; then
    amixer=/nix/store/90kcqvgk6gak7riqymc2sswa9bnmx7p9-alsa-utils-1.2.16/bin/amixer
    pcm=$(awk '/MultiMedia1 Playback/ && /playback [1-9]/ {print $1}' /proc/asound/pcm)
    [[ $pcm =~ ^([0-9]+)-([0-9]+):$ ]]
    card=$((10#${BASH_REMATCH[1]}))
    shopt -s nullglob
    for f in /proc/asound/card"$card"/pcm*/sub*/status; do [[ $(<"$f") == closed ]]; done
    mixer_value() { "$amixer" -c "$card" cget "name=$1" | awk -F= '/^[[:space:]]*: values=/ {print $2}'; }
    # Standard upstream stereo WSA macro route plus the two DAC transports.
    # Do not change gain, digital mute, protection, boost or compander.
    controls=(
        'WSA WSA RX0 MUX' 'WSA WSA RX1 MUX' 'WSA WSA_RX0 INP0' 'WSA WSA_RX1 INP0'
        'SpkrLeft DAC Switch' 'SpkrRight DAC Switch'
    )
    values=(AIF1_PB AIF1_PB RX0 RX1 1 1)
    expected=(1 1 1 2 on on)
    for name in "${controls[@]}"; do
        value=$(mixer_value "$name"); [[ $value =~ ^([0-9]+|on|off)$ ]]; prior+=("$value")
    done
    # Do not turn an unexpectedly selected alternate/MIX path off for the test;
    # reject the state so the validation covers precisely the direct stereo route.
    for lane in 0 1; do
        for input in INP1 INP2 'MIX INP'; do
            [[ $(mixer_value "WSA WSA_RX$lane $input") == 0 ]]
        done
        [[ $(mixer_value "WSA WSA RX_MIX$lane MUX") == 0 ]]
        gain=$(mixer_value "WSA WSA_RX$lane Digital Volume")
        [[ $gain =~ ^[0-9]+$ ]]
        ((gain <= 81))
    done
    for side in Left Right; do
        gain=$(mixer_value "Spkr$side PA Volume")
        [[ $gain =~ ^[0-9]+$ ]]
        ((gain <= 6))
    done
    for i in "${!controls[@]}"; do
        changed=$((i+1))
        "$amixer" -q -c "$card" cset "name=${controls[i]}" "${values[i]}"
        [[ $(mixer_value "${controls[i]}") == "${expected[i]}" ]]
    done
    printf 'Direct stereo RX and both DAC ports verified; alternate inputs off, gain unchanged and capped.\n'
fi
rc=0
report=$(bash "$tests/fullio-test-with-runtime-hold.sh" "$s" "$mode" 2>&1) || rc=$?
printf '0\n' > "$t/tracing_on"
# The bounded trace contains widget names and states, never PCM data.
trace=$(<"$t/trace")
printf '%s\n%s\n' "$report" "$trace"
((rc == 0)) || exit "$rc"
if [[ $route == rx-route ]]; then
    verify=()
    [[ $mode != routed-taps ]] || verify+=(--taps)
    [[ ! -e $sound/microsoft,denali-fullio-pa-off-missing-stop-proof ]] || verify+=(--missing-proof)
    printf '%s\n%s\n' "$report" "$trace" | python3 "$tests/fullio-dapm-stop-order.py" "${verify[@]}" /dev/stdin
fi
if [[ -e $sound/microsoft,denali-fullio-pa-off-guard-audit ]]; then
    [[ $route == rx-route ]]
    printf '%s\n' "$report" | python3 "$tests/fullio-codec-guard-log.py" /dev/stdin
fi
