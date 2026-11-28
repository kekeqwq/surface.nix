#!/usr/bin/env bash
# Read-only snapshots for attended power tests. Never changes sleep or charge policy.
set -euo pipefail
export LC_ALL=C

root=/sys/class/power_supply
[[ -r "$root/BAT1/energy_now" ]] || { echo 'Denali SAM BAT1 energy_now is required' >&2; exit 1; }

value() {
    local path=$1 v
    [[ -r "$path" ]] || return 0
    if v=$(<"$path") && [[ -n $v ]]; then
        printf '%s=%s\n' "$path" "${v//$'\n'/ }"
    fi
}

printf 'utc=%s\n' "$(date -u +%FT%TZ)"
printf 'boot_id=%s\n' "$(</proc/sys/kernel/random/boot_id)"
printf 'release=%s\n' "$(uname -r)"
printf 'uptime=%s\n' "$(</proc/uptime)"
for f in /sys/power/{state,mem_sleep,pm_wakeup_irq,suspend_stats/*}; do value "$f"; done
# BOOTTIME advances in suspend; MONOTONIC does not. Compare this offset
# between snapshots instead of treating a successful kernel cycle as residency.
if command -v python3 >/dev/null; then
    python3 - <<'PY'
import time
start = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
boot = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
end = time.clock_gettime_ns(time.CLOCK_MONOTONIC)
print(f"boottime_minus_monotonic_ns={boot - (start + end) // 2}")
PY
fi
for wake in /sys/class/wakeup/wakeup*; do
    [[ -d $wake ]] || continue
    for p in name event_count wakeup_count active_count expire_count; do value "$wake/$p"; done
done
for d in "$root"/{BAT1,ADP1,qcom-battmgr-{bat,ac,usb}}; do
    for p in {capacity,status,online,energy_now,energy_full,energy_full_design,power_now,cycle_count}; do
        value "$d/$p"
    done
done
for d in /sys/bus/platform/devices/{100000.clock-controller,3d90000.clock-controller,3d6a000.gmu,1d88000.crypto,1dfa000.crypto,interconnect-1,1700000.interconnect}; do
    [[ -d $d ]] || continue
    printf '%s/driver=%s\n' "$d" "$(readlink "$d/driver" || printf 'unbound')"
    value "$d/state_synced"
    value "$d/power/runtime_status"
done
for d in /sys/bus/rpmsg/devices/*APPS_ADSP_PWR_LMTS*; do
    [[ -d $d ]] || continue
    printf '%s/driver=%s\n' "$d" "$(readlink "$d/driver" || printf 'unbound')"
done
for f in /sys/class/drm/card*-*/{status,enabled}; do value "$f"; done
for f in /sys/class/platform-profile/*/{profile,choices}; do value "$f"; done
# Retain per-CPU interrupt counts for later before/after comparison.
printf '\n--- /proc/interrupts ---\n'
cat /proc/interrupts
if [[ -x /sys/kernel/debug ]]; then
    if [[ -r /sys/kernel/debug/wakeup_sources ]]; then
        printf '\n--- /sys/kernel/debug/wakeup_sources ---\n'
        cat /sys/kernel/debug/wakeup_sources
    fi
    shopt -s nullglob
    # These files report kernel accounting, not firmware residency. Preserve
    # all columns (including rejected and s2idle usage) and identify misses.
    for domain in power-domain-system power-domain-cpu-cluster{0,1,2}; do
        f=/sys/kernel/debug/pm_genpd/$domain/idle_states
        if [[ -r $f ]]; then
            printf '\n--- %s ---\n' "$f"
            cat "$f"
        else
            printf 'genpd_%s_idle_states=unavailable\n' "$domain"
        fi
    done
    for f in /sys/kernel/debug/{qcom_stats,rpmh_stats}/{cxsd,aosd,ddr,adsp,adsp_island}; do
        [[ -r $f ]] || continue
        printf '\n--- %s ---\n' "$f"
        cat "$f"
    done
else
    printf 'residency=debugfs_not_readable_without_privilege\n'
fi
