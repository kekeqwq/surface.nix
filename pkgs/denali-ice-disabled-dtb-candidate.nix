{
  runCommand,
  dtc,
  dtbs,
}:
runCommand "denali-unused-ufs-ice-disabled-dtb-candidate" { nativeBuildInputs = [ dtc ]; } ''
  set -o pipefail
  name=qcom/x1e80100-microsoft-denali-oled.dtb
  qce=/soc@0/crypto@1dfa000
  ice=/soc@0/crypto@1d88000
  ufs=/soc@0/ufshc@1d84000
  src=${dtbs}/$name
  test "$(fdtget -t s "$src" "$qce" status)" = disabled
  test "$(fdtget -t s "$src" "$ice" compatible)" = 'qcom,x1e80100-inline-crypto-engine qcom,inline-crypto-engine'
  test "$(fdtget -t x "$src" "$ice" reg)" = '0 1d88000 0 18000'
  test "$(fdtget -d okay -t s "$src" "$ice" status)" = okay
  test "$(fdtget -t s "$src" "$ufs" status)" = disabled
  phandle=$(fdtget -t x "$src" "$ice" phandle)
  test "$(fdtget -t x "$src" "$ufs" qcom,ice)" = "$phandle"
  dtc -q -s -I dtb -O dts "$src" > original.dts
  # On the locked Denali DT, this is the only qcom,ice binding to this engine.
  test "$(grep -Ec "^[[:space:]]*qcom,ice = <0x0*$phandle>;" original.dts)" = 1

  install -Dm0644 "$src" "$out/$name"
  fdtput -t s "$out/$name" "$ice" status disabled
  test "$(fdtget -t s "$out/$name" "$ice" status)" = disabled
  cp "$out/$name" restored.dtb
  if fdtget "$src" "$ice" status >/dev/null 2>&1; then
    fdtput -t s restored.dtb "$ice" status okay
  else
    fdtput -d restored.dtb "$ice" status
  fi
  dtc -q -s -I dtb -O dts restored.dtb > restored.dts
  cmp original.dts restored.dts
''
