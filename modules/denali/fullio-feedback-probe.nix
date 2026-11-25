packages: probe: experiment:
{
  config,
  lib,
  pkgs,
  ...
}:
let
  dtb = "x1e80100-microsoft-denali-oled-feedback-${probe}.dtb";
  name = if probe == "vi" then "Denali-FullIO-VI-Probe" else "Denali-FullIO-CPS-Probe";
  # The probe DT has no VA/TX-DMIC or WSA playback links. Their inherited
  # DAPM routes name widgets that are not registered in a capture-only card.
  probeDtbs =
    pkgs.runCommand "denali-fullio-${probe}-probe-dtbs" { nativeBuildInputs = [ pkgs.dtc ]; }
      ''
            install -Dm644 ${packages.fullio-feedback-probe-kernel}/dtbs/qcom/${dtb} "$out/qcom/${dtb}"
            fdtput -d "$out/qcom/${dtb}" /sound audio-routing
        ${lib.optionalString (experiment != null) ''
          fdtput "$out/qcom/${dtb}" /soc@0/soundwire@6b10000 qcom,denali-cps-probe-wake-test
        ''}
        ${lib.optionalString (experiment == "offset2") ''
          fdtput "$out/qcom/${dtb}" /soc@0/soundwire@6b10000 qcom,denali-cps-probe-active-offset2-test
        ''}
            test "$(fdtget -l "$out/qcom/${dtb}" /sound)" = "wsa-${probe}-dai-link"
            test "$(fdtget "$out/qcom/${dtb}" /sound model)" = ${lib.escapeShellArg name}
      '';
  probeFirmware = pkgs.runCommand "denali-fullio-${probe}-probe-firmware" { } ''
    install -Dm644 ${packages.fullio-feedback-probes}/share/sp11-fullio/probe-${probe}.bin \
      "$out/lib/firmware/qcom/x1e80100/${name}-tplg.bin"
  '';
in
assert
  experiment == null
  || (
    probe == "cps"
    && builtins.elem experiment [
      "wake"
      "offset2"
    ]
  );
assert builtins.elem probe [
  "vi"
  "cps"
];
{
  assertions = [
    {
      assertion =
        config.surface.devices.denali.enable && pkgs.stdenv.hostPlatform.system == "aarch64-linux";
      message = "A FullIO capture probe requires an enabled ARM64 Denali configuration.";
    }
  ];
  boot.kernelPackages = lib.mkForce (pkgs.linuxPackagesFor packages.fullio-feedback-probe-kernel);
  hardware.deviceTree = {
    name = lib.mkForce "qcom/${dtb}";
    filter = lib.mkForce dtb;
    dtbSource = probeDtbs;
  };
  hardware.firmware = [ (lib.hiPrio probeFirmware) ];
  # No automatic opening, sources or sinks: the probe is controlled with ALSA.
  services.pipewire.wireplumber.extraConfig."51-surface-speaker" = lib.mkForce {
    "monitor.alsa.rules" = [
      {
        matches = [ { "device.name" = "alsa_card.platform-sound"; } ];
        actions.update-props."device.disabled" = true;
      }
    ];
  };
}
