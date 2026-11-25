#!/usr/bin/env bash
# Temporary WSA runtime-PM hold for PA-off diagnostics on the Surface test host.
set -euo pipefail
s=${1:?pass native build state directory}
mode=${2:?pass taps, routed-taps, fault, mic, worker-mic or gain}
[[ $(id -u) == 0 && $(hostname -s) == surface && $s == /home/keke/.local/state/fullio-* ]]
[[ $(uname -r) == *-surface-fullio-muted-test && $(readlink -f /run/booted-system) == $(readlink -f "$s/system") ]]
sound=/sys/firmware/devicetree/base/sound
[[ -e $sound/microsoft,denali-fullio-muted-test &&
   -e $sound/microsoft,denali-fullio-clock-off-audit &&
   -e $sound/microsoft,denali-fullio-dsp-start-audit &&
   ! -e $sound/microsoft,denali-fullio-post-pa-test ]]
alsa=/nix/store/90kcqvgk6gak7riqymc2sswa9bnmx7p9-alsa-utils-1.2.16/bin
lib=/nix/store/hs142rv75ssn0g6di4ivp94ii7kgywdp-alsa-lib-1.2.16.1/lib/libasound.so.2
case $mode in
    fault)
        [[ -e $sound/microsoft,denali-fullio-dsp-stop-fault-audit ]]
        test_args=("$s/hardware/tests/fullio-stop-fault-smoke.sh" "$s/hardware" "$alsa" "$lib") ;;
    taps)
        [[ -e $sound/microsoft,denali-fullio-immediate-taps-audit ]]
        test_args=("$s/fullio-lpass-capture-smoke.sh" "$s" "$s/hardware" "$alsa" "$lib") ;;
    routed-taps)
        [[ -e $sound/microsoft,denali-fullio-immediate-taps-audit && -e $sound/microsoft,denali-fullio-pa-stop-audit ]]
        test_args=("$s/hardware/tests/fullio-lpass-capture-smoke.sh" "$s" "$s/hardware" "$alsa" "$lib" observe) ;;
    mic)
        [[ ! -e $sound/microsoft,denali-fullio-dsp-stop-fault-audit ]]
        test_args=("$s/hardware/tests/fullio-muted-mic-coexistence.sh" "$s/hardware" "$alsa" "$lib") ;;
    worker-mic)
        [[ -e $sound/microsoft,denali-fullio-pa-off-gain-audit && -e $sound/microsoft,denali-fullio-pa-off-fault-worker ]]
        test_args=("$s/hardware/tests/fullio-muted-mic-coexistence.sh" "$s/hardware" "$alsa" "$lib" worker-fault) ;;
    gain)
        [[ -e $sound/microsoft,denali-fullio-pa-off-gain-audit ]]
        test_args=("$s/hardware/tests/fullio-gain-audit-smoke.sh" "$s/hardware" "$alsa" "$lib") ;;
    *) echo 'Unsupported runtime hold test' >&2; exit 1 ;;
esac
shopt -s nullglob
devices=(/sys/bus/soundwire/devices/sdw:*:0204:*)
[[ ${#devices[@]} == 2 ]]
files=(/sys/bus/platform/devices/6b00000.codec/power/control /sys/bus/platform/devices/6b10000.soundwire/power/control "${devices[0]}/power/control" "${devices[1]}/power/control")
before=()
for f in "${files[@]}"; do
    value=$(<"$f"); [[ $value == auto || $value == on ]]; before+=("$value")
done
restore() {
    local rc=$? i failed=0
    for ((i=${#files[@]}-1;i>=0;i--)); do
        if ! printf '%s\n' "${before[i]}" > "${files[i]}" || [[ $(<"${files[i]}") != "${before[i]}" ]]; then
            printf 'Error restoring runtime policy: %s\n' "${files[i]}" >&2
            failed=1
        fi
    done
    ((failed == 0)) && printf 'WSA runtime policies restored.\n'
    exit $((rc != 0 ? rc : failed))
}
trap restore EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
snapshot() {
    local d
    printf '%s' "$1"
    for d in "${devices[@]}"; do printf ' %s:%s/%s' "${d##*/}" "$(<"$d/status")" "$(<"$d/power/runtime_status")"; done
    printf '\n'
}
snapshot 'Before runtime hold:'
for f in "${files[@]}"; do printf 'on\n' > "$f"; done
for i in {1..20}; do
    a=$(<"${devices[0]}/status"); b=$(<"${devices[1]}/status")
    if [[ $a == Attached && $b == Attached ]]; then break; fi
    sleep .2
done
snapshot 'After runtime hold:'
[[ $a == Attached && $b == Attached ]] || exit 2
runuser -u keke -- env XDG_RUNTIME_DIR=/run/user/$(id -u keke) bash "${test_args[@]}"
