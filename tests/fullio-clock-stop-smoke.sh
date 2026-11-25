#!/usr/bin/env bash
# Diagnose runtime clock-stop on an idle, PA-blocked FullIO fixture.
# Release one or both boot-held PM votes, then restore them. No PCM open.
set -euo pipefail
s=${1:?pass exact PA-off build state directory}
mode=${2:?pass controller, macro, or paired}
[[ $(id -u) == 0 && $(hostname -s) == surface && $s == /home/keke/.local/state/fullio-* ]]
[[ $(uname -r) == *-surface-fullio-muted-test && $(readlink -f /run/booted-system) == $(readlink -f "$s/system") ]]
sound=/sys/firmware/devicetree/base/sound
[[ -e $sound/microsoft,denali-fullio-muted-test &&
   -e $sound/microsoft,denali-fullio-clock-off-audit &&
   ! -e $sound/microsoft,denali-fullio-post-pa-test ]]
shopt -s nullglob
macro=/sys/bus/platform/devices/6b00000.codec/power
controller=/sys/bus/platform/devices/6b10000.soundwire/power
devices=(/sys/bus/soundwire/devices/sdw:*:0204:*)
substreams=(/proc/asound/card*/pcm*/sub*/status)
[[ ${#devices[@]} == 2 && ${#substreams[@]} -gt 0 ]]
for f in "${substreams[@]}"; do [[ $(<"$f") == closed ]]; done
for p in "$macro" "$controller"; do [[ $(<"$p/control") == on && $(<"$p/runtime_status") == active ]]; done
for d in "${devices[@]}"; do [[ $(<"$d/status") == Attached && $(<"$d/power/control") == auto ]]; done
case $mode in
    controller) targets=("$controller") ;;
    macro) targets=("$macro") ;;
    paired) targets=("$macro" "$controller") ;;
    *) exit 1 ;;
esac
cursor=$(journalctl -kb --no-pager -n 0 --show-cursor | awk '/^-- cursor:/ {print $3}')
[[ -n $cursor ]]
restore() {
    local rc=$? target
    for target in "${targets[@]}"; do
        if ! printf 'on\n' > "$target/control" || [[ $(<"$target/control") != on ]]; then
            printf 'Could not restore %s/control\n' "$target" >&2
            rc=1
        fi
    done
    exit "$rc"
}
trap restore EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
snapshot() {
    local d
    printf 'Clock-stop %s (%s): macro=%s controller=%s' "$mode" "$1" "$(<"$macro/runtime_status")" "$(<"$controller/runtime_status")"
    for d in "${devices[@]}"; do printf ' %s:%s' "${d##*/}" "$(<"$d/status")"; done
    printf '\n'
}
have_status() {
    local target
    for target in "${targets[@]}"; do [[ $(<"$target/runtime_status") == "$1" ]] || return 1; done
}
snapshot before
for target in "${targets[@]}"; do printf 'auto\n' > "$target/control"; done
for i in {1..25}; do
    if have_status suspended; then break; fi
    sleep .2
done
snapshot after-auto
suspended=false
if have_status suspended; then suspended=true; fi
for target in "${targets[@]}"; do printf 'on\n' > "$target/control"; done
for i in {1..15}; do
    if have_status active &&
       [[ $(<"${devices[0]}/status") == Attached && $(<"${devices[1]}/status") == Attached ]]; then break; fi
    sleep .2
done
snapshot after-resume
if ! log=$(journalctl -kb --no-pager --after-cursor "$cursor" -g 'Parity error|bus clsh|MAX_RETRY|failed to exit clock stop|link failed to connect'); then log=; fi
printf '%s\n' "$log"
$suspended || { echo 'Not all selected devices runtime-suspended; inconclusive.'; exit 3; }
have_status active
[[ $(<"${devices[0]}/status") == Attached && $(<"${devices[1]}/status") == Attached && -z $log ]]
printf 'One %s suspend/resume preserved both attachments.\n' "$mode"
