#!/usr/bin/env bash
# Observe one ordinary WSA runtime-PM wake and idle return with no PCM open.
# Trace only codec regcache activity and selected devices' PM states, no values/audio.
set -euo pipefail
s=${1:?pass exact booted FullIO state directory}
mode=${2:-suppliers-first}
[[ $mode == suppliers-first || $mode == slave-first ]]
[[ $(id -u) == 0 && $(hostname -s) == surface && $s == /home/keke/.local/state/fullio-* ]]
[[ $(<"$s/status") == 0 && $(readlink -e /run/booted-system) == $(readlink -e "$s/system") &&
   $(readlink /nix/var/nix/profiles/system) == system-20-link && $(uname -r) == *-surface-fullio-muted-test ]]
for svc in sshd greetd; do systemctl is-active --quiet "$svc"; done
sound=/sys/firmware/devicetree/base/sound
[[ -e $sound/microsoft,denali-fullio-muted-test && -e $sound/microsoft,denali-fullio-capture-only &&
   ! -e $sound/microsoft,denali-fullio-post-pa-test && ! -e $sound/microsoft,denali-fullio-dsp-start-audit ]]
shopt -s nullglob
streams=(/proc/asound/card*/pcm*/sub*/status)
((${#streams[@]} >= 2))
for f in "${streams[@]}"; do [[ $(<"$f") == closed ]]; done
macro=/sys/bus/platform/devices/6b00000.codec
ctrl=/sys/bus/platform/devices/6b10000.soundwire
left=/sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:0
right=/sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:1
devices=("$macro" "$ctrl" "$left" "$right")
if [[ $mode == slave-first ]]; then
    # A single codec request must wake suppliers through normal PM links;
    # do not add manual votes for the macro/controller or the other codec.
    votes=("$left")
else
    votes=("${devices[@]}")
fi
printf 'Idle wake mode: %s.\n' "$mode"
for d in "${devices[@]}"; do [[ $(<"$d/power/control") == auto && $(<"$d/power/runtime_status") == suspended ]]; done
for d in "$left" "$right"; do
    [[ $(<"$d/status") == Attached ]]
    printf 'Before wake: %s device_number=%s\n' "${d##*/}" "$(<"$d/device_number")"
done
cursor=$(journalctl -kb --no-pager -n 0 --show-cursor | awk '/^-- cursor:/ {print $3}')
[[ -n $cursor ]]
inst=/sys/kernel/tracing/instances/fullio-pm-replay-$$
mkdir "$inst"
record_journal() {
    journalctl -kb --no-pager -o short-monotonic --after-cursor "$cursor" |
        awk '/FullIO PM transition|SWR bus clsh|Parity error|MAX_RETRY|failed to exit clock stop|link failed to connect/'
}
held=0
restore() {
    local i failed=0
    for ((i=held-1; i>=0; i--)); do
        if ! printf 'auto\n' > "${votes[i]}/power/control" || [[ $(<"${votes[i]}/power/control") != auto ]]; then
            printf 'PM policy restore failed for %s\n' "${votes[i]##*/}" >&2
            failed=1
        fi
    done
    if ((failed == 0)); then held=0; fi
    return "$failed"
}
cleanup() {
    local rc=$?
    if ((held)) && ! restore; then rc=1; fi
    printf '0\n' > "$inst/tracing_on"
    if ((rc)); then
        printf 'Incomplete or faulted PM/codec trace summary:\n' >&2
        record_journal >&2 || true
        python3 "$s/hardware/tests/fullio-pm-replay-trace.py" --journal <(record_journal) "$inst/trace" >&2 || true
        head -25 "$inst/trace" >&2
    fi
    rmdir "$inst"
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf '0\n' > "$inst/tracing_on"
printf 'mono\n' > "$inst/trace_clock"
printf '128\n' > "$inst/buffer_size_kb"
for e in regmap/regcache_sync regmap/regmap_hw_write_start rpm/rpm_status; do
    only='name == "sdw:1:0:0217:0204:00:0" || name == "sdw:1:0:0217:0204:00:1"'
    if [[ $e == rpm/* ]]; then only+=' || name == "6b00000.codec" || name == "6b10000.soundwire"'; fi
    printf '%s\n' "$only" > "$inst/events/$e/filter"
    printf '1\n' > "$inst/events/$e/enable"
done
printf '1\n' > "$inst/tracing_on"
health() {
    local d observed log
    for d in "$left" "$right"; do
        observed=$(<"$d/status")
        if [[ $observed != Attached ]]; then
            printf 'Codec %s was %s, not Attached.\n' "${d##*/}" "$observed" >&2
            return 1
        fi
    done
    if ! log=$(journalctl -kb --no-pager -o short-monotonic --after-cursor "$cursor"); then
        echo 'Could not check the kernel journal at this transition.' >&2
        return 1
    fi
    if grep -Ei 'Oops:|BUG:|bus clsh|Parity error|MAX_RETRY|failed to exit clock stop|link failed to connect' <<< "$log"; then return 1; fi
}
for i in "${!votes[@]}"; do
    held=$((i+1))
    printf 'wake %s\n' "${votes[i]##*/}" > "$inst/trace_marker"
    printf 'on\n' > "${votes[i]}/power/control"
    [[ $(<"${votes[i]}/power/control") == on && $(<"${votes[i]}/power/runtime_status") == active ]]
    health || { echo 'Wake disturbed the bus. No further devices woken.' >&2; exit 2; }
done
if [[ $mode == slave-first ]]; then
    for d in "$macro" "$ctrl"; do
        observed=$(<"$d/power/runtime_status")
        printf '%s after a single codec vote: %s\n' "${d##*/}" "$observed"
        [[ $observed == active ]] || exit 3
    done
fi
printf 'restore runtime policy\n' > "$inst/trace_marker"
restore
# The two slave timers expire before the controller and its supplier can
# run their own autosuspend timers. A single 3–5 s deadline is not enough.
for _ in {1..75}; do
    all=true
    for d in "${devices[@]}"; do [[ $(<"$d/power/runtime_status") == suspended ]] || all=false; done
    "$all" && break
    sleep .2
done
printf '0\n' > "$inst/tracing_on"
health
for f in "${streams[@]}"; do [[ $(<"$f") == closed ]]; done
printf 'All four runtime policies restored; both speakers attached with no PCM. Idle return complete: %s.\n' "$all"
record_journal
python3 "$s/hardware/tests/fullio-pm-replay-trace.py" --journal <(record_journal) "$inst/trace"
"$all"
