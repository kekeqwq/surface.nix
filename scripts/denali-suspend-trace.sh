#!/usr/bin/env bash
# Collect one attended cycle. Never selects a mode; requests sleep only on opt-in.
set -euo pipefail
umask 077
root=/sys/kernel/tracing
snapshot=$(dirname -- "${BASH_SOURCE[0]}")/denali-power-snapshot.sh
name=denali_suspend_$$
instance=$root/instances/$name
registered=()
created=0

usage() { echo "usage: sudo $0 {deep|s2idle} NEW_OUTPUT_DIRECTORY [--request|--request-after-auth] [--wsa-votes|--psci-system]" >&2; exit 2; }
[[ $# -ge 2 && ( $1 == deep || $1 == s2idle ) ]] || usage
mode=$1
output=$2
shift 2
request=
wsa_votes=0
psci_system=0
for opt; do
    case $opt in
        --request|--request-after-auth) [[ -z $request ]] || usage; request=$opt ;;
        --wsa-votes) (( ! wsa_votes && ! psci_system )) || usage; wsa_votes=1 ;;
        --psci-system) [[ $mode == s2idle ]] && (( ! wsa_votes && ! psci_system )) || usage; psci_system=1 ;;
        *) usage ;;
    esac
done
[[ $EUID == 0 && -t 0 && -t 1 ]] || { echo 'Run as root in an attended terminal.' >&2; exit 2; }
[[ -d $root/instances && -r $snapshot ]] || { echo 'tracefs and the power snapshot script are required.' >&2; exit 2; }
sleep_modes=$(</sys/power/mem_sleep)
[[ " $sleep_modes " == *" [$mode] "* ]] || { echo "Current mode is $sleep_modes, requested $mode; no change made." >&2; exit 2; }
[[ -w $root/kprobe_events ]] || { echo 'Wake IRQ tracing requires writable kprobe_events.' >&2; exit 2; }
if [[ $mode == deep ]]; then
    grep -qE '[[:space:]]psci_system_suspend_enter$' /proc/kallsyms || {
        echo 'No psci_system_suspend_enter symbol; cannot distinguish firmware return.' >&2; exit 2;
    }
fi
wsa_counts() {
    local clk file path value
    for clk in LPASS_HW_MACRO LPASS_HW_DCODEC; do
        for file in clk_prepare_count clk_enable_count; do
            path=/sys/kernel/debug/clk/$clk/$file
            if [[ -r $path ]] && value=$(<"$path") && [[ $value =~ ^[0-9]+$ ]]; then
                printf '%s/%s=%s\n' "$clk" "$file" "$value"
            else
                printf '%s/%s=unavailable\n' "$clk" "$file"
            fi
        done
    done
}
mkdir -- "$output"

cleanup() {
    local status=$? probe
    trap - EXIT
    if (( created )); then
        echo 0 >"$instance/tracing_on" || status=1
        for probe in "${registered[@]}"; do
            echo 0 >"$instance/events/$name/$probe/enable" || status=1
        done
        rmdir -- "$instance" || status=1
    fi
    for probe in "${registered[@]}"; do
        printf '%s\n' "-:$name/$probe" >>"$root/kprobe_events" || status=1
    done
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
printf '1\n' >"$instance/events/power/wakeup_source_activate/enable"
add_probe() {
    local type=$1 probe=$2
    shift 2
    printf '%s:%s/%s %s\n' "$type" "$name" "$probe" "$*" >>"$root/kprobe_events"
    registered+=("$probe")
    printf '1\n' >"$instance/events/$name/$probe/enable"
}
add_probe p wake_irq 'pm_system_irq_wakeup irq=$arg1:u32'
# In s2idle the RPMh callbacks can fire many times per second on the
# idle CPU and overwrite the narrow WSA trace. Keep them for other runs.
if [[ $mode == deep || ( $wsa_votes == 0 && $psci_system == 0 ) ]] &&
    grep -qE '[[:space:]]rpmh_rsc_pd_callback$' /proc/kallsyms; then
    add_probe p rpmh_pd_enter 'rpmh_rsc_pd_callback action=$arg2:u64'
    add_probe r rpmh_pd_return 'rpmh_rsc_pd_callback result=$retval:x32'
    add_probe r rpmh_flush_return 'rpmh_flush result=$retval:s32'
fi
if [[ $mode == deep ]]; then
    add_probe r psci_return 'psci_system_suspend_enter psci_ret=$retval:s32'
fi

if (( wsa_votes )); then
    for op in vote unvote; do
        sym=q6prm_${op}_lpass_core_hw
        entry=wsa_${op}_entry_$name
        add_probe p "$entry" "$sym"' core=$arg2:u32'
        # 1 = LPASS macro, 2 = digital codec in the pinned Q6PRM ABI.
        printf 'core == 1 || core == 2\n' >"$instance/events/$name/$entry/filter"
        add_probe r "wsa_${op}_return_$name" "$sym"' result=$retval:s32'
    done
    wsa_counts >"$output/wsa-before.txt"
fi
if (( psci_system )); then
    psci_param=$(python3 - <<'PY'
from pathlib import Path
root = Path('/sys/firmware/devicetree/base')
state = (root / 'cpus/domain-idle-states/domain-sleep-0').resolve()
refs = (root / 'psci/power-domain-system/domain-idle-states').read_bytes()
handle = (state / 'phandle').read_bytes()
param = (state / 'arm,psci-suspend-param').read_bytes()
if len(handle) != 4 or refs != handle or len(param) != 4 or not any(param):
    raise SystemExit('Unexpected Denali PSCI system idle state; not arming')
print(int.from_bytes(param, 'big'))
PY
    )
    for phase in enter exit; do
        event=$instance/events/power/psci_domain_idle_$phase
        printf 's2idle == 1 && state == %s\n' "$psci_param" >"$event/filter"
        printf '1\n' >"$event/enable"
    done
fi
cat /proc/interrupts >"$output/interrupts-before.txt"
bash "$snapshot" >"$output/before.txt"
{
    printf 'mode=%s\n' "$mode"
    printf 'trace_clock=%s\n' "$(<"$instance/trace_clock")"
    printf 'booted_system=%s\n' "$(readlink -f /run/booted-system)"
    printf 'trace_group=%s\n' "$name"
    printf 'wsa_votes=%s\n' "$wsa_votes"
    printf 'psci_system_param=%s\n' "${psci_param:-disabled}"
} >"$output/session.txt"
printf '1\n' >"$instance/tracing_on"
if [[ $request == --request-after-auth ]]; then
    before_success=$(</sys/power/suspend_stats/success)
    before_fail=$(</sys/power/suspend_stats/fail)
    [[ " $(</sys/power/mem_sleep) " == *" [$mode] "* ]] || { echo 'Selected mode changed; no suspend requested.' >&2; exit 2; }
    printf 'Trace armed for %s. Requesting one cycle now.\n' "$mode"
    systemctl --no-block suspend
elif [[ $request == --request ]]; then
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
if [[ $request == --request-after-auth ]]; then
    confirmed=0
    deadline=$((SECONDS + 120))
    until (( SECONDS >= deadline )); do
        if [[ $(</sys/power/suspend_stats/success) != "$before_success" || $(</sys/power/suspend_stats/fail) != "$before_fail" ]]; then
            state=$(systemctl show -p ActiveState --value systemd-suspend.service)
            [[ $state == inactive || $state == failed ]] && break
        fi
        sleep 1
    done
elif ! read -r -t 240; then
    printf 'No operator confirmation; saving available evidence without a confirmed wake.\n' >&2
    confirmed=0
fi
printf '0\n' >"$instance/tracing_on"
cat "$instance/trace" >"$output/trace.txt"
if (( wsa_votes )); then
    wsa_counts >"$output/wsa-after.txt"
fi
if (( wsa_votes || psci_system )); then
    for stats in "$instance"/per_cpu/cpu*/stats; do
        [[ -r $stats ]] || continue
        printf '\n--- %s ---\n' "$stats"
        cat "$stats"
    done >"$output/trace-buffer-stats.txt"
    if (( wsa_votes )) && [[ -r $root/kprobe_profile ]]; then
        awk -v suffix="_$name" '$1 ~ (suffix "$")' "$root/kprobe_profile" >"$output/kprobe-profile.txt"
    fi
fi
cat /proc/interrupts >"$output/interrupts-after.txt"
printf 'operator_wake_confirmation=%s\n' "$confirmed" >>"$output/session.txt"
bash "$snapshot" >"$output/after.txt"
python3 "${snapshot%/*}/denali-suspend-readout.py" "$output/before.txt" "$output/after.txt" >"$output/readout.json"
printf 'Saved trace and readout: %s\n' "$output"
[[ $request == --request-after-auth ]] || (( confirmed ))
