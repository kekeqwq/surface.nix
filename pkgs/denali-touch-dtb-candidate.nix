{
  runCommand,
  dtc,
  dtbs,
}:
runCommand "denali-mshw0485-dtb-candidate" { nativeBuildInputs = [ dtc ]; } ''
  name=qcom/x1e80100-microsoft-denali-oled.dtb
  spi=/soc@0/geniqup@ac0000/spi@a88000
  touch=$spi/touchscreen@0
  regulator=/regulator-ts
  src=${dtbs}/$name
  test "$(fdtget "$src" "$spi" compatible)" = qcom,geni-spi-qspi
  test "$(fdtget "$src" "$spi" dma-names)" = 'tx rx'
  read -r dma tx engine protocol dma_rx rx engine_rx protocol_rx <<< "$(fdtget -t x "$src" "$spi" dmas)"
  test -n "$dma"
  test "$tx:$engine:$protocol:$dma_rx:$rx:$engine_rx:$protocol_rx" = "0:2:4:$dma:1:2:4"
  test "$(fdtget "$src" "$touch" compatible)" = microsoft,denali-touchscreen
  test "$(fdtget -t u "$src" "$touch" spi-max-frequency)" = 40000000
  for dir in rx tx; do test "$(fdtget -t u "$src" "$touch" spi-$dir-bus-width)" = 4; done
  read -r tlmm reset flag <<< "$(fdtget -t x "$src" "$touch" reset-gpios)"
  test -n "$tlmm"
  test "$reset:$flag" = '30:1'
  test "$(fdtget -t x "$src" "$touch" interrupts-extended)" = "$tlmm 33 2"
  test "$(fdtget "$src" "$regulator" compatible)" = regulator-fixed
  test "$(fdtget -t x "$src" "$regulator" gpio)" = "$tlmm 40 0"
  fdtget "$src" "$regulator" enable-active-high >/dev/null
  test "$(fdtget -t x "$src" "$touch" vdd-supply)" = "$(fdtget -t x "$src" "$regulator" phandle)"
  ! fdtget "$src" "$touch" power-gpios >/dev/null 2>&1 || exit 1
  ! fdtget "$src" "$touch" interrupt-gpios >/dev/null 2>&1 || exit 1

  install -Dm0644 "$src" "$out/$name"
  fdtput -t s "$out/$name" "$touch" compatible microsoft,mshw0485
  fdtput -t x "$out/$name" "$touch" interrupt-gpios "$tlmm" 33 1
  test "$(fdtget "$out/$name" "$touch" compatible)" = microsoft,mshw0485
  test "$(fdtget -t x "$out/$name" "$touch" interrupt-gpios)" = "$tlmm 33 1"
''
