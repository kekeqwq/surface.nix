#!/usr/bin/env bash
# Run on Denali. The kernel outputs must not already exist locally.
set -euo pipefail
if (( $# < 2 )); then
  echo 'Usage: time-full-build.sh <system-flake> <log-directory> [nix build flags...]' >&2
  exit 2
fi
flake=${1%/}
logs=$2
shift 2
mkdir -p "$logs"
kernel="$flake#nixosConfigurations.surface.pkgs.surfacePackages.surfaceNext"
system="$flake#nixosConfigurations.surface.config.system.build.toplevel"
check="$flake#checks.aarch64-linux.surface-boundaries"
flags=(--no-write-lock-file --option builders '' "$@")
drv=$(nix eval "${flags[@]}" --raw "$kernel.drvPath")
[[ $drv == *-surface-next-*.drv ]]
printf '%s\n' "$drv" > "$logs/kernel.drv"
mapfile -t outputs < <(nix-store --query --outputs "$drv")
(( ${#outputs[@]} > 0 ))
for path in "${outputs[@]}"; do
  if nix path-info --offline "$path" >/dev/null 2>&1; then
    echo "Not a fresh compile: $path already exists; refusing to report a time" >&2
    exit 2
  fi
done

SECONDS=0
nix build "${flags[@]}" --print-build-logs --option substitute false \
  --no-link "$kernel" > "$logs/kernel.log" 2>&1
kernel_seconds=$SECONDS
printf 'kernel_seconds=%s\n' "$kernel_seconds" | tee "$logs/timing.txt"
nix build "${flags[@]}" --print-build-logs --out-link "$logs/result" \
  "$system" "$check" > "$logs/system.log" 2>&1
total=$SECONDS
printf 'closure_seconds=%s\ntotal_seconds=%s\n' "$((total - kernel_seconds))" "$total" | tee -a "$logs/timing.txt"
if (( total >= 600 )); then
  echo 'FAIL: whole build took at least 10 minutes' >&2
  exit 1
fi
printf 'PASS: full kernel build and system closure completed in %ss\n' "$total"
