#!/usr/bin/env bash
# Run a bounded diagnostic command with a private tracefs instance. This helper
# does not suspend, touch a codec register, or change global tracing settings.
set -euo pipefail

usage() { printf 'Usage: %s -- absolute-command [args...]\n' "$0" >&2; exit 2; }
[[ $# -ge 2 && $1 == -- && $2 == /* ]] || usage
shift
[[ $EUID == 0 ]] || { echo 'Trace collection requires root.' >&2; exit 1; }

tracefs=/sys/kernel/tracing
[[ -d $tracefs/instances && -w $tracefs/instances ]] || {
  echo 'A mounted tracefs with instance support is required.' >&2
  exit 1
}
instance=$tracefs/instances/denali-lpass-pm-$$
mkdir "$instance"
cleanup() {
  local previous=$?
  trap - EXIT
  printf '0\n' > "$instance/tracing_on" || true
  printf '\n--- Denali LPASS PM trace ---\n'
  if ! cat "$instance/trace"; then
    [[ $previous != 0 ]] || previous=1
  fi
  if ! rmdir "$instance"; then
    echo "Failed to remove private trace instance: $instance" >&2
    [[ $previous != 0 ]] || previous=1
  fi
  exit "$previous"
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

printf '0\n' > "$instance/tracing_on"
printf 'nop\n' > "$instance/current_tracer"
printf '128\n' > "$instance/buffer_size_kb"
# Use a common cross-CPU clock when available to compare PM ordering.
if grep -qw boot "$instance/trace_clock"; then
  printf 'boot\n' > "$instance/trace_clock"
fi

enable() {
  local event=$1 field=${2:-} path
  path=$instance/events/$event
  [[ -w $path/enable ]] || { printf 'Missing tracepoint: %s\n' "$event" >&2; exit 1; }
  if [[ -n $field ]]; then
    printf '%s == "6d44000.codec" || %s == "6b00000.codec"\n' "$field" "$field" > "$path/filter"
  fi
  printf '1\n' > "$path/enable"
}

enable power/suspend_resume
enable power/device_pm_callback_start device
enable power/device_pm_callback_end device
enable rpm/rpm_suspend name
enable rpm/rpm_resume name
enable rpm/rpm_return_int name
enable regmap/regmap_cache_only name
enable regmap/regcache_sync name

printf '1\n' > "$instance/tracing_on"
"$@"
