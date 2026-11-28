{
  runCommand,
  dtc,
  dtbs,
}:
runCommand "denali-cpu-thermal-guard-dtb" { nativeBuildInputs = [ dtc ]; } ''
  set -euo pipefail
  name=qcom/x1e80100-microsoft-denali-oled.dtb
  src=${dtbs}/$name
  outDtb=$out/$name
  thermal=/thermal-zones
  tripName=denali-passive-trip
  mapName=denali-passive-map

  dtc -q -s -I dtb -O dts "$src" >original.dts
  # Allocate new local references above all existing FDT phandles.
  next=1
  while read -r phandle; do
    n=$((16#$phandle))
    if (( n >= next )); then next=$((n + 1)); fi
  done < <(grep -oE '^[[:space:]]*(linux,)?phandle = <0x[0-9a-f]+>;' original.dts | cut -d x -f2 | cut -d '>' -f1)
  test "$next" -gt 1
  test "$next" -lt 4294967265
  install -Dm0644 "$src" "$outDtb"

  for cluster in 0 1 2; do
    case $cluster in
      0) cpu=/cpus/cpu@0 ;;
      1) cpu=/cpus/cpu@10000 ;;
      2) cpu=/cpus/cpu@20000 ;;
    esac
    test "$(fdtget -t u "$src" "$cpu" '#cooling-cells')" = 2
    cpuPhandle=$(fdtget -t x "$src" "$cpu" phandle)
    for zone in cpu"$cluster"-{0,1,2,3}-{top,btm}-thermal cpuss"$cluster"-{top,btm}-thermal; do
      z=$thermal/$zone
      trips=$z/trips
      maps=$z/cooling-maps
      # Qualify the exact baseline: no existing passive polling or cooling maps,
      # and an unchanged critical trip. Disabled sensors remain disabled.
      critical=$(fdtget -l "$src" "$trips")
      [[ $critical =~ ^[a-z0-9-]+$ ]]
      test "$(fdtget -t s "$src" "$trips/$critical" type)" = critical
      test "$(fdtget -t u "$src" "$trips/$critical" temperature)" = 115000
      ! fdtget "$src" "$z" polling-delay-passive >/dev/null 2>&1
      ! fdtget -p "$src" "$maps" >/dev/null 2>&1

      point=$(printf '%x' "$next")
      next=$((next + 1))
      fdtput -t u "$outDtb" "$z" polling-delay-passive 200
      fdtput -c "$outDtb" "$trips/$tripName"
      fdtput -t u "$outDtb" "$trips/$tripName" temperature 85000
      fdtput -t u "$outDtb" "$trips/$tripName" hysteresis 2000
      fdtput -t s "$outDtb" "$trips/$tripName" type passive
      fdtput -t x "$outDtb" "$trips/$tripName" phandle "$point"
      fdtput -cp "$outDtb" "$maps/$mapName"
      fdtput -t x "$outDtb" "$maps/$mapName" trip "$point"
      fdtput -t x "$outDtb" "$maps/$mapName" cooling-device "$cpuPhandle" ffffffff ffffffff
      test "$(fdtget -t s "$outDtb" "$trips/$tripName" type)" = passive
      test "$(fdtget -t u "$outDtb" "$trips/$tripName" temperature)" = 85000
      test "$(fdtget -t u "$outDtb" "$trips/$tripName" hysteresis)" = 2000
      test "$(fdtget -t x "$outDtb" "$maps/$mapName" trip)" = "$(fdtget -t x "$outDtb" "$trips/$tripName" phandle)"
      test "$(fdtget -t x "$outDtb" "$maps/$mapName" cooling-device)" = "$cpuPhandle ffffffff ffffffff"
      printf '%s\n' "$z" >>zones
    done
  done

  test "$(wc -l < zones)" = 30
  cp "$outDtb" restored.dtb
  while read -r z; do
    fdtput -d restored.dtb "$z" polling-delay-passive
    fdtput -r restored.dtb "$z/trips/$tripName" "$z/cooling-maps"
  done <zones
  dtc -q -s -I dtb -O dts restored.dtb >restored.dts
  cmp original.dts restored.dts
''
