#!/usr/bin/env bash
# Watch only; never opens PCM or changes PM policy. Run on a healthy one-shot.
set -euo pipefail
repo=$(dirname "$(readlink -e "$0")")
s=${1:?pass exact native build state}
seconds=${2:-300}
[[ $seconds =~ ^[0-9]{1,4}$ ]]
seconds=$((10#$seconds))
((seconds >= 1 && seconds <= 1800))
mode=${3:-passive-link}
case "$mode" in passive-link|vphx|ring-dma) ;; *) echo 'expected passive-link, vphx or ring-dma' >&2; exit 2;; esac
bash "$repo/fullio-boot-preflight.sh" "$s" "$mode"
left=/sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:0
right=/sys/bus/soundwire/devices/sdw:1:0:0217:0204:00:1
devices=("$left" "$right" /sys/bus/platform/devices/{6b00000.codec,6b10000.soundwire})
for d in "${devices[@]}"; do
    [[ $(<"$d/power/control") == auto && $(<"$d/power/runtime_status") == suspended ]]
done
cursor=$(journalctl -kb -n 0 --show-cursor --no-pager | awk '/^-- cursor:/ {print $3}')
[[ -n $cursor ]]
snapshot() {
    local d
    printf 'WSA PM counters and SoundWire IRQs (%s):\n' "$1"
    for d in "${devices[@]}"; do
        printf '%s control=%s runtime=%s active_ms=%s suspended_ms=%s\n' "${d##*/}" \
            "$(<"$d/power/control")" "$(<"$d/power/runtime_status")" \
            "$(<"$d/power/runtime_active_time")" "$(<"$d/power/runtime_suspended_time")"
    done
    # Record both the primary and optional wake lines. Actions are not
    # controller IDs; retain the IRQ numbers if several controllers match.
    grep -E '[[:space:]](soundwire|swr_wake_irq|6b10000\.soundwire)([[:space:],]|$)' /proc/interrupts ||
        printf 'No matching IRQ action; do not infer zero IRQ activity.\n'
}
inst=/sys/kernel/tracing/instances/fullio-passive-$$
mkdir "$inst"
cleanup() {
    local rc=$?
    printf '0\n' > "$inst/tracing_on" || rc=1
    snapshot end || rc=1
    printf 'SoundWire journal during trace (kernel monotonic timestamps):\n'
    journalctl -kb --after-cursor "$cursor" --no-pager -o short-monotonic |
        awk '/6b10000\.soundwire|6b00000\.codec.*FullIO|sdw:1:0:0217:0204|Oops:|BUG:|Kernel panic/' || rc=1
    head -400 "$inst/trace" || rc=1
    if ! awk '/^# entries-in-buffer\/entries-written:/ {
        split($3, n, "/"); checked=1; if (n[1] != n[2]) exit 1
    } NR > 400 {exit 1} END {if (!checked) exit 1}' "$inst/trace"; then
        printf 'Trace truncated or overflowed; do not infer absence of a wake.\n' >&2
        rc=1
    fi
    rmdir "$inst" || rc=1
    exit "$rc"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
printf '0\n' > "$inst/tracing_on"
printf 'mono\n' > "$inst/trace_clock"
printf '128\n' > "$inst/buffer_size_kb"
ctrl='name == "6b10000.soundwire" || name == "6b00000.codec"'
for event in rpm_resume rpm_status; do
    dir=$inst/events/rpm/$event
    printf '%s || name == "%s" || name == "%s"\n' "$ctrl" "${left##*/}" "${right##*/}" > "$dir/filter"
    printf '1\n' > "$dir/enable"
done
printf 'stacktrace:64 if %s\n' "$ctrl" > "$inst/events/rpm/rpm_resume/trigger"
# These are IRQ delivery events for the default hard handler, not the
# threaded controller handler. Use its kernel snapshots for raw slots.
irq=$inst/events/irq/irq_handler_entry
printf 'name == "soundwire" || name == "swr_wake_irq"\n' > "$irq/filter"
printf '1\n' > "$irq/enable"
printf '1\n' > "$inst/tracing_on"
printf 'FullIO passive window begin\n' > "$inst/trace_marker"
snapshot start
printf 'Passive trace started (%d s); no PM writes.\n' "$seconds"
end=$((SECONDS + seconds))
while :; do
    log=$(journalctl -kb --after-cursor "$cursor" --no-pager -o short-monotonic)
    if [[ $(<"$left/status") != Attached || $(<"$right/status") != Attached ]] ||
       grep -Eq 'FullIO SoundWire new streams locked|FullIO clash snapshot|SWR bus clsh|MAX_RETRY|failed to exit clock stop|link failed to connect|Oops:|BUG:|Kernel panic' <<< "$log"; then
        printf 'FullIO passive fault observed in userspace\n' > "$inst/trace_marker"
        printf 'Passive observation stopped at fault; no recovery action.\n' >&2
        exit 2
    fi
    ((SECONDS >= end)) && break
    sleep 1
done
printf 'FullIO passive window end\n' > "$inst/trace_marker"
printf 'Passive window completed without a detected fault (not a recovery proof).\n'
