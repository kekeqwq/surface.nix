{
  runCommand,
  dtc,
  dtbs,
}:
runCommand "denali-qce-disabled-dtb-candidate" { nativeBuildInputs = [ dtc ]; } ''
  name=qcom/x1e80100-microsoft-denali-oled.dtb
  qce=/soc@0/crypto@1dfa000
  ice=/soc@0/crypto@1d88000
  touch=/soc@0/geniqup@ac0000/spi@a88000/touchscreen@0
  src=${dtbs}/$name
  test "$(fdtget -t s "$src" "$qce" compatible)" = 'qcom,x1e80100-qce qcom,sm8150-qce qcom,qce'
  test "$(fdtget -t s "$src" "$ice" compatible)" = 'qcom,x1e80100-inline-crypto-engine qcom,inline-crypto-engine'
  test "$(fdtget -t s "$src" "$touch" compatible)" = microsoft,denali-touchscreen
  test "$(fdtget -d okay -t s "$src" "$qce" status)" = okay
  test "$(fdtget -t x "$src" "$qce" reg)" = '0 1dfa000 0 6000'

  install -Dm0644 "$src" "$out/$name"
  fdtput -t s "$out/$name" "$qce" status disabled
  test "$(fdtget -t s "$out/$name" "$qce" status)" = disabled
  # Round trip the status property: prove no other DT node or property changed.
  cp "$out/$name" restored.dtb
  if fdtget "$src" "$qce" status >/dev/null 2>&1; then
    fdtput -t s restored.dtb "$qce" status okay
  else
    fdtput -d restored.dtb "$qce" status
  fi
  dtc -q -s -I dtb -O dts "$src" > original.dts
  dtc -q -s -I dtb -O dts restored.dtb > restored.dts
  cmp original.dts restored.dts
''
