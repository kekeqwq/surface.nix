#!/usr/bin/env bash
# Collect one attended cycle. Never selects a mode; requests sleep only on opt-in.
set -euo pipefail
umask 077
root=/sys/kernel/tracing
snapshot=$(dirname -- "${BASH_SOURCE[0]}")/denali-power-snapshot.sh
name=denali_suspend_$$
instance=$root/instances/$name
probe=psci_return
registered=0
created=0

usage() { echo "usage: sudo $0 {deep|s2idle} NEW_OUTPUT_DIRECTORY [--request]" >&2; exit 2; }
[[ $# -ge 2 && $# -le 3 && ( $1 == deep || $1 == s2idle ) ]] || usage
mode=$1
output=$2
request=${3:-}
[[ -z $request || $request == --request ]] || usage
[[ $EUID == 0 && -t 0 && -t 1 ]] || { echo 'Run as root in an attended terminal.' >&2; exit 2; }
[[ -d $root/instances && -r $snapshot ]] || { echo 'tracefs and the power snapshot script are required.' >&2; exit 2; }
sleep_modes=$(</sys/power/mem_sleep)
[[ " $sleep_modes " == *" [$mode] "* ]] || { echo "Current mode is $sleep_modes, requested $mode; no change made." >&2; exit 2; }
if [[ $mode == deep ]]; then
    [[ -w $root/kprobe_events ]] || { echo 'deep requires writable kprobe_events.' >&2; exit 2; }
    grep -qE '[[:space:]]psci_system_suspend_enter$' /proc/kallsyms || {
        echo 'No psci_system_suspend_enter symbol; cannot distinguish firmware return.' >&2; exit 2;
    }
fi
mkdir -- "$output"

cleanup() {
    local status=$?
    trap - EXIT
    if (( created )); then
        echo 0 >"$instance/tracing_on" || status=1
        if (( registered )); then
            echo 0 >"$instance/events/$name/$probe/enable" || status=1
        fi
        rmdir -- "$instance" || status=1
    fi
    if (( registered )); then
        printf '%s\n' "-:$name/$probe" >>"$root/kprobe_events" || status=1
    fi
    exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -- "$instance"
created=1
printf '0\n' >"$instance/tracing_on"
printf '128\n' >"$instance/buffer_size_kb"
# The default local clock can hide elapsed time while the CPUs are suspended.
printf 'boot\n' >"$instance/trace_clock"
printf '1\n' >"$instance/events/power/suspend_resume/enable"
if [[ $mode == deep ]]; then
    printf 'r:%s/%s psci_system_suspend_enter psci_ret=$retval:s32\n' "$name" "$probe" >>"$root/kprobe_events"
    registered=1
    printf '1\n' >"$instance/events/$name/$probe/enable"
fi

bash "$snapshot" >"$output/before.txt"
{
    printf 'mode=%s\n' "$mode"
    printf 'trace_clock=%s\n' "$(<"$instance/trace_clock")"
    printf 'booted_system=%s\n' "$(readlink -f /run/booted-system)"
    printf 'trace_group=%s\n' "$name"
} >"$output/session.txt"
printf '1\n' >"$instance/tracing_on"
if [[ $request == --request ]]; then
    printf 'Trace armed for %s. Type SUSPEND then Enter to request one cycle.\n' "$mode"
    printf 'After about 30 seconds, wake with the power button and press Enter here to save.\n'
    if ! read -r -t 120 answer || [[ $answer != SUSPEND ]]; then
        echo 'No suspend requested.' >&2
        exit 2
    fi
    [[ " $(</sys/power/mem_sleep) " == *" [$mode] "* ]] || { echo 'Selected mode changed; no suspend requested.' >&2; exit 2; }
    systemctl --no-block suspend
else
    printf 'Trace armed for %s. Suspend once from another terminal, wake with the power button, then press Enter here.\n' "$mode"
fi
confirmed=1
if ! read -r -t 240; then
    printf 'No operator confirmation; saving available evidence without a confirmed wake.\n' >&2
    confirmed=0
fi
printf '0\n' >"$instance/tracing_on"
cat "$instance/trace" >"$output/trace.txt"
printf 'operator_wake_confirmation=%s\n' "$confirmed" >>"$output/session.txt"
bash "$snapshot" >"$output/after.txt"
python3 "${snapshot%/*}/denali-suspend-readout.py" "$output/before.txt" "$output/after.txt" >"$output/readout.json"
printf 'Saved trace and readout: %s\n' "$output"
(( confirmed ))
