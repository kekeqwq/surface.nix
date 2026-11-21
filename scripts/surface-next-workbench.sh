#!/usr/bin/env bash
# Run in nix develop .#surface-next on AArch64 Linux.
set -euo pipefail
snapshot=${SURFACE_NEXT_SOURCE:?run in nix develop .#surface-next}
state=${XDG_STATE_HOME:-$HOME/.local/state}/surface-next
work=$state/$(basename "$snapshot" .tar.gz)-${SURFACE_NEXT_RELEASE:-upstream}
mkdir -p "$work/out"
work=$(cd -- "$work" && pwd)
exec 9>"$work/build.lock"
flock 9
if [[ ! -d $work/src ]]; then
  tmp=$(mktemp -d "$work/.src.XXXXXX")
  trap 'rm -rf -- "$tmp"' EXIT
  tar -xf "$snapshot" -C "$tmp" --strip-components=1
  chmod -R u+w "$tmp"
  for p in ${SURFACE_NEXT_PATCHES:-}; do
    patch --batch --fuzz=0 -p1 -d "$tmp" <"$p"
  done
  printf '%s\n' "${SURFACE_NEXT_PATCHES:-}" >"$work/patch-seed"
  mv -- "$tmp" "$work/src"
  trap - EXIT
fi
out=$work/out
config=${SURFACE_NEXT_CONFIG:?run in nix develop .#surface-next}
if [[ $(<"$work/patch-seed") != "${SURFACE_NEXT_PATCHES:-}" ]]; then
  echo 'Patch queue changed: apply the delta to the printed source tree and review it before rebuilding.' >&2
  echo "Source: $work/src" >&2
  echo 'Keep out/ intact for incremental compilation. Update patch-seed explicitly after reconciling the tree.' >&2
  exit 1
fi
kmake() { make -C "$work/src" O="$out" ARCH=arm64 LOCALVERSION="${SURFACE_NEXT_LOCALVERSION:-}" "$@"; }
printf 'Source: %s\nOutput: %s\n' "$work/src" "$out"
case ${1:-build} in
  paths) ;;
  build|config)
    if [[ ! -f $out/.config ]] || ! cmp -s "$config" "$work/config-seed"; then
      cp -- "$config" "$out/.config"
      cp -- "$config" "$work/config-seed"
    fi
    kmake olddefconfig
    if [[ ${1:-build} == build ]]; then
      kmake -j"${SURFACE_NEXT_JOBS:-8}" vmlinuz.efi qcom/x1e80100-microsoft-denali-oled.dtb modules
    fi
    ;;
  *) echo 'usage: surface-next-workbench.sh [paths|config|build]' >&2; exit 2 ;;
esac
